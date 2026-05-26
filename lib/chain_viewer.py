"""
Simplified chain viewer for learning content hierarchy.
Displays clickable chain of related content with clean visual design.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Dict, List, Optional


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
        'default': '#37474f'      # gray
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
        self.geometry("750x600")
        self.attributes("-topmost", True)
        
        # Setup UI
        self._setup_ui()
        self._load_and_display_chain()
    
    def _setup_ui(self):
        """Create the UI components."""
        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header_frame,
            text="🔗 Content Learning Chain",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left")
        
        # Node info label
        self.info_label = ctk.CTkLabel(
            header_frame,
            text="",
            text_color="gray",
            font=ctk.CTkFont(size=11)
        )
        self.info_label.pack(side="right")
        
        # Scrollable area for chain
        self.chain_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.chain_frame.pack(fill="both", expand=True)
        
        # Bottom buttons
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkButton(
            button_frame,
            text="View Subtree",
            command=self._show_subtree
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="Export Chain",
            command=self._export_chain
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="Close",
            command=self.destroy
        ).pack(side="right", padx=5)
    
    def _load_and_display_chain(self):
        """Load chain from database and display it."""
        # Clear existing content
        for widget in self.chain_frame.winfo_children():
            widget.destroy()
        
        # Get the chain (oldest to newest)
        chain = self.db.get_content_chain(self.node_id)
        
        if not chain:
            self._show_error("No chain found for this node.")
            return
        
        # Update info label
        self.info_label.configure(
            text=f"Node {self.node_id} | Chain length: {len(chain)}"
        )
        
        # Display each node in the chain
        for i, node in enumerate(chain):
            is_current = (node['id'] == self.node_id)
            self._add_node_card(node, i, len(chain), is_current)
    
    def _add_node_card(self, node: Dict, index: int, total: int, is_current: bool):
        """
        Add a visual card for a node in the chain.
        
        Args:
            node: Node dictionary from database
            index: Position in chain (0 = oldest)
            total: Total number of nodes
            is_current: Whether this is the node we started from
        """
        # Create card frame
        card = ctk.CTkFrame(
            self.chain_frame,
            corner_radius=10,
            border_width=2 if is_current else 1,
            border_color="#4caf50" if is_current else "gray"
        )
        card.pack(fill="x", pady=8, padx=5)
        
        # Determine if this is the root (no parent) or leaf (no children)
        is_root = (index == 0)
        is_leaf = (index == total - 1)
        
        # Header with level indicator
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(8, 5))
        
        # Level badge (how deep in the chain)
        level = total - index - 1
        level_text = f"Level {level}" if level > 0 else "Current" if is_current else "Root"
        level_color = "#4caf50" if is_current else "#ff9800" if level == 0 else "gray"
        
        ctk.CTkLabel(
            header_frame,
            text=f"┌─ {level_text} ─┐" if not is_current else "★ CURRENT ★",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=level_color
        ).pack(side="left")
        
        # Node type with icon
        icon = self.NODE_ICONS.get(node['node_type'], '📌')
        node_type_display = node['node_type'].replace('_', ' ').title()
        
        ctk.CTkLabel(
            header_frame,
            text=f"{icon} {node_type_display}",
            font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=(15, 0))
        
        # Timestamp
        time_str = datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        ctk.CTkLabel(
            header_frame,
            text=time_str,
            text_color="gray",
            font=ctk.CTkFont(size=10)
        ).pack(side="right")
        
        # Title (if exists)
        if node.get('title'):
            title_frame = ctk.CTkFrame(card, fg_color="transparent")
            title_frame.pack(fill="x", padx=12, pady=(0, 5))
            
            ctk.CTkLabel(
                title_frame,
                text=f"📌 {node['title']}",
                font=ctk.CTkFont(weight="bold", size=13),
                wraplength=600,
                justify="left"
            ).pack(anchor="w")
        
        # Content preview (first 150 chars)
        content = node.get('content', '')
        if content:
            content_preview = content[:150] + "..." if len(content) > 150 else content
            content_frame = ctk.CTkFrame(card, fg_color=("gray95", "gray18"), corner_radius=6)
            content_frame.pack(fill="x", padx=12, pady=(0, 8))
            
            content_label = ctk.CTkLabel(
                content_frame,
                text=content_preview,
                wraplength=650,
                justify="left",
                font=ctk.CTkFont(size=12)
            )
            content_label.pack(padx=10, pady=8)
        
        # Metadata (if any)
        metadata = node.get('metadata', {})
        if metadata and isinstance(metadata, dict):
            meta_str = ", ".join([f"{k}: {v}" for k, v in list(metadata.items())[:3]])
            if meta_str:
                ctk.CTkLabel(
                    card,
                    text=f"ℹ️ {meta_str}",
                    text_color="gray",
                    font=ctk.CTkFont(size=10)
                ).pack(anchor="w", padx=12, pady=(0, 5))
        
        # Action buttons
        button_frame = ctk.CTkFrame(card, fg_color="transparent")
        button_frame.pack(fill="x", padx=12, pady=(0, 8))
        
        # View details button
        ctk.CTkButton(
            button_frame,
            text="View Details",
            width=100,
            height=28,
            command=lambda nid=node['id']: self._view_node_details(nid)
        ).pack(side="left", padx=2)
        
        # If not current, add "Jump to this node" button
        if not is_current:
            ctk.CTkButton(
                button_frame,
                text="Jump to This Node",
                width=120,
                height=28,
                fg_color="#ff9800",
                command=lambda nid=node['id']: self._refresh_for_node(nid)
            ).pack(side="left", padx=2)
        
        # If node has children, show count
        children = self.db.get_node_children(node['id'])
        if children:
            ctk.CTkLabel(
                button_frame,
                text=f"↳ {len(children)} child nodes",
                text_color="gray",
                font=ctk.CTkFont(size=10)
            ).pack(side="right", padx=5)
        
        # Add connector arrow (except for last/current node)
        if not is_leaf and not is_current:
            arrow_frame = ctk.CTkFrame(self.chain_frame, fg_color="transparent", height=20)
            arrow_frame.pack(fill="x", pady=2)
            
            # Visual arrow with context text
            arrow_text = "▼" if index < total - 2 else "▼ Triggered by click ▼"
            ctk.CTkLabel(
                arrow_frame,
                text=arrow_text,
                text_color="#ff9800",
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack()
    
    def _view_node_details(self, node_id: int):
        """Show detailed view of a node."""
        node = self.db.get_content_node(node_id)
        if not node:
            return
        
        # Create details popup
        details = ctk.CTkToplevel(self)
        details.title(f"Node Details - {node['node_type']}")
        details.geometry("600x500")
        details.attributes("-topmost", True)
        
        # Text widget for content
        text_box = ctk.CTkTextbox(details, wrap="word", font=("Consolas", 11))
        text_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Format details
        content = f"""
╔══════════════════════════════════════════════════════════╗
║ NODE DETAILS                                             ║
╚══════════════════════════════════════════════════════════╝

ID: {node['id']}
Type: {node['node_type']}
Created: {datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')}

Title: {node.get('title', 'N/A')}

Content:
{node.get('content', 'N/A')}

Metadata:
{node.get('metadata', {})}

Parent ID: {node.get('parent_id', 'None')}
Session: {node.get('session_id', 'N/A')}
        """
        
        text_box.insert("1.0", content)
        text_box.configure(state="disabled")
        
        # Add close button
        ctk.CTkButton(details, text="Close", command=details.destroy).pack(pady=10)
    
    def _refresh_for_node(self, node_id: int):
        """Refresh the viewer to show chain for a different node."""
        self.node_id = node_id
        self._load_and_display_chain()
    
    def _show_subtree(self):
        """Show the entire subtree from current node."""
        subtree = self.db.get_subtree(self.node_id)
        
        if not subtree:
            self._show_error("No subtree found.")
            return
        
        # Create subtree window
        subtree_win = ctk.CTkToplevel(self)
        subtree_win.title(f"Subtree from Node {self.node_id}")
        subtree_win.geometry("600x400")
        subtree_win.attributes("-topmost", True)
        
        # Text display
        text_box = ctk.CTkTextbox(subtree_win, wrap="word", font=("Consolas", 10))
        text_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Build tree text
        lines = [f"Subtree from Node {self.node_id} (Root)", "=" * 50]
        
        def render_tree(nodes, parent_id=None, indent=0):
            for node in nodes:
                if node['parent_id'] == parent_id:
                    prefix = "  " * indent + "├─ "
                    lines.append(f"{prefix}[{node['node_type'][:8]}] {node.get('title', 'Untitled')[:40]}")
                    render_tree(nodes, node['id'], indent + 1)
        
        render_tree(subtree)
        text_box.insert("1.0", "\n".join(lines))
        text_box.configure(state="disabled")
    
    def _export_chain(self):
        """Export chain to a text file."""
        from tkinter import filedialog
        
        chain = self.db.get_content_chain(self.node_id)
        if not chain:
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Learning Chain Export\n")
                f.write(f"Root Node: {self.node_id}\n")
                f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                
                for i, node in enumerate(chain):
                    f.write(f"Level {len(chain) - i - 1}\n")
                    f.write(f"  ID: {node['id']}\n")
                    f.write(f"  Type: {node['node_type']}\n")
                    f.write(f"  Time: {datetime.fromtimestamp(node['created_at']).strftime('%Y-%m-%d %H:%M:%S')}\n")
                    if node.get('title'):
                        f.write(f"  Title: {node['title']}\n")
                    if node.get('content'):
                        f.write(f"  Content: {node['content'][:200]}\n")
                    f.write("\n" + "-" * 40 + "\n\n")
            
            self._show_info(f"Exported to {file_path}")
    
    def _show_error(self, message: str):
        """Show error message."""
        error_label = ctk.CTkLabel(
            self.chain_frame,
            text=f"❌ {message}",
            text_color="red",
            font=ctk.CTkFont(size=14)
        )
        error_label.pack(pady=20)
    
    def _show_info(self, message: str):
        """Show info message."""
        from tkinter import messagebox
        messagebox.showinfo("Export Complete", message)
    
    def focus(self):
        """Bring window to front."""
        self.lift()
        self.focus_force()