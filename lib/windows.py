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
# Reusable Components
# ======================

class LookupPanel(customtkinter.CTkFrame):
    """Reusable sidebar panel for CEDICT lookup with hover binding support."""
    def __init__(self, master, word_index=None, char_def_index=None, word_click_callback=None, **kwargs):
        super().__init__(master, fg_color=("gray85", "gray25"), corner_radius=8, **kwargs)
        self.word_index = word_index or {}
        self.char_def_index = char_def_index or {}
        self.last_looked_up_word = None
        self.tracked_text_widgets = []
        self.current_hovered_word = None
        self.word_click_callback = word_click_callback or self._default_word_click

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

    def _show_word_mode_popup(self, word):
        popup = customtkinter.CTkToplevel(self)
        popup.geometry("400x200")
        popup.title(f"Select Mode for '{word}'")
        popup.attributes("-topmost", True)
        
        customtkinter.CTkLabel(popup, text=f"Word: {word}", font=("Mengshen-Handwritten", 16, "bold")).pack(pady=(10, 5))
        customtkinter.CTkLabel(popup, text="Choose a mode:", font=("Mengshen-Handwritten", 12)).pack(pady=5)
        
        mode_var = customtkinter.StringVar(value=MODES[0])
        customtkinter.CTkOptionMenu(popup, values=MODES, variable=mode_var, font=("Mengshen-Handwritten", 11)).pack(pady=10, padx=20, fill="x")
        
        button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")
        customtkinter.CTkButton(button_frame, text="✓ Select", fg_color="green", command=lambda: [self.word_click_callback(word, mode_var.get()), popup.destroy()]).pack(side="left", padx=5, expand=True)
        customtkinter.CTkButton(button_frame, text="✕ Cancel", fg_color="#942626", command=popup.destroy).pack(side="left", padx=5, expand=True)

    def _default_word_click(self, word, selected_mode):
        message = f"Mode: {selected_mode}\nWord: {word}\n\n{self._format_lookup_text(word)}"
        Long_message_popup(f"{word} — {selected_mode}", message, master=self, display_image=True, word_index=self.word_index, char_def_index=self.char_def_index, word_click_callback=None).show()


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
    def __init__(self, app_callback=None, ai_client:OllamaClient=OllamaClient(), db=None): 
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme(os.path.join(current_folder, "theme.json"))

        self.ai = ai_client
        self.db = db
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
    def __init__(self, title, message, master, display_image=True, word_index=None, char_def_index=None, word_click_callback=None):
        parent = getattr(master, 'root', master)
        self.long_popup = customtkinter.CTkToplevel(parent)
        self.long_popup.geometry("900x400")
        self.long_popup.title(title)
        self.long_popup.attributes("-topmost", True)
        
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
        
        self.lookup_panel = LookupPanel(text_panel_frame, word_index=word_index, char_def_index=char_def_index, word_click_callback=word_click_callback)
        self.lookup_panel.pack(side="right", fill="y", padx=5, pady=5, ipadx=10, ipady=10)
        self.lookup_panel.pack_propagate(False)
        self.lookup_panel.configure(width=180)
        
        if lookup_cedict and extract_chinese_word_at_position:
            self.lookup_panel.bind_text_box(self.input_box)
            self.lookup_panel.bind_text_box(self.text_box)
            self.lookup_panel.bind_text_box(self.think_component.think_box)

    def add_button(self, text, command):
        btn = customtkinter.CTkButton(self.long_popup, text=text, command=command)
        btn.pack(side="bottom", pady=10)
        return btn
    def append_think(self, new_text):
        self.think_component.append_think(new_text)
    
    def append_text(self, new_text):
        self.text_box.configure(state="normal")
        self.text_box.insert("end", new_text)
        self.text_box.configure(state="disabled")
        self.text_box.see("end")
    
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