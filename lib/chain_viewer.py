"""
Chain Viewer - Displays learning content hierarchy.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Dict, List, Optional
from lib.db import VocabDatabase


class ChainViewer(ctk.CTkToplevel):
    """Popup window displaying learning chain for any node."""
    
    NODE_ICONS = {
        'raw_text': '📄',
        'sentence': '📖',
        'query': '❓',
        'response': '💬',
        'word': '🔍',
        'explanation': '✨',
        'session': '📚',
        'analysis': '🔬'
    }
    
    NODE_COLORS = {
        'query': '#2e7d32',
        'response': '#1565c0',
        'word': '#e65100',
        'sentence': '#6a1b9a',
        'raw_text': '#795548',
        'session': '#37474f',
        'default': '#555555'
    }
    
    def __init__(self, parent, db: VocabDatabase, node_id: int, title: str = "Learning Chain"):
        super().__init__(parent)
        self.db = db
        self.node_id = node_id
        self.title(title)
        self.geometry("900x700")
        self.attributes("-topmost", True)
        
        self._parent_ref = parent
        self.chain_nodes = []
        self.current_node = None
        self.child_nodes = []
        
        # Graph state
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        """Create UI components."""
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tabs
        tab_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        tab_frame.pack(fill="x", pady=(0, 10))
        
        self.list_btn = ctk.CTkButton(tab_frame, text="📋 List View", width=120,
                                      command=lambda: self._show_tab("list"), fg_color="#1565c0")
        self.list_btn.pack(side="left", padx=5)
        
        self.graph_btn = ctk.CTkButton(tab_frame, text="🔗 Graph View", width=120,
                                       command=lambda: self._show_tab("graph"), fg_color="gray")
        self.graph_btn.pack(side="left", padx=5)
        
        self.detail_btn = ctk.CTkButton(tab_frame, text="📊 Node Details", width=120,
                                        command=lambda: self._show_tab("detail"), fg_color="gray")
        self.detail_btn.pack(side="left", padx=5)
        
        # Info label
        self.info_label = ctk.CTkLabel(self.main_frame, text="", text_color="gray", font=ctk.CTkFont(size=11))
        self.info_label.pack(pady=(0, 5))
        
        # Content area
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        
        self.list_frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.graph_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.detail_frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        
        self._show_tab("list")
    
    def _show_tab(self, tab_name: str):
        """Switch between tabs."""
        self.list_frame.pack_forget()
        self.graph_frame.pack_forget()
        self.detail_frame.pack_forget()
        
        self.list_btn.configure(fg_color="#1565c0" if tab_name == "list" else "gray")
        self.graph_btn.configure(fg_color="#1565c0" if tab_name == "graph" else "gray")
        self.detail_btn.configure(fg_color="#1565c0" if tab_name == "detail" else "gray")
        
        if tab_name == "list":
            self.list_frame.pack(fill="both", expand=True)
            self._populate_list()
        elif tab_name == "graph":
            self.graph_frame.pack(fill="both", expand=True)
            self._populate_graph()
        elif tab_name == "detail":
            self.detail_frame.pack(fill="both", expand=True)
            self._populate_detail()
    
    def _load_data(self):
        """Load node data from database."""
        try:
            self.chain_nodes = self.db.get_chain(self.node_id)
            self.current_node = self.db.get_node(self.node_id)
            self.child_nodes = self.db.get_children(self.node_id)
            
            if self.current_node:
                self.info_label.configure(
                    text=f"Node {self.node_id} | Type: {self.current_node.get('node_type', 'Unknown')} | "
                         f"Chain: {len(self.chain_nodes)} | Children: {len(self.child_nodes)}"
                )
        except Exception as e:
            self.info_label.configure(text=f"Error: {e}")
    
    def _populate_list(self):
        """Populate list view."""
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        
        if not self.chain_nodes:
            self._show_error(self.list_frame, "No chain found.")
            return
        
        # Show current node
        self._add_node_card(self.current_node, is_current=True)
        
        # Show ancestors
        if len(self.chain_nodes) > 1:
            arrow = ctk.CTkLabel(self.list_frame, text="⬇️ Came from ⬇️", text_color="orange")
            arrow.pack(pady=5)
        
        for node in reversed(self.chain_nodes[:-1]):
            self._add_node_card(node, is_current=False)
        
        # Show children
        if self.child_nodes:
            arrow = ctk.CTkLabel(self.list_frame, text="⬇️ Led to ⬇️", text_color="green")
            arrow.pack(pady=5)
            
            for child in self.child_nodes:
                child_node = self.db.get_node(child['id'])
                if child_node:
                    self._add_node_card(child_node, is_current=False)
    
    def _add_node_card(self, node: Dict, is_current: bool = False):
        """Add a node card to list view."""
        card = ctk.CTkFrame(self.list_frame, corner_radius=10,
                           border_width=2 if is_current else 1,
                           border_color="#4caf50" if is_current else "gray")
        card.pack(fill="x", pady=5, padx=5)
        
        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 5))
        
        icon = self.NODE_ICONS.get(node.get('node_type', ''), '📌')
        type_display = node.get('node_type', 'Unknown').replace('_', ' ').title()
        
        if is_current:
            ctk.CTkLabel(header, text="★ CURRENT ★", font=ctk.CTkFont(size=11, weight="bold"),
                        text_color="#4caf50").pack(side="left")
        
        ctk.CTkLabel(header, text=f"{icon} {type_display}", font=ctk.CTkFont(weight="bold")
                    ).pack(side="left", padx=(15 if is_current else 0, 0))
        
        time_str = datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        ctk.CTkLabel(header, text=time_str, text_color="gray", font=ctk.CTkFont(size=10)).pack(side="right")
        
        # Title
        if node.get('title'):
            ctk.CTkLabel(card, text=f"📌 {node['title']}", font=ctk.CTkFont(weight="bold", size=13),
                        wraplength=700).pack(anchor="w", padx=12, pady=(0, 5))
        
        # Content preview
        content = node.get('content', '')
        if content:
            preview = content[:200] + "..." if len(content) > 200 else content
            content_frame = ctk.CTkFrame(card, fg_color=("gray95", "gray18"), corner_radius=6)
            content_frame.pack(fill="x", padx=12, pady=(0, 8))
            ctk.CTkLabel(content_frame, text=preview, wraplength=750, justify="left").pack(padx=10, pady=8)
        
        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 8))
        
        def view_chain(nid=node['id']):
            ChainViewer(self._parent_ref, self.db, nid, f"Chain - Node {nid}").focus()
        
        ctk.CTkButton(btn_frame, text="View Chain", width=100, height=28, command=view_chain).pack(side="left", padx=2)
        
        if not is_current:
            def jump(nid=node['id']):
                self.node_id = nid
                self._load_data()
                self._populate_list()
            
            ctk.CTkButton(btn_frame, text="Jump to Node", width=100, height=28,
                         fg_color="#ff9800", command=jump).pack(side="left", padx=2)
    
    def _populate_graph(self):
        """Populate graph visualization."""
        for widget in self.graph_frame.winfo_children():
            widget.destroy()
        
        if not self.chain_nodes and not self.child_nodes:
            self._show_error(self.graph_frame, "No data for graph view.")
            return
        
        self.graph_canvas = ctk.CTkCanvas(self.graph_frame, bg='#1e1e1e', highlightthickness=0)
        self.graph_canvas.pack(fill="both", expand=True)
        
        self._draw_graph()
        
        # Controls
        control_frame = ctk.CTkFrame(self.graph_frame, fg_color="transparent")
        control_frame.place(relx=0.95, rely=0.05, anchor="ne")
        
        for text, cmd in [("+", self._zoom_in), ("-", self._zoom_out), ("⟳", self._reset_view)]:
            ctk.CTkButton(control_frame, text=text, width=30, height=30, command=cmd).pack(pady=2)
        
        # Bind events
        self.graph_canvas.bind("<ButtonPress-1>", self._start_pan)
        self.graph_canvas.bind("<B1-Motion>", self._do_pan)
        self.graph_canvas.bind("<MouseWheel>", lambda e: self._zoom_in() if e.delta > 0 else self._zoom_out())
    
    def _draw_graph(self):
        """Draw graph with current zoom/pan."""
        self.graph_canvas.delete("all")
        
        # Build nodes and edges
        nodes = []
        y_base = 100
        x_center = 400
        
        for i, node in enumerate(self.chain_nodes):
            nodes.append({
                'id': node['id'],
                'type': node['node_type'],
                'title': node.get('title', node['content'][:20] if node.get('content') else '?'),
                'x': x_center,
                'y': y_base + i * 100,
                'is_current': node['id'] == self.node_id
            })
        
        # Draw edges
        for i in range(len(nodes) - 1):
            n1, n2 = nodes[i], nodes[i+1]
            x1 = n1['x'] * self.zoom + self.offset_x
            y1 = n1['y'] * self.zoom + self.offset_y
            x2 = n2['x'] * self.zoom + self.offset_x
            y2 = n2['y'] * self.zoom + self.offset_y
            self.graph_canvas.create_line(x1, y1, x2, y2, fill="#555", width=2, arrow="last")
        
        # Draw nodes
        for node in nodes:
            x = node['x'] * self.zoom + self.offset_x
            y = node['y'] * self.zoom + self.offset_y
            radius = 30 * self.zoom
            
            color = self.NODE_COLORS.get(node['type'], self.NODE_COLORS['default'])
            if node.get('is_current'):
                color = "#4caf50"
            
            self.graph_canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                         fill=color, outline="white", width=2)
            
            icon = self.NODE_ICONS.get(node['type'], '📌')
            self.graph_canvas.create_text(x, y - 5, text=icon, font=("Segoe UI Emoji", int(16 * self.zoom)))
            
            title = node['title'][:12] if node['title'] else node['type'][:8]
            self.graph_canvas.create_text(x, y + radius + 5, text=title, fill="white",
                                         font=("Arial", int(9 * self.zoom)), anchor="n")
            
            tag = f"node_{node['id']}"
            self.graph_canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                         fill="", outline="", tags=(tag,))
            self.graph_canvas.tag_bind(tag, "<Button-1>", lambda e, nid=node['id']: self._on_node_click(nid))
    
    def _on_node_click(self, node_id: int):
        """Handle graph node click."""
        self.node_id = node_id
        self._load_data()
        self._populate_graph()
        self._populate_detail()
    
    def _start_pan(self, e):
        self.drag_start_x = e.x
        self.drag_start_y = e.y
    
    def _do_pan(self, e):
        self.offset_x += e.x - self.drag_start_x
        self.offset_y += e.y - self.drag_start_y
        self.drag_start_x = e.x
        self.drag_start_y = e.y
        self._draw_graph()
    
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
    
    def _populate_detail(self):
        """Populate detail view."""
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
        
        if not self.current_node:
            self._show_error(self.detail_frame, "No node selected.")
            return
        
        node = self.current_node
        
        # Header
        header = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
        header.pack(fill="x", pady=5, padx=5)
        
        icon = self.NODE_ICONS.get(node.get('node_type', ''), '📌')
        type_display = node.get('node_type', 'Unknown').replace('_', ' ').title()
        
        ctk.CTkLabel(header, text=f"{icon} {type_display}", font=ctk.CTkFont(size=18, weight="bold")
                    ).pack(anchor="w", padx=15, pady=(10, 5))
        
        time_str = datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        ctk.CTkLabel(header, text=f"ID: {node['id']} | Created: {time_str}",
                    text_color="gray").pack(anchor="w", padx=15, pady=(0, 5))
        
        # Title
        if node.get('title'):
            title_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
            title_frame.pack(fill="x", pady=5, padx=5)
            ctk.CTkLabel(title_frame, text="📌 Title", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(10, 0))
            ctk.CTkLabel(title_frame, text=node['title'], wraplength=700).pack(anchor="w", padx=15, pady=(5, 10))
        
        # Content
        content_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
        content_frame.pack(fill="both", expand=True, pady=5, padx=5)
        
        ctk.CTkLabel(content_frame, text="📝 Content", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(10, 0))
        
        content_box = ctk.CTkTextbox(content_frame, wrap="word", height=150)
        content_box.insert("1.0", node.get('content', 'No content'))
        content_box.configure(state="disabled")
        content_box.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        
        # Translation
        if node.get('translation'):
            trans_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
            trans_frame.pack(fill="x", pady=5, padx=5)
            ctk.CTkLabel(trans_frame, text="🌐 Translation", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(10, 0))
            ctk.CTkLabel(trans_frame, text=node['translation'], wraplength=700).pack(anchor="w", padx=15, pady=(5, 10))
        
        # Parent/Child info
        parent = self.db.get_parent(node['id'])
        children = self.db.get_children(node['id'])
        
        info_frame = ctk.CTkFrame(self.detail_frame, fg_color=("gray90", "gray20"), corner_radius=10)
        info_frame.pack(fill="x", pady=5, padx=5)
        
        ctk.CTkLabel(info_frame, text="🔗 Connections", font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(10, 0))
        
        if parent:
            ctk.CTkLabel(info_frame, text=f"Parent: {parent['node_type']} (ID: {parent['id']})",
                        text_color="orange").pack(anchor="w", padx=15, pady=2)
        
        if children:
            ctk.CTkLabel(info_frame, text=f"Children: {len(children)}",
                        text_color="green").pack(anchor="w", padx=15, pady=2)
        
        # Action buttons
        btn_frame = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10, padx=5)
        
        def copy_content():
            self.clipboard_clear()
            self.clipboard_append(node.get('content', ''))
            self.info_label.configure(text="Copied!")
        
        ctk.CTkButton(btn_frame, text="📋 Copy", command=copy_content).pack(side="left", padx=5)
        
        def view_full_chain():
            ChainViewer(self._parent_ref, self.db, node['id'], f"Chain - {node.get('title', node['id'])}").focus()
        
        ctk.CTkButton(btn_frame, text="🔗 Full Chain", fg_color="#1565c0", command=view_full_chain).pack(side="left", padx=5)
    
    def _show_error(self, parent, message: str):
        ctk.CTkLabel(parent, text=f"❌ {message}", text_color="red").pack(pady=20)
    
    def focus(self):
        self.lift()
        self.focus_force()