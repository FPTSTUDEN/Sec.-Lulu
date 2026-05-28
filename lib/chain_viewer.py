"""
Chain Viewer for learning content hierarchy.
Displays clickable chain of related content with clean visual design,
plus graph visualization and node detail panel.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Dict, List, Optional
import math


class ChainViewer(ctk.CTkToplevel):
    """
    Popup window that displays the learning chain for any content node.
    Shows hierarchical relationships: User Query -> AI Response -> Word Lookup
    """
    
    # Icons for different node types
    NODE_ICONS = {
        'raw_text': '📄',
        'sentence': '📖',
        'query': '❓',
        'response': '💬',
        'word_lookup': '🔍',
        'explanation': '✨'
    }
    
    NODE_COLORS = {
        'query': '#2e7d32',      # green
        'response': '#1565c0',   # blue
        'word_lookup': '#e65100', # orange
        'sentence': '#6a1b9a',    # purple
        'raw_text': '#795548',    # brown
        'default': '#37474f'       # gray
    }
    
    def __init__(self, parent, db, node_id: int, title: str = "Learning Chain"):
        """
        Args:
            parent: Parent tkinter window
            db: VocabDatabase instance
            node_id: ID of the node to view chain for
            title: Window title
        """
        super().__init__(parent)
        self.db = db
        self.node_id = node_id
        self.title(title)
        self.geometry("900x700")
        self.attributes("-topmost", True)
        
        # Store parent reference
        self._parent_ref = parent
        
        # Data attributes
        self.backward_chain = []
        self.current_node = None
        self.child_nodes = []
        
        # Graph zoom/pan state
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Setup UI
        self._setup_ui()
        self._load_chain_data()
    
    def _setup_ui(self):
        """Create the UI components."""
        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tab control
        tab_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        tab_frame.pack(fill="x", pady=(0, 10))
        
        self.list_tab_btn = ctk.CTkButton(
            tab_frame, text="📋 List View", width=120,
            command=lambda: self._show_tab("list"),
            fg_color="#1565c0"
        )
        self.list_tab_btn.pack(side="left", padx=5)
        
        self.graph_tab_btn = ctk.CTkButton(
            tab_frame, text="🔗 Graph View", width=120,
            command=lambda: self._show_tab("graph"),
            fg_color="gray"
        )
        self.graph_tab_btn.pack(side="left", padx=5)
        
        self.detail_tab_btn = ctk.CTkButton(
            tab_frame, text="📊 Node Details", width=120,
            command=lambda: self._show_tab("detail"),
            fg_color="gray"
        )
        self.detail_tab_btn.pack(side="left", padx=5)
        
        # Node info label
        self.info_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            text_color="gray",
            font=ctk.CTkFont(size=11)
        )
        self.info_label.pack(pady=(0, 5))
        
        # Content area (changes based on tab)
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        
        # List view frame (default)
        self.list_frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        
        # Graph view frame
        self.graph_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        
        # Detail view frame
        self.detail_frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        
        # Show list view by default
        self._show_tab("list")
    
    def _show_tab(self, tab_name: str):
        """Switch between tabs."""
        # Hide all frames
        self.list_frame.pack_forget()
        self.graph_frame.pack_forget()
        self.detail_frame.pack_forget()
        
        # Update button colors
        self.list_tab_btn.configure(fg_color="#1565c0" if tab_name == "list" else "gray")
        self.graph_tab_btn.configure(fg_color="#1565c0" if tab_name == "graph" else "gray")
        self.detail_tab_btn.configure(fg_color="#1565c0" if tab_name == "detail" else "gray")
        
        # Show selected frame
        if tab_name == "list":
            self.list_frame.pack(fill="both", expand=True)
            self._populate_list_view()
        elif tab_name == "graph":
            self.graph_frame.pack(fill="both", expand=True)
            self._populate_graph_view()
        elif tab_name == "detail":
            self.detail_frame.pack(fill="both", expand=True)
            self._populate_detail_view()
    
    def _load_chain_data(self):
        """Load chain data from database."""
        try:
            self.backward_chain = self.db.get_content_chain(self.node_id)
            self.current_node = self.db.get_content_node(self.node_id)
            self.child_nodes = self.db.get_node_children(self.node_id)
            
            # Update info label
            if self.current_node:
                node_type = self.current_node.get('node_type', 'Unknown')
                self.info_label.configure(
                    text=f"Node {self.node_id} | Type: {node_type} | "
                         f"Chain length: {len(self.backward_chain)} | "
                         f"Children: {len(self.child_nodes)}"
                )
        except Exception as e:
            print(f"Error loading chain data: {e}")
            self.info_label.configure(text=f"Error loading chain: {e}")
    
    def _populate_list_view(self):
        """Populate the list view with chain nodes."""
        # Clear existing content
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        
        if not self.backward_chain:
            self._show_error(self.list_frame, "No chain found for this node.")
            return
        
        # Show current node first (as the focus)
        self._add_list_node_card(self.current_node, is_current=True)
        
        # Show "came from" arrow if there are ancestors
        if len(self.backward_chain) > 1:
            arrow_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent", height=30)
            arrow_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(
                arrow_frame, 
                text="⬇️  Came from  ⬇️", 
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="orange"
            ).pack()
        
        # Show ancestors in reverse order (oldest to newest, excluding current)
        for node in reversed(self.backward_chain[:-1]):
            self._add_list_node_card(node, is_current=False)
            if node != self.backward_chain[0]:
                arrow = ctk.CTkLabel(self.list_frame, text="↓", font=ctk.CTkFont(size=10))
                arrow.pack(pady=2)
        
        # Show children if any
        if self.child_nodes:
            arrow_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent", height=30)
            arrow_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(
                arrow_frame, 
                text="⬇️  Led to  ⬇️", 
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="green"
            ).pack()
            
            for i, child in enumerate(self.child_nodes):
                child_node = self.db.get_content_node(child['id'])
                if child_node:
                    self._add_list_node_card(child_node, is_current=False)
                    if i < len(self.child_nodes) - 1:
                        arrow = ctk.CTkLabel(self.list_frame, text="↓", font=ctk.CTkFont(size=10))
                        arrow.pack(pady=2)
    
    def _add_list_node_card(self, node: Dict, is_current: bool = False):
        """Add a visual card for a node in list view."""
        card = ctk.CTkFrame(
            self.list_frame,
            corner_radius=10,
            border_width=2 if is_current else 1,
            border_color="#4caf50" if is_current else "gray"
        )
        card.pack(fill="x", pady=5, padx=5)
        
        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 5))
        
        icon = self.NODE_ICONS.get(node.get('node_type', ''), '📌')
        node_type_display = node.get('node_type', 'Unknown').replace('_', ' ').title()
        
        # Current badge
        if is_current:
            ctk.CTkLabel(
                header,
                text="★ CURRENT ★",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#4caf50"
            ).pack(side="left")
        
        ctk.CTkLabel(
            header,
            text=f"{icon} {node_type_display}",
            font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=(15 if is_current else 0, 0))
        
        # Timestamp
        time_str = datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        ctk.CTkLabel(
            header,
            text=time_str,
            text_color="gray",
            font=ctk.CTkFont(size=10)
        ).pack(side="right")
        
        # Title
        if node.get('title'):
            ctk.CTkLabel(
                card,
                text=f"📌 {node['title']}",
                font=ctk.CTkFont(weight="bold", size=13),
                wraplength=700,
                justify="left"
            ).pack(anchor="w", padx=12, pady=(0, 5))
        
        # Content preview
        content = node.get('content', '')
        if content:
            preview = content[:200] + "..." if len(content) > 200 else content
            content_frame = ctk.CTkFrame(card, fg_color=("gray95", "gray18"), corner_radius=6)
            content_frame.pack(fill="x", padx=12, pady=(0, 8))
            
            ctk.CTkLabel(
                content_frame,
                text=preview,
                wraplength=750,
                justify="left",
                font=ctk.CTkFont(size=12)
            ).pack(padx=10, pady=8)
        
        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 8))
        
        # View Details button
        def view_details(nid=node['id']):
            self._show_node_detail_panel(nid)
        
        ctk.CTkButton(
            btn_frame,
            text="View Details",
            width=100,
            height=28,
            command=view_details
        ).pack(side="left", padx=2)
        
        # Jump button (if not current)
        if not is_current:
            def jump(nid=node['id']):
                self.node_id = nid
                self._load_chain_data()
                self._populate_list_view()
            
            ctk.CTkButton(
                btn_frame,
                text="Jump to This Node",
                width=120,
                height=28,
                fg_color="#ff9800",
                command=jump
            ).pack(side="left", padx=2)
        
        # View Chain button
        def view_chain(nid=node['id']):
            self._open_chain_for_node(nid)
        
        ctk.CTkButton(
            btn_frame,
            text="View Chain",
            width=100,
            height=28,
            fg_color="#1565c0",
            command=view_chain
        ).pack(side="left", padx=2)
        
        # Child count
        child_count = self.db.get_node_children(node['id'])
        if child_count:
            ctk.CTkLabel(
                btn_frame,
                text=f"↳ {len(child_count)} children",
                text_color="gray",
                font=ctk.CTkFont(size=10)
            ).pack(side="right", padx=5)
    
    def _populate_graph_view(self):
        """Populate the graph visualization."""
        for widget in self.graph_frame.winfo_children():
            widget.destroy()
        
        if not self.backward_chain and not self.child_nodes:
            self._show_error(self.graph_frame, "No chain data for graph view.")
            return
        
        # Create canvas for graph
        self.graph_canvas = ctk.CTkCanvas(
            self.graph_frame,
            bg='#1e1e1e',
            highlightthickness=0
        )
        self.graph_canvas.pack(fill="both", expand=True)
        
        # Build graph nodes
        self.graph_nodes = []
        self.graph_edges = []
        
        # Add all chain nodes
        y_offset = 50
        x_center = 400
        
        # Positions: ancestors at top, current in middle, children at bottom
        ancestor_count = len(self.backward_chain) - 1 if self.backward_chain else 0
        child_count = len(self.child_nodes)
        
        # Calculate positions
        for i, node in enumerate(self.backward_chain):
            is_cur = node['id'] == self.node_id
            y = y_offset + i * 100
            self.graph_nodes.append({
                'id': node['id'],
                'type': node['node_type'],
                'title': node.get('title', node['content'][:30] if node.get('content') else 'Untitled'),
                'x': x_center,
                'y': y,
                'is_current': is_cur
            })
        
        # Add children below
        start_y = y_offset + len(self.backward_chain) * 100 + 50
        for i, child in enumerate(self.child_nodes):
            child_node = self.db.get_content_node(child['id'])
            if child_node:
                # Spread children horizontally
                x_offset = (i - child_count / 2) * 150
                self.graph_nodes.append({
                    'id': child_node['id'],
                    'type': child_node['node_type'],
                    'title': child_node.get('title', child_node['content'][:30] if child_node.get('content') else 'Untitled'),
                    'x': x_center + x_offset,
                    'y': start_y + (i // 3) * 100,
                    'is_current': False
                })
        
        # Create edges between connected nodes
        for i in range(len(self.graph_nodes) - 1):
            self.graph_edges.append((self.graph_nodes[i]['id'], self.graph_nodes[i+1]['id']))
        
        # Add parent-child edges for children
        for child_node in self.graph_nodes:
            if child_node['y'] > y_offset + len(self.backward_chain) * 100:
                self.graph_edges.append((self.node_id, child_node['id']))
        
        # Draw the graph
        self._draw_graph()
        
        # Add zoom controls
        control_frame = ctk.CTkFrame(self.graph_frame, fg_color="transparent")
        control_frame.place(relx=0.95, rely=0.05, anchor="ne")
        
        ctk.CTkButton(
            control_frame, text="+", width=30, height=30,
            command=self._zoom_in
        ).pack(pady=2)
        
        ctk.CTkButton(
            control_frame, text="-", width=30, height=30,
            command=self._zoom_out
        ).pack(pady=2)
        
        ctk.CTkButton(
            control_frame, text="⟳", width=30, height=30,
            command=self._reset_view
        ).pack(pady=2)
        
        # Bind mouse events for panning
        self.graph_canvas.bind("<ButtonPress-1>", self._start_pan)
        self.graph_canvas.bind("<B1-Motion>", self._do_pan)
        self.graph_canvas.bind("<MouseWheel>", self._on_mousewheel)
    
    def _draw_graph(self):
        """Draw the graph on canvas with current zoom/pan."""
        self.graph_canvas.delete("all")
        
        # Calculate visible area
        width = self.graph_canvas.winfo_width() if self.graph_canvas.winfo_width() > 100 else 800
        height = self.graph_canvas.winfo_height() if self.graph_canvas.winfo_height() > 100 else 600
        
        # Draw edges first (so they appear behind nodes)
        for from_id, to_id in self.graph_edges:
            from_node = next((n for n in self.graph_nodes if n['id'] == from_id), None)
            to_node = next((n for n in self.graph_nodes if n['id'] == to_id), None)
            
            if from_node and to_node:
                x1 = from_node['x'] * self.zoom + self.offset_x
                y1 = from_node['y'] * self.zoom + self.offset_y
                x2 = to_node['x'] * self.zoom + self.offset_x
                y2 = to_node['y'] * self.zoom + self.offset_y
                
                self.graph_canvas.create_line(
                    x1, y1, x2, y2,
                    fill="#555555", width=2,
                    arrow="last", arrowshape=(8, 10, 5)
                )
        
        # Draw nodes
        for node in self.graph_nodes:
            x = node['x'] * self.zoom + self.offset_x
            y = node['y'] * self.zoom + self.offset_y
            radius = 30 * self.zoom
            
            # Node color based on type
            node_type = node.get('type', 'default')
            color = self.NODE_COLORS.get(node_type, self.NODE_COLORS['default'])
            if node.get('is_current'):
                color = "#4caf50"  # Highlight current node
            
            # Draw circle
            self.graph_canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=color, outline="white", width=2
            )
            
            # Draw icon
            icon = self.NODE_ICONS.get(node_type, '📌')
            self.graph_canvas.create_text(
                x, y - 5,
                text=icon, font=("Segoe UI Emoji", int(16 * self.zoom))
            )
            
            # Draw title below
            title = node['title'][:15] if node['title'] else node_type[:10]
            self.graph_canvas.create_text(
                x, y + radius + 5,
                text=title, fill="white",
                font=("Arial", int(10 * self.zoom)),
                anchor="n"
            )
            
            # Bind click event using tags
            tag = f"node_{node['id']}"
            self.graph_canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill="", outline="", tags=(tag,)
            )
            self.graph_canvas.tag_bind(tag, "<Button-1>", lambda e, nid=node['id']: self._on_graph_node_click(nid))
    
    def _on_graph_node_click(self, node_id: int):
        """Handle click on graph node."""
        self.node_id = node_id
        self._load_chain_data()
        self._populate_graph_view()
        self._populate_detail_view()
    
    def _start_pan(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def _do_pan(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.offset_x += dx
        self.offset_y += dy
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self._draw_graph()
    
    def _on_mousewheel(self, event):
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()
    
    def _zoom_in(self):
        self.zoom *= 1.1
        self._draw_graph()
    
    def _zoom_out(self):
        self.zoom /= 1.1
        self._draw_graph()
    
    def _reset_view(self):
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._draw_graph()
    
    def _populate_detail_view(self):
        """Populate the node detail panel."""
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
        
        if not self.current_node:
            self._show_error(self.detail_frame, "No node selected.")
            return
        
        node = self.current_node
        
        # Header
        header_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
        header_frame.pack(fill="x", pady=5, padx=5)
        
        icon = self.NODE_ICONS.get(node.get('node_type', ''), '📌')
        node_type_display = node.get('node_type', 'Unknown').replace('_', ' ').title()
        
        ctk.CTkLabel(
            header_frame,
            text=f"{icon} {node_type_display}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        # ID and timestamp
        time_str = datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        ctk.CTkLabel(
            header_frame,
            text=f"ID: {node['id']} | Created: {time_str}",
            text_color="gray",
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=15, pady=(0, 5))
        
        # Session info
        if node.get('session_id'):
            ctk.CTkLabel(
                header_frame,
                text=f"Session: {node['session_id']}",
                text_color="gray",
                font=ctk.CTkFont(size=11)
            ).pack(anchor="w", padx=15, pady=(0, 5))
        
        # Title section
        if node.get('title'):
            title_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
            title_frame.pack(fill="x", pady=5, padx=5)
            
            ctk.CTkLabel(
                title_frame,
                text="📌 Title",
                font=ctk.CTkFont(weight="bold", size=14)
            ).pack(anchor="w", padx=15, pady=(10, 0))
            
            ctk.CTkLabel(
                title_frame,
                text=node['title'],
                wraplength=700,
                justify="left",
                font=ctk.CTkFont(size=13, weight="bold")
            ).pack(anchor="w", padx=15, pady=(5, 10))
        
        # Content section
        content_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
        content_frame.pack(fill="both", expand=True, pady=5, padx=5)
        
        ctk.CTkLabel(
            content_frame,
            text="📝 Content",
            font=ctk.CTkFont(weight="bold", size=14)
        ).pack(anchor="w", padx=15, pady=(10, 0))
        
        content_text = ctk.CTkTextbox(content_frame, wrap="word", font=("Consolas", 12), height=150)
        content_text.insert("1.0", node.get('content', 'No content'))
        content_text.configure(state="disabled")
        content_text.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        
        # Metadata section
        metadata = node.get('metadata', {})
        if metadata and isinstance(metadata, dict):
            meta_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
            meta_frame.pack(fill="x", pady=5, padx=5)
            
            ctk.CTkLabel(
                meta_frame,
                text="ℹ️ Metadata",
                font=ctk.CTkFont(weight="bold", size=14)
            ).pack(anchor="w", padx=15, pady=(10, 0))
            
            for key, value in list(metadata.items())[:5]:
                ctk.CTkLabel(
                    meta_frame,
                    text=f"{key}: {value}",
                    text_color="gray",
                    font=ctk.CTkFont(size=11)
                ).pack(anchor="w", padx=15, pady=2)
        
        # Connected words section
        content = node.get('content', '')
        if content:
            import re
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', content)
            if chinese_words:
                words_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
                words_frame.pack(fill="x", pady=5, padx=5)
                
                ctk.CTkLabel(
                    words_frame,
                    text="🔗 Chinese Words Found",
                    font=ctk.CTkFont(weight="bold", size=14)
                ).pack(anchor="w", padx=15, pady=(10, 0))
                
                word_container = ctk.CTkFrame(words_frame, fg_color="transparent")
                word_container.pack(fill="x", padx=15, pady=(5, 10))
                
                for word in chinese_words[:10]:
                    word_btn = ctk.CTkButton(
                        word_container,
                        text=word,
                        width=80,
                        height=30,
                        fg_color="#4a4a4a",
                        command=lambda w=word: self._lookup_word(w)
                    )
                    word_btn.pack(side="left", padx=3, pady=3)
        
        # Parent/Child info
        parent = self.db.get_node_parent(node['id']) if node.get('parent_id') else None
        children = self.db.get_node_children(node['id'])
        
        info_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
        info_frame.pack(fill="x", pady=5, padx=5)
        
        ctk.CTkLabel(
            info_frame,
            text="🔗 Connections",
            font=ctk.CTkFont(weight="bold", size=14)
        ).pack(anchor="w", padx=15, pady=(10, 0))
        
        if parent:
            ctk.CTkLabel(
                info_frame,
                text=f"Parent: {parent['node_type']} (ID: {parent['id']})",
                text_color="orange"
            ).pack(anchor="w", padx=15, pady=2)
        
        if children:
            ctk.CTkLabel(
                info_frame,
                text=f"Children: {len(children)}",
                text_color="green"
            ).pack(anchor="w", padx=15, pady=2)
        
        ctk.CTkLabel(
            info_frame,
            text=f"Position in chain: {len(self.backward_chain)} nodes total",
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(2, 10))
        
        # Action buttons
        btn_frame = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10, padx=5)
        
        if node['node_type'] == 'word_lookup':
            ctk.CTkButton(
                btn_frame,
                text="📚 Review Word",
                fg_color="green",
                command=lambda: self._review_word(node.get('title', node.get('content', '')[:20]))
            ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="📋 Copy Content",
            command=lambda: self._copy_content(node.get('content', ''))
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="🔗 View Full Chain",
            fg_color="#1565c0",
            command=lambda nid=node['id']: self._open_chain_for_node(nid)
        ).pack(side="left", padx=5)
    
    def _show_node_detail_panel(self, node_id: int):
        """Show detailed panel for a node in a popup."""
        node = self.db.get_content_node(node_id)
        if not node:
            return
        
        detail_popup = ctk.CTkToplevel(self)
        detail_popup.geometry("650x550")
        detail_popup.title(f"Node Details: {node.get('title', node_id)}")
        detail_popup.attributes("-topmost", True)
        
        # Main frame
        main_frame = ctk.CTkFrame(detail_popup, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header
        icon = self.NODE_ICONS.get(node.get('node_type', ''), '📌')
        ctk.CTkLabel(
            main_frame,
            text=f"{icon} {node.get('node_type', 'Unknown').upper()}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")
        
        time_str = datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        ctk.CTkLabel(
            main_frame,
            text=f"ID: {node['id']} | Created: {time_str}",
            text_color="gray"
        ).pack(anchor="w", pady=(0, 10))
        
        # Title
        if node.get('title'):
            ctk.CTkLabel(
                main_frame,
                text=f"📌 {node['title']}",
                font=ctk.CTkFont(weight="bold", size=14)
            ).pack(anchor="w")
        
        # Content
        ctk.CTkLabel(
            main_frame,
            text="Content:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", pady=(10, 0))
        
        content_box = ctk.CTkTextbox(main_frame, wrap="word", font=("Consolas", 11), height=200)
        content_box.insert("1.0", node.get('content', 'No content'))
        content_box.configure(state="disabled")
        content_box.pack(fill="both", expand=True, pady=5)
        
        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="View Chain",
            command=lambda: self._open_chain_for_node(node_id)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="Close",
            command=detail_popup.destroy
        ).pack(side="right", padx=5)
    
    def _open_chain_for_node(self, node_id: int):
        """Open chain viewer for another node."""
        new_viewer = ChainViewer(self._parent_ref, self.db, node_id, f"Learning Chain - Node {node_id}")
        new_viewer.focus()
    
    def _lookup_word(self, word: str):
        """Trigger word lookup."""
        self.info_label.configure(text=f"Looking up: {word}")
        # This could be extended to call the main app's lookup function
    
    def _review_word(self, word: str):
        """Review a word."""
        self.info_label.configure(text=f"Reviewing word: {word}")
    
    def _copy_content(self, content: str):
        """Copy content to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(content)
        self.info_label.configure(text="Copied to clipboard!")
    
    def _show_error(self, parent, message: str):
        """Show error message in a frame."""
        error_label = ctk.CTkLabel(
            parent,
            text=f"❌ {message}",
            text_color="red",
            font=ctk.CTkFont(size=14)
        )
        error_label.pack(pady=20)
    
    def focus(self):
        """Bring window to front."""
        self.lift()
        self.focus_force()