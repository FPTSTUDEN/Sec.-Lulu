# lib/windows.py
import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox as tkmb
import customtkinter as ctk
import os
import threading
from PIL import Image, ImageTk
import random
from datetime import datetime
from lib.debug_utils import DebugLogger
import time
from lib.async_utils import run_async, stream_to_widgets, set_widget_text, clear_widget
from lib.sentence_explorer import SentenceExplorerFrame

MODES = ["Lookup Only", "Sparkle Notes", "Immersion Mode", "Word Blossom", "Sentence Whisper"]

current_folder = os.path.dirname(os.path.abspath(__file__))
repo_folder = os.path.dirname(current_folder)
os.chdir(repo_folder)

try:
    from lib.localai import OllamaClient
except ImportError as e:
    from localai import OllamaClient
    print(f"Error importing OllamaClient: {e}")

try:
    from lib.ccedict import lookup_cedict, extract_chinese_word_at_position, is_chinese_char
except ImportError:
    lookup_cedict = extract_chinese_word_at_position = is_chinese_char = None


# ======================
# Learning Context - Single source of truth for chain tracking
# ======================

class LearningContext:
    """Single source of truth for current learning session state."""
    def __init__(self, db=None):
        self.db = db
        self.active_node_id = None
        self.active_session_id = None
        self.current_mode = "Sparkle Notes"
    
    def create_child_node(self, node_type, content, title=None, metadata=None):
        if not self.db:
            return None
        
        node_id = self.db.create_content_node(
            node_type=node_type,
            content=content,
            title=title,
            parent_id=self.active_node_id,
            session_id=self.active_session_id,
            metadata=metadata
        )
        self.active_node_id = node_id
        return node_id


# ======================
# Service Layer (DB Operations Decoupled from UI)
# ======================

class PopupDataService:
    """Encapsulates all DB operations for popups using simplified API."""
    def __init__(self, db=None):
        self.db = db
    
    def save_word(self, word, translation, session_id=None):
        if not self.db:
            return None
        return self.db.create_word(word, translation, session_id=session_id)
    
    def word_exists(self, word):
        if not self.db:
            return False
        return self.db.get_word(word) is not None
    
    def get_active_session_id(self):
        if not self.db:
            return None
        active = self.db.get_active_session()
        return active['id'] if active else None
    
    def save_explanation_as_content(self, title, content, session_id=None, parent_node_id=None, metadata=None):
        if not self.db:
            return None
        return self.db.create_content_node(
            node_type='response',
            content=content,
            title=title,
            parent_id=parent_node_id,
            session_id=session_id,
            metadata=metadata
        )
    
    def record_word_occurrence(self, word, content_node_id):
        if not self.db:
            return
        self.db.record_word_occurrence(word, content_node_id)


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
        
        dialog = TranslationDialog(
            self.parent_widget or tk._default_root,
            word,
            suggested
        )
        translation = dialog.show()
        
        if not translation:
            return None
        
        session_id = self.data_service.get_active_session_id()
        parent_node_id = self.context.active_node_id if self.context else None
        
        word_id = self.data_service.save_word(word, translation, session_id=session_id)
        
        if word_id and parent_node_id:
            self.data_service.record_word_occurrence(word, parent_node_id)
        
        return word_id


# ======================
# Reusable Components
# ======================

class LookupPanel(ctk.CTkFrame):
    """Reusable sidebar panel for CEDICT lookup."""
    def __init__(self, master, word_index=None, char_def_index=None, word_click_callback=None, 
                 generate_explanation_callback=None, data_service=None, context=None, **kwargs):
        super().__init__(master, fg_color=("gray85", "gray25"), corner_radius=8, **kwargs)
        self.word_index = word_index or {}
        self.char_def_index = char_def_index or {}
        self.last_looked_up_word = None
        self.tracked_text_widgets = []
        self.current_hovered_word = None
        self.word_click_callback = word_click_callback or self._default_word_click
        self.generate_explanation_callback = generate_explanation_callback
        self.data_service = data_service
        self.context = context

        lookup_title = ctk.CTkLabel(self, text="📖 Lookup", font=("Mengshen-Handwritten", 14, "bold"), text_color="orange")
        lookup_title.pack(pady=5)

        self.lookup_text = ctk.CTkTextbox(self, wrap="word", font=("Mengshen-Handwritten", 12), height=120)
        self.lookup_text.configure(state="disabled")
        self.lookup_text.pack(fill="both", expand=True, padx=5, pady=5)

    def bind_text_box(self, ctk_textbox):
        try:
            underlying = getattr(ctk_textbox, '_textbox', None)
            if underlying:
                self.tracked_text_widgets.append(underlying)
                underlying.bind("<Motion>", lambda e: self._on_text_motion(e))
                underlying.bind("<Leave>", lambda e: self._on_text_leave())
                underlying.bind("<ButtonPress-1>", lambda e: self._on_button_press(e))
                underlying.bind("<ButtonRelease-1>", lambda e: self._on_button_release(e))
        except Exception:
            pass

    def _on_text_motion(self, event):
        try:
            text_widget = event.widget
            index = text_widget.index(f"@{event.x},{event.y}")
            if not index: return
            line, col = map(int, index.split("."))
            text_content = text_widget.get("1.0", "end-1c")
            lines = text_content.split("\n")
            abs_pos = sum(len(lines[i]) + 1 for i in range(line - 1)) + col
            if abs_pos >= len(text_content): return
            if abs_pos > 0 and not is_chinese_char(text_content[abs_pos]) and is_chinese_char(text_content[abs_pos - 1]):
                abs_pos = abs_pos - 1
            word, start_pos, end_pos = extract_chinese_word_at_position(text_content, abs_pos, self.word_index)
            if word and word != self.last_looked_up_word:
                self.last_looked_up_word = word
                self.current_hovered_word = word
                self._update_lookup_panel(word)
        except Exception:
            pass

    def _on_text_leave(self):
        self.last_looked_up_word = None
        self._clear_lookup_panel()

    def _on_button_press(self, event):
        try:
            event.widget._last_press = (event.x, event.y, getattr(event, 'time', None))
        except Exception:
            pass

    def _on_button_release(self, event):
        try:
            widget = event.widget
            press = getattr(widget, '_last_press', None)
            if not press: return
            px, py, ptime = press
            dx, dy = abs(event.x - px), abs(event.y - py)
            dt = getattr(event, 'time', None) - ptime if ptime and getattr(event, 'time', None) else None
            if dx <= 5 and dy <= 5 and (dt is None or dt <= 500):
                self._on_text_click(event)
            widget._last_press = None
        except Exception:
            pass

    def _on_text_click(self, event):
        if self.current_hovered_word:
            self._show_word_mode_popup(self.current_hovered_word)

    def _update_lookup_panel(self, word):
        self.lookup_text.configure(state="normal")
        self.lookup_text.delete("1.0", "end")
        self.lookup_text.insert("end", self._format_lookup_text(word))
        self.lookup_text.configure(state="disabled")

    def _clear_lookup_panel(self):
        self.lookup_text.configure(state="normal")
        self.lookup_text.delete("1.0", "end")
        self.lookup_text.configure(state="disabled")

    def _format_lookup_text(self, word):
        if not lookup_cedict: return "CEDICT not available"
        try:
            word_entry, char_matches = lookup_cedict(word, self.word_index, self.char_def_index)
            if word_entry:
                parts = [f"📖 {word_entry.get('simplified','')}\n({word_entry.get('traditional','')})\n"]
                parts.extend(f"• {d}" for d in word_entry.get('definitions', []))
                return "\n".join(parts)
            elif char_matches:
                return "Character breakdown:\n" + "\n".join(f"• {char}: {entry.get('simplified','')}" for char, entry in char_matches)
            return "No match found"
        except Exception:
            return "No match found"

    def _default_word_click(self, word, selected_mode):
        message = f"Mode: {selected_mode}\nWord: {word}\n\n{self._format_lookup_text(word)}"
        Long_message_popup(f"{word} — {selected_mode}", message, master=self, display_image=True, 
                           word_index=self.word_index, char_def_index=self.char_def_index, word_click_callback=None).show()

    def _show_word_mode_popup(self, word, data_service=None, db=None, session_id=None):
        parent_node_id = self.context.active_node_id if self.context else None
        if parent_node_id:
            print(f"🔗 Using LookupPanel context.active_node_id: {parent_node_id}")
        
        popup = ctk.CTkToplevel(self)
        popup.geometry("400x250")
        popup.title(f"Select Mode for '{word}'")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=f"Word: {word}", font=("Mengshen-Handwritten", 16, "bold")).pack(pady=(10, 5))
        ctk.CTkLabel(popup, text="Choose a mode:", font=("Mengshen-Handwritten", 12)).pack(pady=5)
        
        mode_var = ctk.StringVar(value=MODES[0])
        ctk.CTkOptionMenu(popup, values=MODES, variable=mode_var, font=("Mengshen-Handwritten", 11)).pack(pady=10, padx=20, fill="x")
        
        button_frame = ctk.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")
        
        service = data_service or self.data_service
        if not service and db:
            service = PopupDataService(db)
        
        def on_select():
            print(f"🔗 LookupPanel: Selected word '{word}' with mode '{mode_var.get()}', parent_node_id={parent_node_id}")
            
            new_node_id = None
            if service and service.db and parent_node_id:
                new_node_id = service.save_explanation_as_content(
                    title=f"Lookup: {word}",
                    content=word,
                    session_id=session_id,
                    parent_node_id=parent_node_id,
                    metadata={"source": "lookup_panel", "mode": mode_var.get()}
                )
                if new_node_id:
                    service.record_word_occurrence(word, new_node_id)
                    print(f"✓ Created lookup node {new_node_id} with parent {parent_node_id}")
                    if self.context:
                        self.context.active_node_id = new_node_id
            
            if self.generate_explanation_callback:
                self.generate_explanation_callback(word, mode_var.get(), context=self.context)
            else:
                self.word_click_callback(word, mode_var.get())
            
            popup.destroy()
        
        ctk.CTkButton(button_frame, text="✓ Select", fg_color="green", command=on_select).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(button_frame, text="✕ Cancel", fg_color="#942626", command=popup.destroy).pack(side="left", padx=5, expand=True)
        
        if parent_node_id and service and service.db:
            chain_info = ctk.CTkLabel(popup, text=f"🔗 This lookup will be linked to existing content (parent: {parent_node_id})", 
                                    font=ctk.CTkFont(size=10), text_color="green")
            chain_info.pack(pady=5)


class ThinkBox(ctk.CTkFrame):
    """Simple collapsible thinking box - UI only, no streaming logic."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.think_visible = True

        think_header = ctk.CTkFrame(self, fg_color="transparent")
        think_header.pack(side="top", fill="x", pady=(0, 3))
        ctk.CTkLabel(think_header, text="🧠 Thinking", font=("Mengshen-Handwritten", 12, "bold")).pack(side="left")
        self.toggle_btn = ctk.CTkButton(think_header, text="▲", width=25, height=20, command=self._toggle)
        self.toggle_btn.pack(side="right", padx=(5, 0))

        self.text_box = ctk.CTkTextbox(self, wrap="word", font=("Mengshen-Handwritten", 12), height=3)
        self.text_box.configure(state="disabled")
        self.text_box.pack(fill="both", expand=True)

    def append_think(self, text):
        """Append text (call from UI thread only)."""
        self.text_box.configure(state="normal")
        self.text_box.insert("end", text)
        self.text_box.configure(state="disabled")
        self.text_box.see("end")

    def clear_think(self):
        """Clear text (call from UI thread only)."""
        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", "end")
        self.text_box.configure(state="disabled")

    def _toggle(self):
        self.think_visible = not self.think_visible
        if self.think_visible:
            self.text_box.pack(fill="both", expand=True)
            self.toggle_btn.configure(text="▲")
        else:
            self.text_box.pack_forget()
            self.toggle_btn.configure(text="▼")


class ControlPanel:
    def __init__(self, app_callback=None, ai_client=None, db=None, data_service=None, context=None): 
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme(os.path.join(current_folder, "theme.json"))

        self.ai = ai_client or OllamaClient()
        self.db = db
        self.data_service = data_service or PopupDataService(db)
        self.context = context or LearningContext(db)
        self.context.current_mode = MODES[1]
        
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
        
        nodes = self.db.get_recent_nodes(limit=20)
        
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
            date_str = datetime.fromtimestamp(node['created_at']).strftime('%H:%M:%S')
            
            item_frame = ctk.CTkFrame(list_frame)
            item_frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(item_frame, text=f"[{date_str}]", width=80, text_color="gray").pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=f"{node['node_type'][:8]}", width=100, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=node.get('title', '-')[:40], width=250).pack(side="left", padx=5)
            
            def view(nid=node['id']):
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
            parent_id=root_id,
            session_id=self.data_service.get_active_session_id()
        )
        self._add_debug_log(f"✓ Created child node: {child_id}")
        
        chain = self.db.get_chain(child_id)
        self._add_debug_log(f"Chain length: {len(chain)}")
        for i, node in enumerate(chain):
            self._add_debug_log(f"  [{i}] id={node['id']}, type={node['node_type']}")
        
        self._add_debug_log("=" * 60)
    
    def _show_last_node_chain(self):
        if not self.db:
            self._add_debug_log("❌ No database available to show chain")
            return
        
        last_node_id = self.db.get_last_node_id()
        
        if not last_node_id:
            self._add_debug_log("⚠️ No content nodes found in database")
            return
        
        self._add_debug_log(f"🔍 Fetching chain for last node id: {last_node_id}")
        try:
            chain = self.db.get_chain(last_node_id)
            self._add_debug_log(f"Chain length: {len(chain)}")
            for i, node in enumerate(chain):
                self._add_debug_log(f"  [{i}] id={node['id']}, type={node['node_type']}, title={node.get('title')}")
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
        """Load AI model using unified async pattern."""
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
        
        if popup_message("End Session", f"End session with {active.get('word_count', 0)} words?", is_yes_no=True, parent=self.root):
            # Sessions don't need explicit end in simplified API
            self._refresh_session_status()
            popup_message("Session Ended", f"Session ended.", parent=self.root)

    def _refresh_session_status(self):
        """Update session status display."""
        if self.db is None:
            self.session_status_label.configure(text="📚 No session", text_color="gray")
            return

        active = self.db.get_active_session()
        if active:
            self.session_status_label.configure(
                text=f"📚 {active.get('title', 'Session')[:30]}: {active.get('word_count', 0)} words", 
                text_color="green"
            )
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
            
            date_str = datetime.fromtimestamp(s['created_at']).strftime('%m-%d %H:%M')
            title = s.get('title', 'Session')
            status = "🟢"
            
            ctk.CTkLabel(item_frame, text=f"{status} 📚", 
                        font=ctk.CTkFont(weight="bold"), width=40).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=title[:40], width=200).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=f"{s.get('word_count', 0)} words", width=80).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=date_str, width=100, text_color="gray").pack(side="left", padx=5)
            
            def view_words(sid=s['id']):
                self._view_session_words(sid)
                popup.destroy()
            ctk.CTkButton(item_frame, text="View Words", width=80, command=view_words).pack(side="right", padx=5)

    def _view_session_words(self, session_id: int):
        words = self.db.get_session_words(session_id)
        
        popup = ctk.CTkToplevel(self.root)
        popup.geometry("500x400")
        popup.title(f"Session Words")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text=f"📚 Session Details", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        if words:
            list_frame = ctk.CTkScrollableFrame(popup)
            list_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            for w in words:
                word_frame = ctk.CTkFrame(list_frame)
                word_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(word_frame, text=w['content'], font=ctk.CTkFont(weight="bold"), width=100).pack(side="left", padx=5)
                ctk.CTkLabel(word_frame, text=w.get('translation', '')[:40], width=250).pack(side="left", padx=5)
        else:
            ctk.CTkLabel(popup, text="No words in this session yet.").pack(pady=20)
    
    def get_current_chain_context(self):
        """Get current chain context."""
        active_session = self.db.get_active_session() if self.db else None
        return {
            "db": self.db,
            "session_id": active_session['id'] if active_session else None,
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


def popup_message(title, message, is_yes_no=False, parent=None):
    root = parent or tk._default_root
    created_root = False
    if root is None:
        root = tk.Tk()
        root.withdraw()
        created_root = True

    try:
        if is_yes_no:
            return tkmb.askyesno(title, message, parent=root)
        else:
            tkmb.showinfo(title, message, parent=root)
            return None
    finally:
        if created_root:
            root.destroy()


class Long_message_popup:
    def __init__(self, title, message, master, display_image=True, 
             word_index=None, char_def_index=None, word_click_callback=None,
             data_service=None, db=None, session_id=None, context=None,
             generate_explanation_callback=None):
        
        parent = getattr(master, 'root', master)
        self.long_popup = ctk.CTkToplevel(parent)
        self.long_popup.geometry("900x550")
        self.long_popup.title(title)
        self.long_popup.attributes("-topmost", True)

        self.debug = DebugLogger("Long_message_popup")
        self.debug.debug(f"Creating popup: title='{title}', context.active_node_id={context.active_node_id if context else None}, session_id={session_id}")
        
        if data_service:
            self.data_service = data_service
        elif db:
            self.data_service = PopupDataService(db)
        else:
            self.data_service = PopupDataService(None)
        
        self.db = db
        self.context = context or LearningContext(self.data_service.db if self.data_service else None)
        if session_id:
            self.context.active_session_id = session_id
        self.generate_explanation_callback = generate_explanation_callback
        self.active_node_id_before_popup = self.context.active_node_id if self.context else None
        self.control_panel = master if hasattr(master, 'root') else getattr(master, 'control_panel', None)

        ctk.CTkLabel(self.long_popup, text=title, font=("Mengshen-Handwritten", 24, "bold")).pack(pady=(5, 5))
        
        content_frame = ctk.CTkFrame(self.long_popup, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        if display_image:
            try:
                img_num = random.randint(1, 5)
                img_path = os.path.join(repo_folder, ".misc", "long_response", f"{img_num}.png")
                img = Image.open(img_path)
                max_size = (150, 150)
                scale = min(max_size[0]/img.size[0], max_size[1]/img.size[1])
                photo = ctk.CTkImage(img, size=(int(img.size[0]*scale), int(img.size[1]*scale)))
                img_label = ctk.CTkLabel(content_frame, image=photo, text="")
                img_label.image = photo
                img_label.pack(side="left", padx=5, pady=0)
            except Exception:
                pass

        text_panel_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        text_panel_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        input_frame = ctk.CTkFrame(text_panel_frame, fg_color="transparent")
        input_frame.pack(side="top", fill="x", padx=5, pady=(0,5))

        self.input_box = ctk.CTkTextbox(input_frame, wrap="word", font=("Mengshen-Handwritten", 16), height=3)
        self.input_box.insert("1.0", message)
        self.input_box.configure(state="normal")
        self.input_box.pack(side="left", fill="both", expand=True, padx=(0,5))

        self.think_component = ThinkBox(input_frame)
        self.think_component.pack(side="left", fill="both", expand=True, padx=(5,0))

        self.text_box = ctk.CTkTextbox(text_panel_frame, wrap="word", font=("Mengshen-Handwritten", 20))
        self.text_box.insert("1.0", message)
        self.text_box.configure(state="disabled")
        self.text_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        self.lookup_panel = LookupPanel(text_panel_frame, word_index=word_index, char_def_index=char_def_index, 
                                         word_click_callback=word_click_callback,
                                         generate_explanation_callback=generate_explanation_callback,
                                         data_service=self.data_service,
                                         context=self.context)
        self.lookup_panel.pack(side="right", fill="y", padx=5, pady=5, ipadx=10, ipady=10)
        self.lookup_panel.pack_propagate(False)
        self.lookup_panel.configure(width=180)
        
        if lookup_cedict and extract_chinese_word_at_position:
            self.lookup_panel.bind_text_box(self.input_box)
            self.lookup_panel.bind_text_box(self.text_box)
            self.lookup_panel.bind_text_box(self.think_component.text_box)
        
        if self.data_service and self.data_service.db:
            chain_btn = ctk.CTkButton(self.long_popup, text="🔗 View Chain", width=100,
                                    command=self._view_chain)
            chain_btn.pack(side="bottom", pady=5)
        
        if self.data_service and self.data_service.db:
            self.debug.debug("Storing popup content as node...")
            self.store_as_content_node()
        self.long_popup.bind("<Control-d>", lambda e: self._debug_current_chain())

        if self.data_service and self.data_service.db and self.context.active_node_id:
            chain_frame = ctk.CTkFrame(self.long_popup, fg_color="transparent")
            chain_frame.pack(side="bottom", fill="x", padx=10, pady=5)
            
            chain_status = ctk.CTkLabel(chain_frame, 
                text=f"🔗 Current chain node: {self.context.active_node_id}", 
                font=ctk.CTkFont(size=10), 
                text_color="green")
            chain_status.pack(side="left", padx=5)
            
            view_chain_btn = ctk.CTkButton(chain_frame, text="View Chain", width=80, height=25,
                                          command=self._view_chain)
            view_chain_btn.pack(side="right", padx=5)

    def _generate_for_word(self, text, mode=None, context=None):
        original_mode = None
        if mode and self.control_panel:
            original_mode = self.control_panel.response_mode
            self.control_panel.response_mode = mode
        
        if self.data_service and self.data_service.db:
            use_context = context or self.context
            query_node_id = use_context.create_child_node(
                node_type='query',
                title=f"Query: {text}",
                content=text,
                metadata={"source": "clipboard_query", "mode": mode or self.control_panel.response_mode}
            )
            print(f"📝 Created query node: {query_node_id} for text: {text}")
            
            if query_node_id:
                self.data_service.record_word_occurrence(text, query_node_id)
        
        try:
            explanation = self.get_explanation(text)
            if isinstance(explanation, str):
                explanation = (explanation,)
            self._show_explanation_popup(text, explanation, context=use_context)
        finally:
            if original_mode and self.control_panel:
                self.control_panel.response_mode = original_mode

    def _show_explanation_popup(self, text, explanation_generator, context=None):
        use_context = context or self.context
        
        print(f"🔗 Creating popup with context.active_node_id={use_context.active_node_id} for text='{text}'")
        
        response_popup = Long_message_popup(
            "Explanation",
            text,
            master=self.control_panel,
            display_image=(self.control_panel.response_mode.lower() != "lookup only"),
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service,
            context=use_context,
            generate_explanation_callback=self._generate_for_word
        )
        
        response_popup.start_streaming(explanation_generator, text)
        response_popup.show()

    def get_explanation(self, text):
        """Placeholder - should be overridden by integrated app."""
        def generator():
            yield f"Explanation for: {text}"
        return generator

    def start_streaming(self, generator, word_text):
        """Start streaming using unified async function."""
        def on_complete(full_text):
            self._on_stream_complete(word_text, full_text)
        
        stream_to_widgets(
            root=self.long_popup,
            generator=generator,
            text_widget=self.text_box,
            think_widget=self.think_component.text_box,
            on_complete=on_complete,
            show_thinking=self.control_panel.show_thinking if self.control_panel else True
        )

    def _on_stream_complete(self, word, full_text):
        """Called when streaming finishes."""
        if self.context:
            self.context.create_child_node(
                node_type='response',
                content=full_text,
                title=f"Response to: {word}",
                metadata={"source": "ai_explanation"}
            )
        self._setup_save_button(word, full_text)

    def _setup_save_button(self, word, explanation_text):
        def save_logic():
            if self.control_panel and hasattr(self.control_panel, 'save_manager'):
                word_id = self.control_panel.save_manager.save_word_with_prompt(
                    word, 
                    explanation_text
                )
                if word_id:
                    print(f"✓ Word '{word}' saved successfully!")
            self.long_popup.destroy()
        
        self.add_button("💾 Save/Update word", save_logic)

    def _debug_current_chain(self):
        if not self.context or not self.context.active_node_id:
            self.store_as_content_node()
        
        if self.context and self.context.active_node_id and self.data_service and self.data_service.db:
            chain = self.data_service.db.get_chain(self.context.active_node_id)
            popup_message("Debug", f"Node {self.context.active_node_id} has chain length {len(chain)}", parent=self.long_popup)
            
    def add_button(self, text, command):
        btn = ctk.CTkButton(self.long_popup, text=text, command=command)
        btn.pack(side="bottom", expand=True, fill="x", pady=10, padx=10)
        return btn
    
    def store_as_content_node(self):
        self.debug.debug(f"Storing as content node: title={self.long_popup.title()}")
        
        if not self.data_service or not self.data_service.db:
            self.debug.warning("No data_service or db available")
            return
        
        title = self.long_popup.title()
        content = self.text_box.get("1.0", "end-1c")
        
        node_id = self.context.create_child_node(
            node_type='response',
            content=content,
            title=title,
            metadata={"source": "popup_display"}
        )
        self.debug.info(f"Stored as node {node_id}, active_node_id now {self.context.active_node_id}")
        
        if node_id:
            import re
            chinese_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', content))
            self.debug.debug(f"Found {len(chinese_words)} Chinese words in content")
            for word in chinese_words:
                self.debug.debug(f"  Recording occurrence: '{word}'")
                self.data_service.record_word_occurrence(word, node_id)
    
    def _view_chain(self):
        """Open chain viewer for this content."""
        if not self.data_service or not self.data_service.db:
            return
        
        if not self.context or not self.context.active_node_id:
            self.store_as_content_node()
        
        if self.context and self.context.active_node_id:
            from lib.chain_viewer import ChainViewer
            viewer = ChainViewer(
                self.long_popup, 
                self.data_service.db, 
                self.context.active_node_id,
                f"Chain for: {self.long_popup.title()}"
            )
            viewer.focus()
    
    def show(self):
        self.long_popup.focus_set()


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
            self.word_label.configure(text=word.get('content', ''))
            self.trans_label.configure(text=word.get('translation', ''))
            self.example_label.configure(text=f'"{word.get("example_sentence", "")}"' if word.get("example_sentence") else "")
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
        
        word_list = ", ".join([w.get('content', '') for w in self.last_words]) if self.last_words else ""
        if not word_list:
            set_widget_text(self.insight_text, "No words in database yet. Add some words first!")
            self.is_generating = False
            self.refresh_btn.configure(state="normal")
            return
        
        def generator():
            return self.ai.generate_response(
                f"Word Blossom Mode: {word_list}",
                self.control_panel.show_thinking if self.control_panel else True
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
        
        word_list = ", ".join([w.get('content', '') for w in self.last_words])
        
        def generator():
            return self.ai.generate_response(
                f"Summarize these words with Sparkle Notes Mode: {word_list}",
                self.control_panel.show_thinking if self.control_panel else True
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
    longpop = Long_message_popup("Test Long Popup", "This is a test of the long message popup.", master=panel, display_image=True)
    longpop.show()
    panel.show()