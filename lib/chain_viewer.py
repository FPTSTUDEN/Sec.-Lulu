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
    
    def __init__(self, parent, db, node_id: int, title: str = "Content Chain"):
        super().__init__(parent)
        self.db = db
        self.node_id = node_id
        self.title(title)
        self.geometry("800x600")
        self.attributes("-topmost", True)
        
        # Store references to widgets - RENAME TO AVOID CONFLICT
        self.backward_chain_data = []  # Changed from self.backward_chain
        self.current_node = None
        self.child_nodes = []  # Changed from self.children
        
        self._setup_ui()
        self._load_chain()
    
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
        
        # Store button references
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
        
        # Clear content - MORE ROBUST CLEANUP
        widgets_to_destroy = list(self.content_frame.winfo_children())
        for widget in widgets_to_destroy:
            try:
                widget.destroy()
            except Exception as e:
                print(f"Error destroying widget: {e}")
        
        if tab_name == "backward":
            self._show_backward_chain()
        elif tab_name == "forward":
            self._show_forward_chain()
        elif tab_name == "related":
            self._show_related_words()
    
    def _load_chain(self):
        """Load chain data from database"""
        try:
            self.backward_chain_data = self.db.get_content_chain(self.node_id)
            self.current_node = self.db.get_content_node(self.node_id)
            self.child_nodes = self.db.get_node_children(self.node_id)
            
            # Update status
            node_type = self.current_node['node_type'] if self.current_node else 'Unknown'
            self.status_label.configure(text=f"Node ID: {self.node_id} | Type: {node_type}")
            
            # Show backward chain by default
            self._show_backward_chain()
        except Exception as e:
            self.status_label.configure(text=f"Error loading chain: {e}", text_color="red")
    
    def _show_backward_chain(self):
        """Show the chain of ancestors (where this content came from)"""
        if not self.backward_chain_data or len(self.backward_chain_data) == 0:
            ctk.CTkLabel(self.content_frame, text="No backward chain found.", 
                         text_color="gray").pack(pady=20)
            return
        
        # Show current node first (as the focus)
        if self.current_node:
            self._add_node_card(self.current_node, is_current=True)
        
        # Show "came from" arrow if there are ancestors
        if len(self.backward_chain_data) > 1:
            arrow_label = ctk.CTkLabel(self.content_frame, text="⬇️ Came from ⬇️", 
                                        font=ctk.CTkFont(size=12), text_color="orange")
            arrow_label.pack(pady=5)
        
        # Show ancestors in reverse order (oldest to newest)
        # Exclude current node (last in chain)
        ancestors = self.backward_chain_data[:-1] if len(self.backward_chain_data) > 1 else []
        for i, node in enumerate(reversed(ancestors)):
            self._add_node_card(node, is_current=False)
            
            # Add arrow between ancestors (except after last one)
            if i < len(ancestors) - 1:
                arrow = ctk.CTkLabel(self.content_frame, text="↓", font=ctk.CTkFont(size=10))
                arrow.pack(pady=2)
    
    def _show_forward_chain(self):
        """Show what this node led to (children)"""
        if not self.child_nodes:
            ctk.CTkLabel(self.content_frame, text="No forward chain found (nothing led from this content).", 
                         text_color="gray").pack(pady=20)
            return
        
        # Show current node
        if self.current_node:
            self._add_node_card(self.current_node, is_current=True)
        
        # Show arrow
        arrow_label = ctk.CTkLabel(self.content_frame, text="⬇️ Led to ⬇️", 
                                    font=ctk.CTkFont(size=12), text_color="green")
        arrow_label.pack(pady=5)
        
        # Show children
        for i, child in enumerate(self.child_nodes):
            child_node = self.db.get_content_node(child['id'])
            if child_node:
                self._add_node_card(child_node, is_current=False)
                
                # Add arrow between children (except after last one)
                if i < len(self.child_nodes) - 1:
                    arrow = ctk.CTkLabel(self.content_frame, text="↓", font=ctk.CTkFont(size=10))
                    arrow.pack(pady=2)
    
    def _show_related_words(self):
        """Show words related through content chains"""
        # First, get the main word from the current node
        main_word = None
        if self.current_node and self.current_node.get('node_type') == 'word_lookup':
            main_word = self.current_node.get('title') or self.current_node.get('content', '')[:20]
        
        if not main_word and self.current_node:
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
        if not node:
            return
            
        card = ctk.CTkFrame(self.content_frame, 
                            fg_color=("#3a6ea5" if is_current else "gray85", 
                                     "#1a4a7a" if is_current else "gray25"),
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
        if content:
            if len(content) > 200:
                content = content[:200] + "..."
            ctk.CTkLabel(card, text=content, wraplength=600, justify="left", 
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15, pady=5)
        
        # Action buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        if node.get('id') != self.node_id:
            view_btn = ctk.CTkButton(btn_frame, text="View Chain", width=80, height=25,
                                      command=lambda nid=node['id']: self._open_chain(nid))
            view_btn.pack(side="right", padx=2)
    
    def _open_chain(self, node_id: int):
        """Open chain viewer for another node"""
        try:
            new_viewer = ChainViewer(self, self.db, node_id, f"Content Chain - Node {node_id}")
            new_viewer.focus()
        except Exception as e:
            print(f"Error opening chain viewer: {e}")
    
    def _show_graph_view(self):
        """Show chain as a simple text graph"""
        if not self.backward_chain_data:
            return
        
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Create text graph
        graph_text = ctk.CTkTextbox(self.content_frame, wrap="none", font=("Consolas", 10))
        graph_text.pack(fill="both", expand=True)
        
        lines = []
        for i, node in enumerate(self.backward_chain_data):
            prefix = "└─ " if i == len(self.backward_chain_data) - 1 else "├─ "
            lines.append(f"{prefix}[{node['node_type'][:8]}] {node.get('title', 'Untitled')[:40]}")
        
        graph_text.insert("1.0", "\n".join(lines))
        graph_text.configure(state="disabled")

    def _lookup_word(self, word: str):
        """Trigger word lookup in main app"""
        self.status_label.configure(text=f"Looking up: {word}")
        print(f"Lookup word: {word}")
    
    def destroy(self):
        """Clean up when closing"""
        try:
            super().destroy()
        except Exception as e:
            print(f"Error destroying ChainViewer: {e}")