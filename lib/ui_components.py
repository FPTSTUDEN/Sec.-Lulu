"""
Reusable UI components for the vocabulary learning app.
Provides base classes for cards, popups, and session management.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any


class BaseCard(ctk.CTkFrame):
    """Base card component for displaying any data."""
    
    def __init__(self, master, title: str = "", subtitle: str = "", 
                 icon: str = "📌", **kwargs):
        super().__init__(master, corner_radius=10, border_width=1, 
                        border_color="gray", **kwargs)
        
        self.title = title
        self.subtitle = subtitle
        self.icon = icon
        
        self._setup_header()
    
    def _setup_header(self):
        """Create card header."""
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=12, pady=(8, 5))
        
        # Icon and title
        title_text = f"{self.icon} {self.title}" if self.icon else self.title
        self.title_label = ctk.CTkLabel(self.header, text=title_text, 
                                        font=ctk.CTkFont(weight="bold"))
        self.title_label.pack(side="left")
        
        # Subtitle (right side)
        if self.subtitle:
            self.subtitle_label = ctk.CTkLabel(self.header, text=self.subtitle, 
                                               text_color="gray", 
                                               font=ctk.CTkFont(size=10))
            self.subtitle_label.pack(side="right")
    
    def add_content(self, content: str, wraplength: int = 700):
        """Add content area to card."""
        content_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray18"), 
                                     corner_radius=6)
        content_frame.pack(fill="x", padx=12, pady=(0, 8))
        
        self.content_label = ctk.CTkLabel(content_frame, text=content, 
                                          wraplength=wraplength, justify="left")
        self.content_label.pack(padx=10, pady=8)
        return content_frame
    
    def add_button_row(self, buttons: List[Dict[str, Any]]):
        """Add row of buttons.
        
        Args:
            buttons: List of dicts with keys: text, command, fg_color (optional)
        """
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 8))
        
        for btn in buttons:
            ctk.CTkButton(btn_frame, text=btn['text'], width=100, height=28,
                         fg_color=btn.get('fg_color', "#1565c0"),
                         command=btn['command']).pack(side="left", padx=2)


class ExpandableCard(BaseCard):
    """Card that can be expanded to show more content."""
    
    def __init__(self, master, title: str = "", subtitle: str = "", 
                 icon: str = "📌", preview: str = "", **kwargs):
        super().__init__(master, title, subtitle, icon, **kwargs)
        
        self.expanded = False
        self.expanded_widgets = []
        self.preview = preview
        
        # Add expand button to header
        self.expand_btn = ctk.CTkButton(self.header, text="▼", width=30, height=30,
                                        command=self._toggle_expand)
        self.expand_btn.pack(side="right", padx=(5, 0))
        
        # Preview label
        if preview:
            self.preview_label = ctk.CTkLabel(self, text=preview, wraplength=700,
                                              justify="left")
            self.preview_label.pack(anchor="w", padx=12, pady=(0, 5))
    
    def _toggle_expand(self):
        """Toggle expanded state."""
        self.expanded = not self.expanded
        
        if self.expanded:
            self._show_expanded_content()
            self.expand_btn.configure(text="▲")
        else:
            self._hide_expanded_content()
            self.expand_btn.configure(text="▼")
    
    def _show_expanded_content(self):
        """Show expanded content. Override in subclass."""
        for widget in self.expanded_widgets:
            widget.pack(fill="x", padx=12, pady=(5, 0))
    
    def _hide_expanded_content(self):
        """Hide expanded content."""
        for widget in self.expanded_widgets:
            widget.pack_forget()
    
    def add_expanded_section(self, title: str, content: str, 
                            text_color: str = None) -> ctk.CTkFrame:
        """Add a section to the expanded area."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        self.expanded_widgets.append(frame)
        
        title_label = ctk.CTkLabel(frame, text=title, 
                                   font=ctk.CTkFont(weight="bold"))
        title_label.pack(anchor="w")
        
        content_label = ctk.CTkLabel(frame, text=content, wraplength=650,
                                     justify="left", text_color=text_color)
        content_label.pack(anchor="w", padx=10)
        
        return frame


class SessionManager:
    """Reusable session management UI component."""
    
    def __init__(self, master, db, on_session_changed: Callable = None):
        self.master = master
        self.db = db
        self.on_session_changed = on_session_changed
        self.current_session_id = None
        
        self._setup_ui()
        self._refresh_status()
    
    def _setup_ui(self):
        """Create session UI controls."""
        self.frame = ctk.CTkFrame(self.master, fg_color="transparent")
        
        ctk.CTkLabel(self.frame, text="🎯 Session:").pack(side="left")
        
        self.session_var = ctk.StringVar(value="Auto")
        session_options = ["Auto", "Manhua", "Song", "News", "Conversation", "General"]
        self.session_menu = ctk.CTkOptionMenu(self.frame, values=session_options, 
                                               variable=self.session_var, width=90)
        self.session_menu.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(self.frame, text="", 
                                         font=ctk.CTkFont(size=10))
        self.status_label.pack(side="left", padx=5)
        
        self.new_btn = ctk.CTkButton(self.frame, text="📂", width=30, height=25,
                                     command=self._create_session)
        self.new_btn.pack(side="left", padx=2)
        
        self.end_btn = ctk.CTkButton(self.frame, text="⏹️", width=30, height=25,
                                     fg_color="orange", command=self._end_session)
        self.end_btn.pack(side="left", padx=2)
        
        self.history_btn = ctk.CTkButton(self.frame, text="📜", width=30, height=25,
                                         command=self._show_history)
        self.history_btn.pack(side="left", padx=2)
    
    def pack(self, **kwargs):
        """Pack the session manager frame."""
        self.frame.pack(**kwargs)
    
    def pack_forget(self):
        """Hide the session manager frame."""
        self.frame.pack_forget()
    
    def get_active_session_id(self) -> Optional[int]:
        """Get current active session ID."""
        if self.session_var.get() == "Auto":
            active = self.db.get_active_session()
            return active['id'] if active else None
        else:
            # Get or create session for this type
            active = self.db.get_active_session()
            if active and active.get('title', '').startswith(self.session_var.get()):
                return active['id']
            return None
    
    def get_or_create_session(self, title: str = None) -> int:
        """Get active session or create new one."""
        session_type = self.session_var.get()
        
        if session_type == "Auto":
            active = self.db.get_active_session()
            if active:
                return active['id']
            else:
                return self.db.create_session("General", title or "Auto-created")
        else:
            active = self.db.get_active_session()
            if active and active.get('title', '').startswith(session_type):
                return active['id']
            else:
                return self.db.create_session(session_type, title or session_type)
    
    def _refresh_status(self):
        """Update session status display."""
        active = self.db.get_active_session()
        if active:
            self.current_session_id = active['id']
            title = active.get('title', 'Session')
            self.status_label.configure(text=f"📚 {title[:30]}: {active.get('word_count', 0)} words", 
                                        text_color="green")
        else:
            self.current_session_id = None
            self.status_label.configure(text="No active session", text_color="gray")
        
        if self.on_session_changed:
            self.on_session_changed(self.current_session_id)
    
    def _create_session(self):
        """Create a new learning session."""
        popup = ctk.CTkToplevel(self.master)
        popup.geometry("300x250")
        popup.title("New Session")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Create New Learning Session", 
                     font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        ctk.CTkLabel(popup, text="Session Type:").pack(anchor="w", padx=20)
        type_var = ctk.StringVar(value="General")
        type_menu = ctk.CTkOptionMenu(popup, values=["Manhua", "Song", "News", "Conversation", "General"], 
                                       variable=type_var)
        type_menu.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(popup, text="Source Name (optional):").pack(anchor="w", padx=20)
        source_entry = ctk.CTkEntry(popup, placeholder_text="e.g., Legend of the Sword Ch3")
        source_entry.pack(fill="x", padx=20, pady=5)
        
        def create():
            source = source_entry.get().strip() or None
            session_id = self.db.create_session(type_var.get(), source)
            self.session_var.set(type_var.get())
            self._refresh_status()
            popup.destroy()
            
            from lib.windows import popup_message
            popup_message("Session Created", f"Session created!\nAdd words while studying to track them.", 
                         parent=self.master)
        
        ctk.CTkButton(popup, text="Create", command=create, fg_color="green").pack(pady=10)
    
    def _end_session(self):
        """End the current active session."""
        from lib.windows import popup_message
        
        active = self.db.get_active_session()
        if not active:
            popup_message("No Active Session", "No active session to end.", parent=self.master)
            return
        
        if popup_message("End Session", f"End session with {active.get('word_count', 0)} words?", 
                        is_yes_no=True, parent=self.master):
            self.current_session_id = None
            self._refresh_status()
            popup_message("Session Ended", f"Session ended.", parent=self.master)
    
    def _show_history(self):
        """Show session history popup."""
        from lib.windows import popup_message
        
        sessions = self.db.get_all_sessions()
        
        if not sessions:
            popup_message("Sessions", "No sessions recorded yet.", parent=self.master)
            return
        
        popup = ctk.CTkToplevel(self.master)
        popup.geometry("700x500")
        popup.title("Session History")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="📚 Your Learning Sessions", 
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        list_frame = ctk.CTkScrollableFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        for s in sessions:
            item_frame = ctk.CTkFrame(list_frame)
            item_frame.pack(fill="x", pady=3)
            
            date_str = datetime.fromtimestamp(s['created_at']).strftime('%m-%d %H:%M')
            title = s.get('title', 'Session')
            
            ctk.CTkLabel(item_frame, text="📚", font=ctk.CTkFont(weight="bold"), 
                        width=40).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=title[:40], width=200).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=f"{s.get('word_count', 0)} words", 
                        width=80).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=date_str, width=100, 
                        text_color="gray").pack(side="left", padx=5)
            
            def view(sid=s['id']):
                self._view_session_words(sid)
                popup.destroy()
            
            ctk.CTkButton(item_frame, text="View Words", width=80, command=view).pack(side="right", padx=5)
    
    def _view_session_words(self, session_id: int):
        """Show detailed view of a session with all words."""
        words = self.db.get_session_words(session_id)
        
        popup = ctk.CTkToplevel(self.master)
        popup.geometry("500x400")
        popup.title(f"Session Words")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=f"📚 Session Details", 
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        if words:
            list_frame = ctk.CTkScrollableFrame(popup)
            list_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            for w in words:
                word_frame = ctk.CTkFrame(list_frame)
                word_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(word_frame, text=w['content'], 
                            font=ctk.CTkFont(weight="bold"), width=100).pack(side="left", padx=5)
                ctk.CTkLabel(word_frame, text=w.get('translation', '')[:40], 
                            width=250).pack(side="left", padx=5)
        else:
            ctk.CTkLabel(popup, text="No words in this session yet.").pack(pady=20)


class PopupManager:
    """Unified popup manager for all dialog windows."""
    
    @staticmethod
    def show_info(parent, title: str, message: str):
        """Show info dialog."""
        from lib.windows import popup_message
        popup_message(title, message, parent=parent)
    
    @staticmethod
    def show_yes_no(parent, title: str, message: str, on_yes: Callable, on_no: Callable = None):
        """Show yes/no dialog."""
        from lib.windows import popup_message
        result = popup_message(title, message, is_yes_no=True, parent=parent)
        if result and on_yes:
            on_yes()
        elif not result and on_no:
            on_no()
    
    @staticmethod
    def create_selection_list(parent, title: str, items: List[Dict], 
                              display_func: Callable, on_select: Callable,
                              width: int = 600, height: int = 400):
        """Create a selection list popup."""
        popup = ctk.CTkToplevel(parent)
        popup.geometry(f"{width}x{height}")
        popup.title(title)
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        list_frame = ctk.CTkScrollableFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for item in items:
            item_frame = ctk.CTkFrame(list_frame)
            item_frame.pack(fill="x", pady=2)
            
            display_text = display_func(item)
            ctk.CTkLabel(item_frame, text=display_text).pack(side="left", padx=5)
            
            def select(i=item):
                on_select(i)
                popup.destroy()
            
            ctk.CTkButton(item_frame, text="Select", width=80, command=select).pack(side="right", padx=5)
        
        return popup