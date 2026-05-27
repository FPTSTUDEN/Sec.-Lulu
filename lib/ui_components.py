# lib/ui_components.py - Shared UI components

import customtkinter as ctk
import os
import tkinter as tk
import tkinter.messagebox as tkmb

# Import CEDICT functions if available
try:
    from lib.ccedict import lookup_cedict, extract_chinese_word_at_position, is_chinese_char
except ImportError:
    lookup_cedict = extract_chinese_word_at_position = is_chinese_char = None

# Global MODES list
MODES = ["Lookup Only", "Sparkle Notes", "Immersion Mode", "Word Blossom", "Sentence Whisper"]


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

    def append(self, text):
        """Append text (call from UI thread only)."""
        try:
            self.text_box.configure(state="normal")
            self.text_box.insert("end", text)
            self.text_box.configure(state="disabled")
            self.text_box.see("end")
        except:
            pass

    def clear(self):
        """Clear text (call from UI thread only)."""
        try:
            self.text_box.configure(state="normal")
            self.text_box.delete("1.0", "end")
            self.text_box.configure(state="disabled")
        except:
            pass

    def _toggle(self):
        self.think_visible = not self.think_visible
        if self.think_visible:
            self.text_box.pack(fill="both", expand=True)
            self.toggle_btn.configure(text="▲")
        else:
            self.text_box.pack_forget()
            self.toggle_btn.configure(text="▼")


class LookupPanel(ctk.CTkFrame):
    """Reusable sidebar panel for CEDICT lookup with hover binding support."""
    
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
        if not lookup_cedict: 
            return "CEDICT not available"
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
        """Default handler when no generate_explanation_callback is provided."""
        from lib.streaming_popup import StreamingPopup
        popup = StreamingPopup(
            word=word,
            master=self,
            chain_mgr=self.context,
            ai_client=None,
            mode=selected_mode,
            display_image=(selected_mode.lower() != "lookup only"),
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service
        )
        popup.focus()

    def _show_word_mode_popup(self, word, data_service=None, db=None, session_id=None):
        """Show word mode selection popup."""
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
        mode_menu = ctk.CTkOptionMenu(popup, values=MODES, variable=mode_var, font=("Mengshen-Handwritten", 11))
        mode_menu.pack(pady=10, padx=20, fill="x")
        
        button_frame = ctk.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")
        
        def on_select():
            selected_mode = mode_var.get()
            print(f"LookupPanel: Selected word '{word}' with mode '{selected_mode}'")
            
            if self.generate_explanation_callback:
                self.generate_explanation_callback(word, selected_mode, context=self.context)
            else:
                self.word_click_callback(word, selected_mode)
            
            popup.destroy()
        
        ctk.CTkButton(button_frame, text="✓ Select", fg_color="green", command=on_select).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(button_frame, text="✕ Cancel", fg_color="#942626", command=popup.destroy).pack(side="left", padx=5, expand=True)