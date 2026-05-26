#lib/windows.py
import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox as tkmb
import customtkinter
import os
import threading
from PIL import Image, ImageTk
import random
from datetime import datetime
from lib.sentence_explorer import SentenceExplorerFrame
from lib.debug_utils import DebugLogger
import time

MODES=["Lookup Only","Sparkle Notes","Immersion Mode", "Word Blossom", "Sentence Whisper"]

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
# Core Streaming Handlers
# ======================

def stream_ai_response(ai, prompt, display_thinking, on_think=None, on_chunk=None, on_complete=None):
    """Core streaming handler - yields chunks and routes thinking text."""
    try:
        full_response = ""
        for chunk in ai.generate_response(prompt, display_thinking):
            if chunk.startswith("__THINK__"):
                thinking_text = chunk[len("__THINK__"):]
                if on_think:
                    on_think(thinking_text)
            else:
                full_response += chunk
                if on_chunk:
                    on_chunk(chunk)
        if on_complete:
            on_complete(full_response)
        return full_response
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if on_chunk:
            on_chunk(error_msg)
        return error_msg

class StreamHandler:
    """Helper class to manage streaming updates to UI components."""
    def __init__(self, master, text_widget, think_widget, control_panel=None):
        self.master = master
        self.text_widget = text_widget
        self.think_widget = think_widget
        self.display_thinking = getattr(control_panel, 'show_thinking', False) if control_panel else False
    
    def append_text(self, text):
        """Thread-safe text append."""
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", text)
        self.text_widget.configure(state="disabled")
        self.text_widget.see("end")
    
    def set_text(self, text):
        """Thread-safe text replacement."""
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.configure(state="disabled")
    
    def append_think(self, text):
        """Thread-safe think append."""
        if self.think_widget:
            self.think_widget.configure(state="normal")
            self.think_widget.insert("end", text)
            self.think_widget.configure(state="disabled")
            self.think_widget.see("end")
    
    def clear_think(self):
        """Clear think widget."""
        if self.think_widget:
            self.think_widget.configure(state="normal")
            self.think_widget.delete("1.0", "end")
            self.think_widget.configure(state="disabled")
    
    def stream(self, ai, prompt, on_complete=None):
        """Start streaming response."""
        def generate():
            stream_ai_response(
                ai, prompt, self.display_thinking,
                on_think=lambda t: self.master.after(0, lambda: self.append_think(t)),
                on_chunk=lambda c: self.master.after(0, lambda: self.append_text(c)),
                on_complete=lambda _: self.master.after(0, on_complete) if on_complete else None
            )
        threading.Thread(target=generate, daemon=True).start()

# ======================
# Service Layer (DB Operations Decoupled from UI)
# ======================

class PopupDataService:
    """Encapsulates all DB operations for popups. Decouples UI from DB schema."""
    def __init__(self, db=None):
        self.db = db
    
    def save_word(self, word, translation, session_id=None):
        """Save word to database. Returns word_id or None if no DB."""
        if not self.db:
            return None
        
        word_id = self.db.add_word(word, translation, example="")
        if session_id:
            self.db.add_word_to_session(session_id, word_id)
        return word_id
    
    def save_explanation_as_content(self, title, content, session_id=None, parent_node_id=None, metadata=None):
        """Store explanation as content node. Returns node_id or None if no DB."""
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
        """Record where a word appears in content. Requires DB."""
        if not self.db or not content_node_id:
            return
        
        word_id = self.db.get_word_id(word)
        if word_id:
            self.db.record_word_occurrence(
                word_id=word_id,
                content_node_id=content_node_id,
                position_start=position_start,
                position_end=position_end or len(word),
                context_before="",
                context_after=""
            )
    
    def get_active_session_id(self):
        """Get current active session ID, or None if no session or no DB."""
        if not self.db:
            return None
        active = self.db.get_active_session()
        return active['session_id'] if active else None
    
    def word_exists(self, word):
        """Check if word already exists in database."""
        if not self.db:
            return False
        return self.db.get_word_id(word) is not None


class TranslationDialog:
    """Modal dialog to prompt user for translation confirmation/editing."""
    def __init__(self, master, word, suggested_translation=""):
        self.result = None
        self.dialog = customtkinter.CTkToplevel(master)
        self.dialog.geometry("500x250")
        self.dialog.title(f"Confirm Translation: {word}")
        self.dialog.attributes("-topmost", True)
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.grab_set()
        
        # Word display
        customtkinter.CTkLabel(
            self.dialog, 
            text=f"Word: {word}", 
            font=("Mengshen-Handwritten", 18, "bold")
        ).pack(pady=(10, 5))
        
        # Translation label
        customtkinter.CTkLabel(
            self.dialog,
            text="Translation (edit if needed):",
            font=("Mengshen-Handwritten", 12)
        ).pack(pady=(5, 2))
        
        # Translation text box
        self.translation_box = customtkinter.CTkTextbox(
            self.dialog,
            wrap="word",
            font=("Mengshen-Handwritten", 12),
            height=4
        )
        self.translation_box.insert("1.0", suggested_translation)
        self.translation_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Button frame
        button_frame = customtkinter.CTkFrame(self.dialog, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        customtkinter.CTkButton(
            button_frame,
            text="✓ Save",
            fg_color="green",
            command=self._on_save
        ).pack(side="left", padx=5, expand=True, fill="x")
        
        customtkinter.CTkButton(
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
        """Show modal and return translation or None if cancelled."""
        self.dialog.focus_set()
        self.dialog.wait_window()
        return self.result


class PopupSaveManager:
    """Orchestrates word save workflow: extraction, validation, user confirmation."""
    def __init__(self, data_service, parent_widget=None):
        self.data_service = data_service
        self.parent_widget = parent_widget
    
    def extract_translation(self, explanation_text):
        """Extract translation from AI explanation text.
        
        Strategy: Take first sentence (up to . ! or ?), or first 150 chars.
        This is the suggested translation; user can edit it.
        """
        if not explanation_text:
            return ""
        
        # Try to extract first sentence
        import re
        sentences = re.split(r'[。！？\.\!\?]', explanation_text)
        first_sentence = sentences[0].strip() if sentences else ""
        
        # If too long, truncate
        if len(first_sentence) > 200:
            first_sentence = first_sentence[:197] + "..."
        
        return first_sentence
    
    def save_word_with_prompt(self, word, explanation_text, parent_node_id=None):
        """Save word: extract translation, prompt user to confirm, then save.
        
        Returns: word_id if saved, None if cancelled.
        """
        if not word or not word.strip():
            return None
        
        word = word.strip()
        
        # Check if word already exists
        if self.data_service.word_exists(word):
            tkmb.showinfo("Word Exists", f"'{word}' is already in your vocabulary.")
            return None
        
        # Extract suggested translation
        suggested = self.extract_translation(explanation_text)
        
        # Prompt user to confirm/edit translation
        dialog = TranslationDialog(
            self.parent_widget or tk._default_root,
            word,
            suggested
        )
        translation = dialog.show()
        
        if not translation:  # User cancelled
            return None
        
        # Get active session if available
        session_id = self.data_service.get_active_session_id()
        
        # Save to DB
        word_id = self.data_service.save_word(word, translation, session_id=session_id)
        
        # Record word occurrence in content node if available
        if word_id and parent_node_id:
            self.data_service.record_word_occurrence(word, parent_node_id)
        
        return word_id

# ======================
# Reusable Components
# ======================

class LookupPanel(customtkinter.CTkFrame):
    """Reusable sidebar panel for CEDICT lookup with hover binding support."""
    def __init__(self, master, word_index=None, char_def_index=None, word_click_callback=None, 
                 generate_explanation_callback=None, data_service=None, parent_node_id=None, **kwargs):
        super().__init__(master, fg_color=("gray85", "gray25"), corner_radius=8, **kwargs)
        self.word_index = word_index or {}
        self.char_def_index = char_def_index or {}
        self.last_looked_up_word = None
        self.tracked_text_widgets = []
        self.current_hovered_word = None
        self.word_click_callback = word_click_callback or self._default_word_click
        self.generate_explanation_callback = generate_explanation_callback
        self.data_service = data_service
        self.parent_node_id = parent_node_id

        lookup_title = customtkinter.CTkLabel(self, text="📖 Lookup", font=("Mengshen-Handwritten", 14, "bold"), text_color="orange")
        lookup_title.pack(pady=5)

        self.lookup_text = customtkinter.CTkTextbox(self, wrap="word", font=("Mengshen-Handwritten", 12), height=120)
        self.lookup_text.configure(state="disabled")
        self.lookup_text.pack(fill="both", expand=True, padx=5, pady=5)

    def bind_text_box(self, ctk_textbox):
        """Bind a CTkTextbox for hover lookup and click detection."""
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

    def _show_word_mode_popup(self, word, parent_node_id=None, data_service=None, db=None, session_id=None):
        """Show word mode popup with chain tracking"""
        
        # Use the current popup's node as parent if available
        if parent_node_id is None and hasattr(self, 'parent_node_id'):
            parent_node_id = self.parent_node_id
            print(f"🔗 Using LookupPanel parent_node_id: {parent_node_id}")
        
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
            
            # Create a content node for this word lookup if service available
            node_for_chain = None
            if service and service.db and parent_node_id:
                node_for_chain = service.save_explanation_as_content(
                    title=f"Lookup: {word}",
                    content=word,
                    session_id=session_id,
                    parent_node_id=parent_node_id,
                    metadata={"source": "lookup_panel", "mode": mode_var.get()}
                )
                # Record word occurrence
                if node_for_chain:
                    service.record_word_occurrence(word, node_for_chain, 0, len(word))
                    print(f"✓ Created lookup node {node_for_chain} with parent {parent_node_id}")
            
            # If generate_explanation_callback is available, use it for full AI response
            if self.generate_explanation_callback:
                # Pass the word, mode, AND the node we just created as parent
                self.generate_explanation_callback(word, mode_var.get(), parent_node_id=node_for_chain)
            else:
                # Fallback to static word click
                self.word_click_callback(word, mode_var.get())
            
            popup.destroy()
        
        ctk.CTkButton(button_frame, text="✓ Select", fg_color="green", command=on_select).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(button_frame, text="✕ Cancel", fg_color="#942626", command=popup.destroy).pack(side="left", padx=5, expand=True)
        
        # Chain info if available
        if parent_node_id and service and service.db:
            chain_info = ctk.CTkLabel(popup, text=f"🔗 This lookup will be linked to existing content (parent: {parent_node_id})", 
                                    font=ctk.CTkFont(size=10), text_color="green")
            chain_info.pack(pady=5)

class ThinkBox(customtkinter.CTkFrame):
    """Reusable collapsible thinking box component."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.think_visible = True

        think_header = customtkinter.CTkFrame(self, fg_color="transparent")
        think_header.pack(side="top", fill="x", pady=(0, 3))
        customtkinter.CTkLabel(think_header, text="🧠 Thinking", font=("Mengshen-Handwritten", 12, "bold")).pack(side="left")
        self.think_toggle_btn = customtkinter.CTkButton(think_header, text="▲", width=25, height=20, command=self._toggle_think_box)
        self.think_toggle_btn.pack(side="right", padx=(5, 0))

        self.think_box = customtkinter.CTkTextbox(self, wrap="word", font=("Mengshen-Handwritten", 12), height=3)
        self.think_box.configure(state="disabled")
        self.think_box.pack(fill="both", expand=True)

    def append_think(self, new_text):
        self.think_box.configure(state="normal")
        self.think_box.insert("end", new_text)
        self.think_box.configure(state="disabled")
        self.think_box.see("end")

    def _toggle_think_box(self):
        self.think_visible = not self.think_visible
        if self.think_visible:
            self.think_box.pack(fill="both", expand=True)
            self.think_toggle_btn.configure(text="▲")
        else:
            self.think_box.pack_forget()
            self.think_toggle_btn.configure(text="▼")

    def clear_think(self):
        self.think_box.configure(state="normal")
        self.think_box.delete("1.0", "end")
        self.think_box.configure(state="disabled")


class ControlPanel:
    def __init__(self, app_callback=None, ai_client:OllamaClient=OllamaClient(), db=None, data_service=None): 
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme(os.path.join(current_folder, "theme.json"))

        self.ai = ai_client
        self.db = db
        # Create or use provided data service for popup operations
        self.data_service = data_service or PopupDataService(db)
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

        # UI Setup (condensed)
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
        """Show a window to select a node and view its chain"""
        if not self.db:
            popup_message("No Database", "Database not available", parent=self.root)
            return
        
        # Get recent nodes
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
        """Show debug console window"""
        if self.debug_console and self.debug_console.winfo_exists():
            self.debug_console.lift()
            return
        
        self.debug_console = ctk.CTkToplevel(self.root)
        self.debug_console.title("Debug Console - Chain Events")
        self.debug_console.geometry("800x400")
        self.debug_console.attributes("-topmost", True)
        
        # Text widget for logs
        self.debug_text = ctk.CTkTextbox(self.debug_console, wrap="word", font=("Consolas", 10))
        self.debug_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self.debug_console, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(btn_frame, text="Clear", command=self._clear_debug_console).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Test Chain", command=self._test_chain_creation).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Show Last Node", command=self._show_last_node_chain).pack(side="left", padx=5)
        
        # Display existing logs
        for log in self.debug_logs:
            self.debug_text.insert("end", log + "\n")
        self.debug_text.see("end")
    
    def _clear_debug_console(self):
        self.debug_text.delete("1.0", "end")
        self.debug_logs.clear()
    
    def _test_chain_creation(self):
        """Create a test chain to verify functionality"""
        if not self.db:
            self._add_debug_log("❌ No database available for test")
            return
        
        self._add_debug_log("=" * 60)
        self._add_debug_log("🧪 TEST: Creating test chain")
        
        # Create root node
        root_id = self.db.create_content_node(
            node_type='raw_text',
            content="Test root content",
            title="Test Root",
            session_id=self.data_service.get_active_session_id()
        )
        self._add_debug_log(f"✓ Created root node: {root_id}")
        
        # Create child node
        child_id = self.db.create_content_node(
            node_type='response',
            content="Test child response",
            title="Test Child",
            parent_node_id=root_id,
            session_id=self.data_service.get_active_session_id()
        )
        self._add_debug_log(f"✓ Created child node: {child_id}")
        
        # Verify chain
        chain = self.db.get_content_chain(child_id)
        self._add_debug_log(f"Chain length: {len(chain)}")
        for i, node in enumerate(chain):
            self._add_debug_log(f"  [{i}] id={node['id']}, type={node['node_type']}")
        
        self._add_debug_log("=" * 60)
    def _show_last_node_chain(self):
        """Show the content chain for the last created node in debug console"""
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
        def task():
            self.update_ai_status("Loading...", "orange")
            if self.ai.manage_model("load"):
                self.update_ai_status("Loaded (VRAM Occupied)", "green")
        threading.Thread(target=task, daemon=True).start()

    def unload_ai(self):
        def task():
            self.update_ai_status("Unloading...", "orange")
            if self.ai.manage_model("unload"):
                self.update_ai_status("Unloaded (VRAM Free)", "gray")
        threading.Thread(target=task, daemon=True).start()

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
        """Create a new learning session from ControlPanel."""
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
        """End the current active session from ControlPanel."""
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
        """Update session status display in ControlPanel."""
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
        """Show all sessions from ControlPanel."""
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
        """Show words in a specific session."""
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
        """Get the current chain context for new lookups/responses"""
        active_session = self.db.get_active_session() if self.db else None
        return {
            "db": self.db,
            "session_id": active_session['session_id'] if active_session else None,
            "parent_node_id": self.current_response_node_id if hasattr(self, 'current_response_node_id') else None
        }

    def store_generated_response(self, user_query: str, ai_response: str, mode: str):
        """Store AI response as a content node"""
        if not self.data_service or not self.data_service.db:
            return None
        
        # Get current session
        session_id = self.data_service.get_active_session_id()
        
        # Get parent node (the query that triggered this)
        parent_node_id = None
        if hasattr(self, 'last_query_node_id'):
            parent_node_id = self.last_query_node_id
        
        # Create response node
        node_id = self.data_service.save_explanation_as_content(
            title=f"AI Response to: {user_query[:50]}",
            content=ai_response,
            session_id=session_id,
            parent_node_id=parent_node_id
        )
        
        self.current_response_node_id = node_id
        return node_id
    def show(self):
        self.root.mainloop()

    def cancel(self):
        self.done = True
        self.root.destroy()


def popup_message(title, message, is_yes_no=False, parent=None):
    """Show popup message. Returns bool if is_yes_no=True."""
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
             data_service=None, db=None, session_id=None, parent_node_id=None,
             generate_explanation_callback=None):
        """
        Args:
            data_service: PopupDataService instance (recommended over raw db param)
            db: (deprecated) Use data_service instead. Kept for backwards compatibility.
            session_id: Active session ID (passed to data_service for word saves)
            parent_node_id: Parent content node ID (for content chain)
            generate_explanation_callback: Function to call for generating explanations (for chained popups)
                Expected signature: callback(word, mode) -> streams response to new popup
        """
        parent = getattr(master, 'root', master)
        self.long_popup = customtkinter.CTkToplevel(parent)
        self.long_popup.geometry("900x550")  # Increased height for button visibility
        self.long_popup.title(title)
        self.long_popup.attributes("-topmost", True)

        self.debug = DebugLogger("Long_message_popup")
        self.debug.debug(f"Creating popup: title='{title}', parent_node_id={parent_node_id}, session_id={session_id}")
        
        # Support both new (data_service) and old (db) API; prefer data_service
        if data_service:
            self.data_service = data_service
        elif db:
            self.data_service = PopupDataService(db)
        else:
            self.data_service = PopupDataService(None)
        
        self.db = db  # Keep for backward compatibility
        self.session_id = session_id
        self.parent_node_id = parent_node_id
        self.current_node_id = None
        self.generate_explanation_callback = generate_explanation_callback
        self.current_query_node_id = None  # Track current query node
        self.current_response_node_id = None  # Track current response node
        self.control_panel = master if hasattr(master, 'root') else getattr(master, 'control_panel', None)


        customtkinter.CTkLabel(self.long_popup, text=title, font=("Mengshen-Handwritten", 24, "bold")).pack(pady=(5, 5))
        
        content_frame = customtkinter.CTkFrame(self.long_popup, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        if display_image:
            try:
                img_num = random.randint(1, 5)
                img_path = os.path.join(repo_folder, ".misc", "long_response", f"{img_num}.png")
                img = Image.open(img_path)
                max_size = (150, 150)
                scale = min(max_size[0]/img.size[0], max_size[1]/img.size[1])
                photo = customtkinter.CTkImage(img, size=(int(img.size[0]*scale), int(img.size[1]*scale)))
                img_label = customtkinter.CTkLabel(content_frame, image=photo, text="")
                img_label.image = photo
                img_label.pack(side="left", padx=5, pady=0)
            except Exception:
                pass

        text_panel_frame = customtkinter.CTkFrame(content_frame, fg_color="transparent")
        text_panel_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        input_frame = customtkinter.CTkFrame(text_panel_frame, fg_color="transparent")
        input_frame.pack(side="top", fill="x", padx=5, pady=(0,5))

        self.input_box = customtkinter.CTkTextbox(input_frame, wrap="word", font=("Mengshen-Handwritten", 16), height=3)
        self.input_box.insert("1.0", message)
        self.input_box.configure(state="normal")
        self.input_box.pack(side="left", fill="both", expand=True, padx=(0,5))

        self.think_component = ThinkBox(input_frame)
        self.think_component.pack(side="left", fill="both", expand=True, padx=(5,0))

        self.text_box = customtkinter.CTkTextbox(text_panel_frame, wrap="word", font=("Mengshen-Handwritten", 20))
        self.text_box.insert("1.0", message)
        self.text_box.configure(state="disabled")
        self.text_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        self.lookup_panel = LookupPanel(text_panel_frame, word_index=word_index, char_def_index=char_def_index, 
                                         word_click_callback=word_click_callback,
                                         generate_explanation_callback=generate_explanation_callback,
                                         data_service=self.data_service,
                                         parent_node_id=parent_node_id)
        self.lookup_panel.pack(side="right", fill="y", padx=5, pady=5, ipadx=10, ipady=10)
        self.lookup_panel.pack_propagate(False)
        self.lookup_panel.configure(width=180)
        
        if lookup_cedict and extract_chinese_word_at_position:
            self.lookup_panel.bind_text_box(self.input_box)
            self.lookup_panel.bind_text_box(self.text_box)
            self.lookup_panel.bind_text_box(self.think_component.think_box)
        
        if self.data_service and self.data_service.db:
            chain_btn = ctk.CTkButton(self.long_popup, text="🔗 View Chain", width=100,
                                    command=self._view_chain)
            chain_btn.pack(side="bottom", pady=5)
        
        if self.data_service and self.data_service.db:
            self.debug.debug("Storing popup content as node...")
            node_id = self.store_as_content_node()
            if node_id:
                self.debug.info(f"Popup stored as node {node_id}")
                self.debug.debug(f"Chain for node {node_id}:")
                # Print chain from DB
                if self.data_service.db:
                    self.data_service.db.debug_print_chain(node_id)
            else:
                self.debug.warning("Failed to store popup as content node")
        self.long_popup.bind("<Control-d>", lambda e: self._debug_current_chain())

        if self.data_service and self.data_service.db and parent_node_id:
            chain_frame = ctk.CTkFrame(self.long_popup, fg_color="transparent")
            chain_frame.pack(side="bottom", fill="x", padx=10, pady=5)
            
            chain_status = ctk.CTkLabel(chain_frame, 
                text=f"🔗 Chained to parent: {parent_node_id}", 
                font=ctk.CTkFont(size=10), 
                text_color="green")
            chain_status.pack(side="left", padx=5)
            
            view_chain_btn = ctk.CTkButton(chain_frame, text="View Chain", width=80, height=25,
                                          command=self._view_chain)
            view_chain_btn.pack(side="right", padx=5)

    def _generate_for_word(self, text, mode=None, parent_node_id=None):
        """Generate explanation for a word and display in popup.
        
        Args:
            text: The word to explain
            mode: (optional) Response mode
            parent_node_id: Parent content node ID for chain tracking
        """
        # Temporarily set control panel response mode if specified
        original_mode = None
        if mode and self.control_panel:
            original_mode = self.control_panel.response_mode
            self.control_panel.response_mode = mode
        
        # Create a query node for this lookup
        query_node_id = None
        if self.data_service and self.data_service.db:
            # Store the query as a content node
            query_node_id = self.data_service.save_explanation_as_content(
                title=f"Query: {text}",
                content=text,
                session_id=self.data_service.get_active_session_id(),
                parent_node_id=parent_node_id,
                metadata={"source": "clipboard_query", "mode": mode or self.control_panel.response_mode}
            )
            self.current_query_node_id = query_node_id
            print(f"📝 Created query node: {query_node_id} for text: {text}")
            
            # Record word occurrence
            if query_node_id:
                self.data_service.record_word_occurrence(text, query_node_id, 0, len(text))
        
        try:
            explanation = self.get_explanation(text)
            # Wrap string explanation in a generator if needed
            if isinstance(explanation, str):
                explanation = (explanation,)
            
            # Pass the query node as parent for the response
            self._show_explanation_popup(text, explanation, parent_node_id=query_node_id)
        finally:
            # Restore original mode if we changed it
            if original_mode and self.control_panel:
                self.control_panel.response_mode = original_mode

    
    def _show_explanation_popup(self, text, explanation_generator, parent_node_id=None):
        """Handles the streaming update of the popup UI."""
        
        # Get parent node ID - use passed param or from control panel
        effective_parent_id = parent_node_id or getattr(self.control_panel, 'current_response_node_id', None)
        
        print(f"🔗 Creating popup with parent_node_id={effective_parent_id} for text='{text}'")
        
        response_popup = Long_message_popup(
            "Explanation",
            text,
            master=self.control_panel,
            display_image=(self.control_panel.response_mode.lower() != "lookup only"),
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service,
            session_id=self.data_service.get_active_session_id() if self.data_service else None,
            parent_node_id=effective_parent_id,  # Now using the query node as parent!
            generate_explanation_callback=self._generate_for_word
        )
        
        def stream_thread():
            full_explanation = ""
            try:
                for chunk in explanation_generator:
                    # Route thinking-marked chunks to the think box
                    if isinstance(chunk, str) and chunk.startswith("__THINK__"):
                        thinking = chunk[len("__THINK__"):]
                        full_explanation += thinking
                        self.control_panel.root.after(0, lambda t=thinking: response_popup.append_think(t))
                    else:
                        full_explanation += chunk
                        # Update the UI on the main thread
                        self.control_panel.root.after(0, lambda c=chunk: response_popup.append_text(c))

                # Once finished, enable the save button with PopupSaveManager
                self.control_panel.root.after(0, lambda: self._setup_save_button(response_popup, text, full_explanation))
                
                # Debug: Print the chain after popup is created
                if self.data_service and self.data_service.db and response_popup.current_node_id:
                    print(f"\n🔗 CHAIN DEBUG for response node {response_popup.current_node_id}:")
                    self.data_service.db.debug_print_chain(response_popup.current_node_id)
            except Exception as e:
                print(f"Streaming error: {e}")

        threading.Thread(target=stream_thread, daemon=True).start()
        response_popup.show()

    def _debug_current_chain(self):
        """Debug the current popup's chain"""
        if not self.current_node_id:
            self.store_as_content_node()
        
        if self.current_node_id and self.data_service and self.data_service.db:
            self.data_service.db.debug_print_chain(self.current_node_id)
            
            # Show message
            popup_message("Debug", f"Chain info printed to console for node {self.current_node_id}", parent=self.long_popup)
            
    def add_button(self, text, command):
        """Add button to popup with proper layout (visible at bottom)."""
        btn = customtkinter.CTkButton(self.long_popup, text=text, command=command)
        btn.pack(side="bottom", expand=True, fill="x", pady=10, padx=10)
        return btn
    def append_think(self, new_text):
        self.think_component.append_think(new_text)
    
    def append_text(self, new_text):
        self.text_box.configure(state="normal")
        self.text_box.insert("end", new_text)
        self.text_box.configure(state="disabled")
        self.text_box.see("end")
    def store_as_content_node(self):
        """Store this popup's content as a content node in the database"""
        self.debug.debug(f"Storing as content node: title={self.long_popup.title()}")
        
        if not self.data_service or not self.data_service.db:
            self.debug.warning("No data_service or db available")
            return None
        
        node_type = 'response'
        title = self.long_popup.title()
        content = self.text_box.get("1.0", "end-1c")
        self.debug.debug(f"Content length: {len(content)} chars")
        
        node_id = self.data_service.save_explanation_as_content(
            title=title,
            content=content,
            session_id=self.session_id,
            parent_node_id=self.parent_node_id
        )
        self.current_node_id = node_id
        self.lookup_panel.parent_node_id = node_id  # Update lookup panel with new node ID for word occurrence tracking
        self.debug.info(f"Stored as node {node_id}, parent was {self.parent_node_id}")
        
        # Record word occurrences in content
        if node_id:
            import re
            chinese_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', content))
            self.debug.debug(f"Found {len(chinese_words)} Chinese words in content")
            for word in chinese_words:
                self.debug.debug(f"  Recording occurrence: '{word}'")
                self.data_service.record_word_occurrence(word, node_id)
        
        return node_id
    
    def _view_chain(self):
        """Open chain viewer for this content"""
        if not self.data_service or not self.data_service.db:
            return
        
        if not self.current_node_id:
            # Store as node first
            self.store_as_content_node()
        
        if self.current_node_id:
            from lib.chain_viewer import ChainViewer
            viewer = ChainViewer(self.long_popup, self.data_service.db, self.current_node_id, 
                                f"Chain for: {self.long_popup.title()}")
            viewer.focus()
    def show(self):
        self.long_popup.focus_set()


import customtkinter as ctk


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
            next_date = self.reviewer.review_current(quality)
            tkmb.showinfo("Review Complete", f"Next review: {next_date}")
            self._update_display()

    def _prev_word(self):
        if self.reviewer.current_index > 0:
            self.reviewer.current_index -= 1
            self._update_display()

    def _next_word(self):
        if self.reviewer.next_word():
            self._update_display()


# In windows.py, modify HomeFrame.__init__:

class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, ai_client, db, control_panel=None, 
                 word_index=None, char_def_index=None, **kwargs):
        super().__init__(master, **kwargs)
        self.ai = ai_client
        self.db = db
        self.control_panel = control_panel
        self.is_generating = False
        
        # Use passed indices or load them
        self.word_index = word_index if word_index is not None else {}
        self.char_def_index = char_def_index if char_def_index is not None else {}
        
        # Only load if not provided
        if not self.word_index and not self.char_def_index:
            try:
                from lib.ccedict import load_cedict_entries
                _, self.word_index, _, self.char_def_index = load_cedict_entries("cedict_ts.u8")
            except Exception:
                pass
        
        # ... rest of __init__ remains the same
        
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
            self._set_text(self.insight_text, "❌ AI Client or Database not available")
            return

        try:
            self.last_words = self.db.get_recent_words(limit=3)
        except Exception as e:
            self.last_words = []
            print(f"Error reading recent words: {e}")

        self.is_generating = True
        self.refresh_btn.configure(state="disabled")
        self.summary_btn.configure(state="disabled")
        
        handler = StreamHandler(self, self.insight_text, self.think_challenge.think_box, self.control_panel)
        handler.set_text("Generating challenge...")
        handler.clear_think()
        
        word_list = ", ".join([w[1] for w in self.last_words]) if self.last_words else ""
        if not word_list:
            handler.set_text("No words in database yet. Add some words first!")
            self.is_generating = False
            self.refresh_btn.configure(state="normal")
            return
        
        def on_complete():
            self.is_generating = False
            self.refresh_btn.configure(state="normal")
            self.summary_btn.configure(state="normal")
        
        handler.stream(self.ai, f"Word Blossom Mode: {word_list}", on_complete)

    def generate_summary(self):
        if self.is_generating or not self.last_words:
            return

        self.is_generating = True
        self.refresh_btn.configure(state="disabled")
        
        handler = StreamHandler(self, self.summary_text, self.think_summary.think_box, self.control_panel)
        handler.set_text("Generating summary...")
        handler.clear_think()
        
        word_list = ", ".join([w[1] for w in self.last_words])
        
        def on_complete():
            self.is_generating = False
            self.refresh_btn.configure(state="normal")
        
        handler.stream(self.ai, f"Summarize these words with Sparkle Notes Mode: {word_list}", on_complete)

    def _set_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")


# In windows.py, modify the App.__init__ method:

# Add to windows.py - modifications

# In the App class __init__, add the import and new frame:

class App(ctk.CTk):
    def __init__(self, reviewer, ai_client=None, db=None, control_panel=None):
        super().__init__()
        self.reviewer = reviewer
        self.ai_client = ai_client
        self.db = db
        self.control_panel = control_panel
        self.title("Vocabulary App")
        self.geometry("800x550")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Load CEDICT indices at App level
        self.word_index = {}
        self.char_def_index = {}
        try:
            from lib.ccedict import load_cedict_entries
            _, self.word_index, _, self.char_def_index = load_cedict_entries("cedict_ts.u8")
        except Exception as e:
            print(f"Could not load CEDICT: {e}")

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="VocabMaster", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20)
        ctk.CTkButton(self.sidebar, text="Home", command=lambda: self.show_frame("home")).grid(row=1, column=0, padx=20, pady=10)
        ctk.CTkButton(self.sidebar, text="Review", command=lambda: self.show_frame("review")).grid(row=2, column=0, padx=20, pady=10)
        ctk.CTkButton(self.sidebar, text="📖 Sentence Explorer", 
                      command=lambda: self.show_frame("explorer")).grid(row=3, column=0, padx=20, pady=10)

        # Frames
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
    longpop = Long_message_popup("Test Long Popup", "This is a test of the long message popup. It should display this text and an image if enabled.", master=panel, display_image=True)
    longpop.show()
    panel.show()