#lib/windows.py
import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox as tkmb
import customtkinter as ctk
import os
import threading
from PIL import Image, ImageTk
import random
from datetime import datetime
from lib.sentence_explorer import SentenceExplorerFrame
from lib.debug_utils import DebugLogger
import time

# Import from ui_components
from lib.ui_components import LookupPanel, ThinkBox, popup_message, MODES

# Import async utilities
from lib.async_utils import run_async, stream_to_widgets, set_widget_text, clear_widget

# Import chain and streaming popup
from lib.chain import ChainManager
from lib.streaming_popup import StreamingPopup

try:
    from lib.localai import OllamaClient
except ImportError as e:
    from localai import OllamaClient
    print(f"Error importing OllamaClient: {e}")

try:
    from lib.ccedict import lookup_cedict, extract_chinese_word_at_position, is_chinese_char
except ImportError:
    lookup_cedict = extract_chinese_word_at_position = is_chinese_char = None


class PopupDataService:
    """Encapsulates all DB operations for popups."""
    def __init__(self, db=None):
        self.db = db
    
    def save_word(self, word, translation, session_id=None):
        if not self.db:
            return None
        word_id = self.db.add_word(word, translation, example="")
        if session_id:
            self.db.add_word_to_session(session_id, word_id)
        return word_id
    
    def save_explanation_as_content(self, title, content, session_id=None, parent_node_id=None, metadata=None):
        if not self.db:
            return None
        return self.db.create_content_node(
            node_type='response',
            content=content,
            title=title,
            parent_node_id=parent_node_id,
            session_id=session_id,
            metadata=metadata or {"source": "popup_explanation"}
        )
    
    def record_word_occurrence(self, word, content_node_id, position_start=0, position_end=None):
        if not self.db or not content_node_id:
            return
        word_id = self.db.get_word_id(word)
        if word_id:
            self.db.record_word_occurrence(
                word_id=word_id,
                content_node_id=content_node_id,
                position_start=position_start,
                position_end=position_end or len(word)
            )
    
    def get_active_session_id(self):
        if not self.db:
            return None
        active = self.db.get_active_session()
        return active['session_id'] if active else None
    
    def word_exists(self, word):
        if not self.db:
            return False
        return self.db.get_word_id(word) is not None


class TranslationDialog:
    """Modal dialog to prompt user for translation confirmation/editing."""
    def __init__(self, master, word, suggested_translation=""):
        self.result = None
        self.dialog = ctk.CTkToplevel(master)
        self.dialog.geometry("500x250")
        self.dialog.title(f"Confirm Translation: {word}")
        self.dialog.attributes("-topmost", True)
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        
        ctk.CTkLabel(
            self.dialog, 
            text=f"Word: {word}", 
            font=("Mengshen-Handwritten", 18, "bold")
        ).pack(pady=(10, 5))
        
        ctk.CTkLabel(
            self.dialog,
            text="Translation (edit if needed):",
            font=("Mengshen-Handwritten", 12)
        ).pack(pady=(5, 2))
        
        self.translation_box = ctk.CTkTextbox(
            self.dialog,
            wrap="word",
            font=("Mengshen-Handwritten", 12),
            height=4
        )
        self.translation_box.insert("1.0", suggested_translation)
        self.translation_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        button_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(
            button_frame,
            text="✓ Save",
            fg_color="green",
            command=self._on_save
        ).pack(side="left", padx=5, expand=True, fill="x")
        
        ctk.CTkButton(
            button_frame,
            text="✕ Cancel",
            fg_color="#942626",
            command=self._on_cancel
        ).pack(side="left", padx=5, expand=True, fill="x")
    
    def _on_save(self):
        self.result = self.translation_box.get("1.0", "end-1c").strip()
        self.dialog.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        self.dialog.focus_set()
        self.dialog.wait_window()
        return self.result


class PopupSaveManager:
    """Orchestrates word save workflow."""
    def __init__(self, data_service, parent_widget=None, context=None):
        self.data_service = data_service
        self.parent_widget = parent_widget
        self.context = context
    
    def extract_translation(self, explanation_text):
        if not explanation_text:
            return ""
        import re
        sentences = re.split(r'[。！？\.\!\?]', explanation_text)
        first_sentence = sentences[0].strip() if sentences else ""
        if len(first_sentence) > 200:
            first_sentence = first_sentence[:197] + "..."
        return first_sentence
    
    def save_word_with_prompt(self, word, explanation_text):
        if not word or not word.strip():
            return None
        word = word.strip()
        
        if self.data_service.word_exists(word):
            tkmb.showinfo("Word Exists", f"'{word}' is already in your vocabulary.")
            return None
        
        suggested = self.extract_translation(explanation_text)
        dialog = TranslationDialog(self.parent_widget or ctk._default_root, word, suggested)
        translation = dialog.show()
        
        if not translation:
            return None
        
        session_id = self.data_service.get_active_session_id()
        parent_node_id = self.context.active_node_id if self.context else None
        
        word_id = self.data_service.save_word(word, translation, session_id=session_id)
        
        if word_id and parent_node_id:
            self.data_service.record_word_occurrence(word, parent_node_id)
        
        return word_id


class ControlPanel:
    def __init__(self, app_callback=None, ai_client: OllamaClient = OllamaClient(), db=None, data_service=None, context=None): 
        ctk.set_appearance_mode("dark")
        # ctk.set_default_color_theme(os.path.join(current_folder, "theme.json"))

        self.ai = ai_client
        self.db = db
        self.data_service = data_service or PopupDataService(db)
        self.context = context or ChainManager(db)
        self.context.current_mode = MODES[1] if hasattr(self.context, 'current_mode') else MODES[1]
        
        self.ai_opened = True
        self.opened = False
        self.done = False
        self.app_callback = app_callback
        self.generate_callback = None
        self.mode_index = 1
        self.response_mode = MODES[self.mode_index]
        self.current_clipboard_text = ""
        self.long_clipboard_warning = False
        self.thinking_enabled = getattr(self.ai, "think", False)
        self.show_thinking = True
        
        self.root = ctk.CTk()
        self.root.title("Monitor")
        self.root.resizable(width=True, height=True)
        self.root.wm_attributes("-topmost", True)
        self.status_text = "Unknown"

        # UI Setup
        self.top_line_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.top_line_frame.pack(side="top", fill="x", padx=10, pady=5)
        self.top_line_label = ctk.CTkLabel(self.top_line_frame, text="AI Unknown, 📋 (No clipboard text)", text_color="gray", anchor="w", justify="left", cursor="hand2")
        self.top_line_label.pack(side="left", fill="x", expand=True)
        self.top_line_label.bind("<Button-1>", self._on_clipboard_click)
        self.top_line_font = tkfont.Font(font=self.top_line_label.cget("font"))

        # Session context
        self.session_context = ""
        self.session_entry = ctk.CTkEntry(self.top_line_frame, width=220)
        self.session_entry.insert(0, "")
        self.session_entry.pack(side="right", padx=(5,0))
        self.session_send = ctk.CTkButton(self.top_line_frame, text="💬", width=40, command=lambda: setattr(self, 'session_context', self.session_entry.get()))
        self.session_send.pack(side="right", padx=(5,0))

        # Session management controls
        session_control_frame = ctk.CTkFrame(self.top_line_frame, fg_color="transparent")
        session_control_frame.pack(side="right", padx=5)

        self.session_status_label = ctk.CTkLabel(session_control_frame, text="📚 No session", 
                                                font=ctk.CTkFont(size=10), text_color="gray")
        self.session_status_label.pack(side="left", padx=2)

        self.new_session_btn = ctk.CTkButton(session_control_frame, text="📂", width=30, height=25,
                                            command=self._create_new_session)
        self.new_session_btn.pack(side="left", padx=2)

        self.end_session_btn = ctk.CTkButton(session_control_frame, text="⏹️", width=30, height=25,
                                            fg_color="orange", command=self._end_current_session)
        self.end_session_btn.pack(side="left", padx=2)

        self.session_list_btn = ctk.CTkButton(session_control_frame, text="📜", width=30, height=25,
                                            command=self._show_session_list)
        self.session_list_btn.pack(side="left", padx=2)
        
        # Buttons Frame
        self.buttons_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.buttons_frame.pack(side="top", fill="x", padx=10, pady=5)
        
        self.state_btn = ctk.CTkButton(self.buttons_frame, text="▶️", fg_color="green", width=50, command=self.toggle_state)
        self.state_btn.pack(side="left", padx=5)
        self.app_btn = ctk.CTkButton(self.buttons_frame, text="📱", width=50, command=self.open_app)
        self.app_btn.pack(side="left", padx=5)
        self.toggle_advanced_btn = ctk.CTkButton(self.buttons_frame, text="▼", width=50, command=self.toggle_advanced)
        self.toggle_advanced_btn.pack(side="left", padx=5)
        self.exit_btn = ctk.CTkButton(self.buttons_frame, text="❌", fg_color="#942626", hover_color="#731d1d", width=50, command=self.cancel)
        self.exit_btn.pack(side="left", padx=5)

        self.advanced_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.ai_btn = ctk.CTkButton(self.advanced_frame, text="🤖 Unload", fg_color="#4a4a4a", command=self.toggle_ai)
        self.ai_btn.pack(side="top", fill="x", pady=5)
        self.think_btn = ctk.CTkButton(self.advanced_frame, text=f"🧠 {'On' if self.thinking_enabled else 'Off'}", fg_color="#4a4a4a", command=self.toggle_thinking)
        self.think_btn.pack(side="top", fill="x", pady=5)
        self.show_think_btn = ctk.CTkButton(self.advanced_frame, text=f"👁️ {'Show' if self.show_thinking else 'Hide'}", fg_color="#4a4a4a", command=self.toggle_show_thinking)
        self.show_think_btn.pack(side="top", fill="x", pady=5)
        self.mode_menu = ctk.CTkOptionMenu(self.advanced_frame, values=MODES, command=lambda m: setattr(self, 'response_mode', m))
        self.mode_menu.set(self.response_mode)
        self.mode_menu.pack(side="top", fill="x", pady=5)

        self.root.bind("<Configure>", self._on_root_configure)
        self.advanced_visible = False

        self.debug_btn = ctk.CTkButton(self.buttons_frame, text="🐛 Debug", width=50, command=self.show_debug_console)
        self.debug_btn.pack(side="left", padx=5)
        
        self.debug_console = None
        self.debug_logs = []

        self.chain_viewer_btn = ctk.CTkButton(self.top_line_frame, text="🔗", width=30, command=self.show_chain_selector)
        self.chain_viewer_btn.pack(side="right", padx=2)
    
    def show_chain_selector(self):
        if not self.db:
            popup_message("No Database", "Database not available", parent=self.root)
            return
        
        cursor = self.db._get_cursor()
        cursor.execute("""
            SELECT id, node_type, title, created_at 
            FROM content_nodes 
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        nodes = cursor.fetchall()
        
        if not nodes:
            popup_message("No Nodes", "No content nodes found", parent=self.root)
            return
        
        selector = ctk.CTkToplevel(self.root)
        selector.title("Select Node to View Chain")
        selector.geometry("600x400")
        selector.attributes("-topmost", True)
        
        ctk.CTkLabel(selector, text="Recent Content Nodes", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        list_frame = ctk.CTkScrollableFrame(selector)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for node in nodes:
            node_id, node_type, title, created_at = node
            date_str = datetime.fromtimestamp(created_at).strftime('%H:%M:%S')
            
            item_frame = ctk.CTkFrame(list_frame)
            item_frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(item_frame, text=f"[{date_str}]", width=80, text_color="gray").pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=f"{node_type[:8]}", width=100, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=title[:40] if title else "-", width=250).pack(side="left", padx=5)
            
            def view(nid=node_id):
                from lib.chain_viewer import ChainViewer
                viewer = ChainViewer(selector, self.db, nid, f"Content Chain - Node {nid}")
                viewer.focus()
            
            ctk.CTkButton(item_frame, text="View Chain", width=100, command=view).pack(side="right", padx=5)

    def show_debug_console(self):
        if self.debug_console and self.debug_console.winfo_exists():
            self.debug_console.lift()
            return
        
        self.debug_console = ctk.CTkToplevel(self.root)
        self.debug_console.title("Debug Console - Chain Events")
        self.debug_console.geometry("800x400")
        self.debug_console.attributes("-topmost", True)
        
        self.debug_text = ctk.CTkTextbox(self.debug_console, wrap="word", font=("Consolas", 10))
        self.debug_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        btn_frame = ctk.CTkFrame(self.debug_console, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(btn_frame, text="Clear", command=self._clear_debug_console).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Test Chain", command=self._test_chain_creation).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Show Last Node", command=self._show_last_node_chain).pack(side="left", padx=5)
        
        for log in self.debug_logs:
            self.debug_text.insert("end", log + "\n")
        self.debug_text.see("end")
    
    def _clear_debug_console(self):
        self.debug_text.delete("1.0", "end")
        self.debug_logs.clear()
    
    def _test_chain_creation(self):
        if not self.db:
            self._add_debug_log("❌ No database available for test")
            return
        
        self._add_debug_log("=" * 60)
        self._add_debug_log("🧪 TEST: Creating test chain")
        
        root_id = self.db.create_content_node(
            node_type='raw_text',
            content="Test root content",
            title="Test Root",
            session_id=self.data_service.get_active_session_id()
        )
        self._add_debug_log(f"✓ Created root node: {root_id}")
        
        child_id = self.db.create_content_node(
            node_type='response',
            content="Test child response",
            title="Test Child",
            parent_node_id=root_id,
            session_id=self.data_service.get_active_session_id()
        )
        self._add_debug_log(f"✓ Created child node: {child_id}")
        
        chain = self.db.get_content_chain(child_id)
        self._add_debug_log(f"Chain length: {len(chain)}")
        for i, node in enumerate(chain):
            self._add_debug_log(f"  [{i}] id={node['id']}, type={node['node_type']}")
        
        self._add_debug_log("=" * 60)
    
    def _show_last_node_chain(self):
        if not self.db:
            self._add_debug_log("❌ No database available to show chain")
            return
        
        last_node_id = None
        try:
            last_node_id = self.db.get_last_content_node_id()
        except Exception as e:
            self._add_debug_log(f"❌ Error fetching last node: {e}")
            return
        
        if not last_node_id:
            self._add_debug_log("⚠️ No content nodes found in database")
            return
        
        self._add_debug_log(f"🔍 Fetching chain for last node id: {last_node_id}")
        try:
            chain = self.db.get_content_chain(last_node_id)
            self._add_debug_log(f"Chain length: {len(chain)}")
            for i, node in enumerate(chain):
                self._add_debug_log(f"  [{i}] id={node['id']}, type={node['node_type']}, title={node['title']}")
        except Exception as e:
            self._add_debug_log(f"❌ Error fetching chain: {e}")
    
    def _add_debug_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.debug_logs.append(log_entry)
        if self.debug_console and self.debug_console.winfo_exists():
            self.debug_text.insert("end", log_entry + "\n")
            self.debug_text.see("end")
    
    def update_ai_status(self, status_text, color):
        self.status_text = status_text
        self.root.after(0, lambda: self._update_top_line(color=color))
    
    def update_clipboard_display(self, text, is_valid_chinese=False, too_long=False):
        if too_long:
            self.current_clipboard_text = ""
            self.clipboard_is_chinese = False
            self.long_clipboard_warning = True
        else:
            self.current_clipboard_text = text
            self.clipboard_is_chinese = is_valid_chinese
            self.long_clipboard_warning = False
        self.root.after(0, lambda: self._update_top_line())

    def _update_top_line(self, color=None):
        status_text = self.status_text or "Unknown"
        if getattr(self, 'long_clipboard_warning', False):
            clip_text = "(long text ignored)"
            icon = "⚠️"
        else:
            clip_text = self.current_clipboard_text or "(No clipboard text)"
            icon = "🔤" if getattr(self, 'clipboard_is_chinese', False) else "📋"
        self.top_line_label.configure(text=f"AI {status_text}, {icon} {clip_text}", text_color=color or "gray")

    def _on_root_configure(self, event):
        pass

    def _on_clipboard_click(self, event):
        if self.current_clipboard_text and self.generate_callback:
            self.generate_callback(self.current_clipboard_text)

    def load_ai(self):
        def worker():
            return self.ai.manage_model("load")
        
        def on_done(success):
            if success:
                self.update_ai_status("Loaded (VRAM Occupied)", "green")
            else:
                self.update_ai_status("Load Failed", "red")
        
        self.update_ai_status("Loading...", "orange")
        run_async(self.root, worker, on_done)

    def unload_ai(self):
        def worker():
            return self.ai.manage_model("unload")
        
        def on_done(success):
            if success:
                self.update_ai_status("Unloaded (VRAM Free)", "gray")
            else:
                self.update_ai_status("Unload Failed", "red")
        
        self.update_ai_status("Unloading...", "orange")
        run_async(self.root, worker, on_done)

    def toggle_ai(self):
        if self.ai_opened:
            self.unload_ai()
            self.ai_opened = False
            self.ai_btn.configure(text="🤖 Load", fg_color="#4a4a4a")
        else:
            self.load_ai()
            self.ai_opened = True
            self.ai_btn.configure(text="🤖 Unload", fg_color="#4a4a4a")

    def toggle_thinking(self):
        self.thinking_enabled = not self.thinking_enabled
        if hasattr(self.ai, 'think'):
            self.ai.think = self.thinking_enabled
        self.think_btn.configure(text="🧠 On" if self.thinking_enabled else "🧠 Off", fg_color="green" if self.thinking_enabled else "#4a4a4a")

    def toggle_show_thinking(self):
        self.show_thinking = not self.show_thinking
        self.show_think_btn.configure(text="👁️ Show" if self.show_thinking else "👁️ Hide", fg_color="green" if self.show_thinking else "#4a4a4a")

    def toggle_state(self):
        self.opened = not self.opened
        self.state_btn.configure(text="⏸️" if self.opened else "▶️", fg_color="orange" if self.opened else "green")
        self.update_ai_status("Running" if self.opened else "Paused", "green" if self.opened else "gray")
    
    def toggle_advanced(self):
        if self.advanced_visible:
            self.advanced_frame.pack_forget()
            self.toggle_advanced_btn.configure(text="▼")
            self.advanced_visible = False
            if self.session_entry and self.session_send:
                self.session_entry.pack(side="right", padx=(5,0))
                self.session_send.pack(side="right", padx=(5,0))
        else:
            self.advanced_frame.pack(after=self.buttons_frame, side="top", fill="x", padx=10, pady=5)
            self.toggle_advanced_btn.configure(text="▲")
            self.advanced_visible = True
            if self.session_entry and self.session_send:
                self.session_entry.pack_forget()
                self.session_send.pack_forget()

    def open_app(self):
        if self.app_callback:
            self.app_callback()

    def _create_new_session(self):
        if self.db is None:
            popup_message("Database Missing", "Session management requires a database connection.", parent=self.root)
            return

        popup = ctk.CTkToplevel(self.root)
        popup.geometry("300x250")
        popup.title("New Session")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Create New Learning Session", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
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
            self._refresh_session_status()
            popup.destroy()
            popup_message("Session Created", f"Session {session_id} created!\nAdd words while studying to track them.", parent=self.root)
        
        ctk.CTkButton(popup, text="Create", command=create, fg_color="green").pack(pady=10)

    def _end_current_session(self):
        if self.db is None:
            popup_message("Database Missing", "Session management requires a database connection.", parent=self.root)
            return

        active = self.db.get_active_session()
        if not active:
            popup_message("No Active Session", "No active session to end.", parent=self.root)
            return
        
        if popup_message("End Session", f"End session '{active['session_type']}' with {active['word_count']} words?", is_yes_no=True, parent=self.root):
            self.db.end_session(active['session_id'])
            self._refresh_session_status()
            popup_message("Session Ended", f"Session ended. {active['word_count']} words recorded.", parent=self.root)

    def _refresh_session_status(self):
        if self.db is None:
            self.session_status_label.configure(text="📚 No session", text_color="gray")
            return

        active = self.db.get_active_session()
        if active:
            self.session_status_label.configure(text=f"📚 {active['session_type']}: {active['word_count']} words", 
                                                text_color="green")
        else:
            self.session_status_label.configure(text="📚 No session", text_color="gray")

    def _show_session_list(self):
        if self.db is None:
            popup_message("Database Missing", "Session management requires a database connection.", parent=self.root)
            return

        sessions = self.db.get_all_sessions()
        if not sessions:
            popup_message("Sessions", "No sessions recorded yet.", parent=self.root)
            return
        
        popup = ctk.CTkToplevel(self.root)
        popup.geometry("700x500")
        popup.title("Session Manager")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="📚 Session Manager", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        list_frame = ctk.CTkScrollableFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        for s in sessions:
            item_frame = ctk.CTkFrame(list_frame)
            item_frame.pack(fill="x", pady=3)
            
            date_str = datetime.fromtimestamp(s['start_time']).strftime('%m-%d %H:%M')
            type_icon = {"Manhua": "📖", "Song": "🎵", "News": "📰", "Conversation": "💬"}.get(s['session_type'], "📚")
            status = "🟢" if s['end_time'] == 0 else "🔴"
            
            ctk.CTkLabel(item_frame, text=f"{status} {type_icon} {s['session_type']}", 
                        font=ctk.CTkFont(weight="bold"), width=120).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=s['source_name'][:30] if s['source_name'] else "Untitled", 
                        width=150).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=f"{s['word_count']} words", width=80).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=date_str, width=100, text_color="gray").pack(side="left", padx=5)
            
            def view_words(sid=s['session_id']):
                self._view_session_words(sid)
                popup.destroy()
            ctk.CTkButton(item_frame, text="View Words", width=80, command=view_words).pack(side="right", padx=5)

    def _view_session_words(self, session_id: str):
        words = self.db.get_session_words(session_id)
        
        popup = ctk.CTkToplevel(self.root)
        popup.geometry("500x400")
        popup.title(f"Session Words")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=f"📚 Session: {session_id}", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        if words:
            list_frame = ctk.CTkScrollableFrame(popup)
            list_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            for w in words:
                word_frame = ctk.CTkFrame(list_frame)
                word_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(word_frame, text=w['word'], font=ctk.CTkFont(weight="bold"), width=100).pack(side="left", padx=5)
                ctk.CTkLabel(word_frame, text=w['translation'][:40], width=250).pack(side="left", padx=5)
        else:
            ctk.CTkLabel(popup, text="No words in this session yet.").pack(pady=20)
    
    def get_current_chain_context(self):
        active_session = self.db.get_active_session() if self.db else None
        return {
            "db": self.db,
            "session_id": active_session['session_id'] if active_session else None,
            "parent_node_id": self.context.active_node_id if self.context else None
        }

    def store_generated_response(self, user_query: str, ai_response: str, mode: str, parent_node_id=None):
        if not self.data_service or not self.data_service.db:
            return None
        
        session_id = self.data_service.get_active_session_id()
        actual_parent = parent_node_id or (self.context.active_node_id if self.context else None)
        
        node_id = self.data_service.save_explanation_as_content(
            title=f"AI Response to: {user_query[:50]}",
            content=ai_response,
            session_id=session_id,
            parent_node_id=actual_parent
        )
        if self.context:
            self.context.active_node_id = node_id
        return node_id
    
    def show(self):
        self.root.mainloop()

    def cancel(self):
        self.done = True
        self.root.destroy()


class ReviewFrame(ctk.CTkFrame):
    def __init__(self, master, reviewer, **kwargs):
        super().__init__(master, **kwargs)
        self.reviewer = reviewer
        self._setup_ui()
        self._load_words()

    def _setup_ui(self):
        ctk.CTkLabel(self, text="📚 Word Review", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)
        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.pack()
        
        card = ctk.CTkFrame(self)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        self.word_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=36, weight="bold"), wraplength=400)
        self.word_label.pack(pady=(30, 10))
        self.trans_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=24), text_color="green")
        self.trans_label.pack(pady=10)
        self.example_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=14, slant="italic"), text_color="gray", wraplength=400)
        self.example_label.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="Hard", fg_color="orange", command=lambda: self._review("hard")).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(btn_frame, text="Good", fg_color="green", command=lambda: self._review("good")).pack(side="left", padx=5, expand=True)

        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=20, pady=10)
        self.prev_btn = ctk.CTkButton(nav_frame, text="← Previous", command=self._prev_word)
        self.prev_btn.pack(side="left", padx=5)
        self.next_btn = ctk.CTkButton(nav_frame, text="Next →", command=self._next_word)
        self.next_btn.pack(side="right", padx=5)

    def _load_words(self):
        self.reviewer.load_review_words()
        self._update_display()

    def _update_display(self):
        word = self.reviewer.get_current_word()
        if word:
            self.word_label.configure(text=word[1])
            self.trans_label.configure(text=word[2])
            self.example_label.configure(text=f'"{word[3]}"' if word[3] else "")
            self.progress_label.configure(text=self.reviewer.get_progress())
            self.prev_btn.configure(state="normal" if self.reviewer.current_index > 0 else "disabled")
            self.next_btn.configure(state="normal" if self.reviewer.current_index < len(self.reviewer.words) - 1 else "disabled")
        else:
            self.word_label.configure(text="✨ All caught up!")

    def _review(self, quality):
        if self.reviewer.has_words():
            def worker():
                return self.reviewer.review_current(quality)
            
            def on_done(next_date):
                tkmb.showinfo("Review Complete", f"Next review: {next_date}")
                self._update_display()
            
            run_async(self, worker, on_done)

    def _prev_word(self):
        if self.reviewer.current_index > 0:
            self.reviewer.current_index -= 1
            self._update_display()

    def _next_word(self):
        if self.reviewer.next_word():
            self._update_display()


class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, ai_client, db, control_panel=None, 
                 word_index=None, char_def_index=None, **kwargs):
        super().__init__(master, **kwargs)
        self.ai = ai_client
        self.db = db
        self.control_panel = control_panel
        self.is_generating = False
        
        self.word_index = word_index if word_index is not None else {}
        self.char_def_index = char_def_index if char_def_index is not None else {}
        
        if not self.word_index and not self.char_def_index:
            try:
                from lib.ccedict import load_cedict_entries
                _, self.word_index, _, self.char_def_index = load_cedict_entries("cedict_ts.u8")
            except Exception:
                pass
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="Welcome Back", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, pady=(20, 10), sticky="n")

        # Daily Challenge Section
        self.insight_card = ctk.CTkFrame(self, fg_color=("gray90", "gray15"))
        self.insight_card.grid(row=1, column=0, padx=40, pady=10, sticky="nsew")
        self.insight_card.grid_columnconfigure(0, weight=1)
        self.insight_card.grid_columnconfigure(1, weight=0)
        
        ctk.CTkLabel(self.insight_card, text="✨ Daily AI Challenge", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=5)
        self.insight_text = ctk.CTkTextbox(self.insight_card, wrap="word", font=("Mengshen-Handwritten", 14), height=100)
        self.insight_text.configure(state="disabled")
        self.insight_text.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")
        
        self.think_challenge = ThinkBox(self.insight_card)
        self.think_challenge.grid(row=2, column=0, pady=5, padx=10, sticky="ew")
        
        self.lookup_challenge = LookupPanel(self.insight_card, word_index=self.word_index, char_def_index=self.char_def_index)
        self.lookup_challenge.grid(row=1, column=1, rowspan=2, pady=10, padx=5, sticky="nsew")
        self.lookup_challenge.configure(width=150)
        
        # Words Summary Section
        self.summary_card = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        self.summary_card.grid(row=2, column=0, padx=40, pady=10, sticky="nsew")
        self.summary_card.grid_columnconfigure(0, weight=1)
        self.summary_card.grid_columnconfigure(1, weight=0)
        
        ctk.CTkLabel(self.summary_card, text="📚 Words Summary", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, pady=5)
        self.summary_text = ctk.CTkTextbox(self.summary_card, wrap="word", font=("Mengshen-Handwritten", 12), height=100)
        self.summary_text.configure(state="disabled")
        self.summary_text.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")
        
        self.think_summary = ThinkBox(self.summary_card)
        self.think_summary.grid(row=2, column=0, pady=5, padx=10, sticky="ew")
        
        self.lookup_summary = LookupPanel(self.summary_card, word_index=self.word_index, char_def_index=self.char_def_index)
        self.lookup_summary.grid(row=1, column=1, rowspan=2, pady=10, padx=5, sticky="nsew")
        self.lookup_summary.configure(width=150)

        # Buttons
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=3, column=0, pady=20)
        self.refresh_btn = ctk.CTkButton(self.button_frame, text="New Challenge", command=self.generate_challenge)
        self.refresh_btn.pack(side="left", padx=5)
        self.summary_btn = ctk.CTkButton(self.button_frame, text="Generate Summary", command=self.generate_summary, state="disabled")
        self.summary_btn.pack(side="left", padx=5)

        self.last_words = []

    def generate_challenge(self):
        if self.is_generating:
            tkmb.showwarning("In Progress", "Already generating. Please wait.")
            return
        if not self.ai or not self.db:
            set_widget_text(self.insight_text, "❌ AI Client or Database not available")
            return

        try:
            self.last_words = self.db.get_recent_words(limit=3)
        except Exception as e:
            self.last_words = []
            print(f"Error reading recent words: {e}")

        self.is_generating = True
        self.refresh_btn.configure(state="disabled")
        self.summary_btn.configure(state="disabled")
        
        set_widget_text(self.insight_text, "Generating challenge...")
        clear_widget(self.think_challenge.text_box)
        
        word_list = ", ".join([w[1] for w in self.last_words]) if self.last_words else ""
        if not word_list:
            set_widget_text(self.insight_text, "No words in database yet. Add some words first!")
            self.is_generating = False
            self.refresh_btn.configure(state="normal")
            return
        
        def generator():
            return self.ai.generate_response(
                f"Word Blossom Mode: {word_list}",
                display_thinking=self.control_panel.show_thinking if self.control_panel else True
            )
        
        def on_complete(_):
            self.is_generating = False
            self.refresh_btn.configure(state="normal")
            self.summary_btn.configure(state="normal")
        
        stream_to_widgets(
            root=self,
            generator=generator(),
            text_widget=self.insight_text,
            think_widget=self.think_challenge.text_box,
            on_complete=on_complete,
            show_thinking=self.control_panel.show_thinking if self.control_panel else True
        )

    def generate_summary(self):
        if self.is_generating or not self.last_words:
            return

        self.is_generating = True
        self.refresh_btn.configure(state="disabled")
        
        set_widget_text(self.summary_text, "Generating summary...")
        clear_widget(self.think_summary.text_box)
        
        word_list = ", ".join([w[1] for w in self.last_words])
        
        def generator():
            return self.ai.generate_response(
                f"Summarize these words with Sparkle Notes Mode: {word_list}",
                display_thinking=self.control_panel.show_thinking if self.control_panel else True
            )
        
        def on_complete(_):
            self.is_generating = False
            self.refresh_btn.configure(state="normal")
        
        stream_to_widgets(
            root=self,
            generator=generator(),
            text_widget=self.summary_text,
            think_widget=self.think_summary.text_box,
            on_complete=on_complete,
            show_thinking=self.control_panel.show_thinking if self.control_panel else True
        )


class App(ctk.CTk):
    def __init__(self, reviewer, ai_client=None, db=None, control_panel=None, context=None):
        super().__init__()
        self.reviewer = reviewer
        self.ai_client = ai_client
        self.db = db
        self.control_panel = control_panel
        self.context = context
        self.title("Vocabulary App")
        self.geometry("800x550")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.word_index = {}
        self.char_def_index = {}
        try:
            from lib.ccedict import load_cedict_entries
            _, self.word_index, _, self.char_def_index = load_cedict_entries("cedict_ts.u8")
        except Exception as e:
            print(f"Could not load CEDICT: {e}")

        self.sidebar = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="VocabMaster", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20)
        ctk.CTkButton(self.sidebar, text="Home", command=lambda: self.show_frame("home")).grid(row=1, column=0, padx=20, pady=10)
        ctk.CTkButton(self.sidebar, text="Review", command=lambda: self.show_frame("review")).grid(row=2, column=0, padx=20, pady=10)
        ctk.CTkButton(self.sidebar, text="📖 Sentence Explorer", 
                      command=lambda: self.show_frame("explorer")).grid(row=3, column=0, padx=20, pady=10)

        self.frames = {
            "home": HomeFrame(self, self.ai_client, self.db, control_panel=self.control_panel, 
                             word_index=self.word_index, char_def_index=self.char_def_index, 
                             fg_color="transparent"),
            "review": ReviewFrame(self, self.reviewer, fg_color="transparent"),
            "explorer": SentenceExplorerFrame(self, self.ai_client, self.db, 
                                              word_index=self.word_index, 
                                              char_def_index=self.char_def_index,
                                              fg_color="transparent")
        }
        
        for frame in self.frames.values():
            frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.show_frame("home")
    
    def show_frame(self, page_name):
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[page_name].grid(row=0, column=1, sticky="nsew", padx=20, pady=20)


if __name__ == "__main__":
    popup_message("Test Message", "This is a test message to verify the popup_message function is working correctly.")
    panel = ControlPanel()
    # Test with a mock chain manager
    from lib.chain import ChainManager
    mock_chain = ChainManager(None)
    popup = StreamingPopup("测试", panel.root, mock_chain, None, mode="Lookup Only", 
                           word_index={}, char_def_index={})
    popup.focus()
    panel.show()