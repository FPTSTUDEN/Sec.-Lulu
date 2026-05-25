# lib/chain_viewer.py
import customtkinter as ctk
from datetime import datetime
import json
from typing import List, Dict, Optional


class ChainViewer(ctk.CTkToplevel):
    """
    Popup window to display content chain relationships.
    Shows both backward chain (ancestors) and forward chain (children).
    """
    
    def __init__(self, parent, db, node_id: int, title: str = "Content Chain",
                 data_service=None, generate_callback=None, word_index=None, char_def_index=None):
        super().__init__(parent)
        self.db = db
        self.node_id = node_id
        self.data_service = data_service
        self.generate_callback = generate_callback
        self.word_index = word_index or {}
        self.char_def_index = char_def_index or {}
        self.title(title)
        self.geometry("800x600")
        self.attributes("-topmost", True)
        
        # Data attributes (will be populated in background thread)
        self.backward_chain = None
        self.current_node = None
        self.children = None
        
        self._setup_ui()
        # Load chain data in background thread to avoid freezing UI
        import threading
        threading.Thread(target=self._load_chain_background, daemon=True).start()
    
    def _setup_ui(self):
        # Main frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        ctk.CTkLabel(main_frame, text="🔗 Content Relationship Chain", 
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=5)
        
        # Create notebook-style tabs (using frames)
        tab_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        tab_frame.pack(fill="x", pady=5)
        
        self.backward_btn = ctk.CTkButton(tab_frame, text="⬅️ Backward Chain (Origin)",
                                          command=lambda: self._show_tab("backward"),
                                          fg_color="blue", width=150)
        self.backward_btn.pack(side="left", padx=5)
        
        self.forward_btn = ctk.CTkButton(tab_frame, text="➡️ Forward Chain (Led To)",
                                         command=lambda: self._show_tab("forward"),
                                         fg_color="gray", width=150)
        self.forward_btn.pack(side="left", padx=5)
        
        self.related_btn = ctk.CTkButton(tab_frame, text="🔗 Related Words",
                                         command=lambda: self._show_tab("related"),
                                         fg_color="gray", width=150)
        self.related_btn.pack(side="left", padx=5)
        
        # Content area (scrollable)
        self.content_frame = ctk.CTkScrollableFrame(main_frame)
        self.content_frame.pack(fill="both", expand=True, pady=10)
        
        # Status label
        self.status_label = ctk.CTkLabel(main_frame, text="", text_color="gray")
        self.status_label.pack()
    
    def _show_tab(self, tab_name):
        # Update button colors
        self.backward_btn.configure(fg_color="blue" if tab_name == "backward" else "gray")
        self.forward_btn.configure(fg_color="blue" if tab_name == "forward" else "gray")
        self.related_btn.configure(fg_color="blue" if tab_name == "related" else "gray")
        
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        if tab_name == "backward":
            self._show_backward_chain()
        elif tab_name == "forward":
            self._show_forward_chain()
        elif tab_name == "related":
            self._show_related_words()
    
    def _load_chain_background(self):
        """Load chain data from database in background thread"""
        try:
            self.backward_chain = self.db.get_content_chain(self.node_id)
            self.current_node = self.db.get_content_node(self.node_id)
            self.children = self.db.get_node_children(self.node_id)
            
            # Schedule UI update on main thread
            self.after(0, self._load_chain_complete)
        except Exception as e:
            print(f"Error loading chain data: {e}")
            self.after(0, lambda: self.status_label.configure(text=f"Error loading chain: {e}"))
    
    def _load_chain_complete(self):
        """Complete chain loading on main thread after data is fetched"""
        # Update status
        self.status_label.configure(text=f"Node ID: {self.node_id} | Type: {self.current_node['node_type'] if self.current_node else 'Unknown'}")
        
        # Show backward chain by default
        self._show_backward_chain()
    
    def _show_backward_chain(self):
        """Show the chain of ancestors (where this content came from)"""
        if not self.backward_chain:
            ctk.CTkLabel(self.content_frame, text="No backward chain found.", 
                         text_color="gray").pack(pady=20)
            return
        
        # Show current node first (as the focus)
        self._add_node_card(self.current_node, is_current=True)
        
        # Show "came from" arrow
        if len(self.backward_chain) > 1:
            arrow_label = ctk.CTkLabel(self.content_frame, text="⬇️ Came from ⬇️", 
                                        font=ctk.CTkFont(size=12), text_color="orange")
            arrow_label.pack(pady=5)
        
        # Show ancestors in reverse order (oldest to newest)
        for node in reversed(self.backward_chain[:-1]):  # Exclude current node
            self._add_node_card(node, is_current=False)
            
            # Add arrow to next
            if node != self.backward_chain[0]:
                arrow = ctk.CTkLabel(self.content_frame, text="↓", font=ctk.CTkFont(size=10))
                arrow.pack(pady=2)
    
    def _show_forward_chain(self):
        """Show what this node led to (children)"""
        children = self.db.get_node_children(self.node_id)
        
        if not children:
            ctk.CTkLabel(self.content_frame, text="No forward chain found (nothing led from this content).", 
                         text_color="gray").pack(pady=20)
            return
        
        # Show current node
        self._add_node_card(self.current_node, is_current=True)
        
        # Show arrow
        arrow_label = ctk.CTkLabel(self.content_frame, text="⬇️ Led to ⬇️", 
                                    font=ctk.CTkFont(size=12), text_color="green")
        arrow_label.pack(pady=5)
        
        # Show children
        for child in children:
            child_node = self.db.get_content_node(child['id'])
            if child_node:
                self._add_node_card(child_node, is_current=False)
                
                # Add arrow between children
                if child != children[-1]:
                    arrow = ctk.CTkLabel(self.content_frame, text="↓", font=ctk.CTkFont(size=10))
                    arrow.pack(pady=2)
    
    def _show_related_words(self):
        """Show words related through content chains"""
        # First, get the main word from the current node
        main_word = None
        if self.current_node and self.current_node['node_type'] == 'word_lookup':
            main_word = self.current_node.get('title') or self.current_node.get('content')[:20]
        
        if not main_word:
            # Try to extract from content
            content = self.current_node.get('content', '')
            # Look for Chinese words
            import re
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', content)
            if chinese_words:
                main_word = chinese_words[0]
        
        if main_word:
            ctk.CTkLabel(self.content_frame, text=f"🎯 Words related to '{main_word}':", 
                         font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=5)
        
        related = self.db.find_connected_words(main_word) if main_word else []
        
        if not related:
            ctk.CTkLabel(self.content_frame, text="No related words found in this content chain.", 
                         text_color="gray").pack(pady=20)
            return
        
        for rel in related:
            word_frame = ctk.CTkFrame(self.content_frame, fg_color=("gray90", "gray25"), corner_radius=8)
            word_frame.pack(fill="x", pady=3, padx=5)
            
            ctk.CTkLabel(word_frame, text=rel['word'], font=ctk.CTkFont(weight="bold", size=14)).pack(side="left", padx=10, pady=5)
            ctk.CTkLabel(word_frame, text=f"Strength: {rel['strength']}", text_color="gray").pack(side="left", padx=10)
            
            def lookup(w=rel['word']):
                self._lookup_word(w)
            
            ctk.CTkButton(word_frame, text="Lookup", width=60, command=lookup).pack(side="right", padx=5)
    
    def _add_node_card(self, node: Dict, is_current: bool = False):
        """Add a visual card for a content node"""
        card = ctk.CTkFrame(self.content_frame, 
                            fg_color=("blue" if is_current else "gray85", 
                                     "darkblue" if is_current else "gray25"),
                            corner_radius=10)
        card.pack(fill="x", pady=5, padx=5)
        
        # Header with node type and timestamp
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        
        type_icons = {
            'raw_text': '📄',
            'sentence': '📖',
            'query': '❓',
            'response': '💬',
            'word_lookup': '🔍'
        }
        icon = type_icons.get(node.get('node_type', ''), '📌')
        
        time_str = datetime.fromtimestamp(node.get('created_at', 0)).strftime('%H:%M:%S') if node.get('created_at') else 'Unknown'
        
        ctk.CTkLabel(header, text=f"{icon} {node.get('node_type', 'Unknown').upper()}", 
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text=time_str, text_color="gray", font=ctk.CTkFont(size=10)).pack(side="right")
        
        # Title (if exists)
        if node.get('title'):
            ctk.CTkLabel(card, text=f"📌 {node['title']}", 
                         font=ctk.CTkFont(weight="bold"), wraplength=600, justify="left").pack(anchor="w", padx=15)
        
        # Content preview
        content = node.get('content', '')
        if len(content) > 200:
            content = content[:200] + "..."
        if content:
            ctk.CTkLabel(card, text=content, wraplength=600, justify="left", 
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15, pady=5)
        
        # Action buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        if node.get('id') != self.node_id:
            # View Full button - opens content with full features (lookup, save, etc.)
            view_full_btn = ctk.CTkButton(btn_frame, text="👁️ View Full", width=80, height=25,
                                          fg_color="green",
                                          command=lambda nid=node['id']: self._view_full_content(nid))
            view_full_btn.pack(side="right", padx=2)
            
            # View Chain button - navigates to child node's chain
            view_btn = ctk.CTkButton(btn_frame, text="🔗 View Chain", width=90, height=25,
                                      fg_color="blue",
                                      command=lambda nid=node['id']: self._open_chain(nid))
            view_btn.pack(side="right", padx=2)
    
    def _open_chain(self, node_id: int):
        """Open chain viewer for another node"""
        new_viewer = ChainViewer(self, self.db, node_id, f"Content Chain - Node {node_id}",
                                 data_service=self.data_service,
                                 generate_callback=self.generate_callback,
                                 word_index=self.word_index,
                                 char_def_index=self.char_def_index)
        new_viewer.focus()
    
    def _view_full_content(self, node_id: int):
        """Open full content in Long_message_popup with all features"""
        node = self.db.get_content_node(node_id)
        if not node:
            return
        
        # Import here to avoid circular imports
        from lib.windows import Long_message_popup
        
        popup = Long_message_popup(
            title=node.get('title', 'Content'),
            message=node.get('content', ''),
            master=self,
            display_image=False,
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service,
            generate_explanation_callback=self.generate_callback,
            parent_node_id=node_id
        )
        popup.show()
    
    def _lookup_word(self, word: str):
        """Trigger word lookup in main app"""
        # This should communicate back to main app
        # For now, just show a message
        self.status_label.configure(text=f"Looking up: {word} (integration with main app needed)")