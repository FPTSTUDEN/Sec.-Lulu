import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox as tkmb
import customtkinter
import os
import threading
from PIL import Image, ImageTk
import random

MODES=["Lookup Only","Sparkle Notes","Immersion Mode", "Word Blossom", "Sentence Whisper"]

# from lib.localai import OllamaClient
current_folder = os.path.dirname(os.path.abspath(__file__))
repo_folder = os.path.dirname(current_folder)
# print(f"Current folder: {current_folder}")
# print(f"Parent folder: {repo_folder}")
os.chdir(repo_folder)
try:
    from lib.localai import OllamaClient
except ImportError as e:
    from localai import OllamaClient
    print(f"Error importing OllamaClient: {e}")
try:
    from lib.ccedict import lookup_cedict, extract_chinese_word_at_position, is_chinese_char
except ImportError:
    # Fallback if ccedict module is not available
    lookup_cedict = None
    extract_chinese_word_at_position = None
    is_chinese_char = None
# customtkinter.FontManager.load_font(os.path.join(current_folder, "Mengshen-HanSerif.ttf"))

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
        self.current_hovered_word = None  # Track the currently hovered word
        # If caller did not provide a callback, use the default long-response popup
        if word_click_callback is None:
            self.word_click_callback = self._default_word_click
        else:
            self.word_click_callback = word_click_callback

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
                # Use press/release to detect short clicks (avoid triggering on drags)
                underlying.bind("<ButtonPress-1>", lambda e: self._on_button_press(e))
                underlying.bind("<ButtonRelease-1>", lambda e: self._on_button_release(e))
        except Exception as e:
            pass

    def _on_text_motion(self, event):
        """Handle mouse motion over text box - perform lookup on Chinese words."""
        try:
            text_widget = event.widget
            index = text_widget.index(f"@{event.x},{event.y}")
            if not index:
                return

            line, col = map(int, index.split("."))
            text_content = text_widget.get("1.0", "end-1c")
            lines = text_content.split("\n")
            abs_pos = sum(len(lines[i]) + 1 for i in range(line - 1)) + col

            if abs_pos >= len(text_content):
                return

            if abs_pos > 0 and not is_chinese_char(text_content[abs_pos]):
                if is_chinese_char(text_content[abs_pos - 1]):
                    abs_pos = abs_pos - 1

            word, start_pos, end_pos = extract_chinese_word_at_position(text_content, abs_pos, self.word_index)

            if word and word != self.last_looked_up_word:
                self.last_looked_up_word = word
                self.current_hovered_word = word  # Track the hovered word
                self._update_lookup_panel(word)
        except Exception:
            pass

    def _on_text_leave(self):
        """Clear lookup panel when mouse leaves text box."""
        self.last_looked_up_word = None
        self._clear_lookup_panel()

    def _on_text_click(self, event):
        """Handle click on text box - show mode selection popup for clicked word."""
        try:
            if not self.current_hovered_word:
                return
            # Show word selection popup
            self._show_word_mode_popup(self.current_hovered_word)
        except Exception as e:
            print(f"Error handling text click: {e}")

    def _on_button_press(self, event):
        """Record press position/time for short-click detection."""
        try:
            widget = event.widget
            # store press info on the widget to avoid external state
            widget._last_press = (event.x, event.y, getattr(event, 'time', None))
        except Exception:
            pass

    def _on_button_release(self, event):
        """On release, check whether this was a short click (not a drag).
        If so, treat it as a click.
        """
        try:
            widget = event.widget
            press = getattr(widget, '_last_press', None)
            if not press:
                return
            px, py, ptime = press
            rx, ry = event.x, event.y
            rtime = getattr(event, 'time', None)
            dx = abs(rx - px)
            dy = abs(ry - py)
            dt = None
            if ptime is not None and rtime is not None:
                dt = rtime - ptime
            # thresholds: movement <= 5 pixels and time <= 500ms (if available)
            if dx <= 5 and dy <= 5 and (dt is None or dt <= 500):
                # treat as click
                self._on_text_click(event)
            # clear stored press
            widget._last_press = None
        except Exception:
            pass

    def _update_lookup_panel(self, word):
        """Update the lookup panel with CEDICT information for the given word."""
        self.lookup_text.configure(state="normal")
        self.lookup_text.delete("1.0", "end")
        formatted = self._format_lookup_text(word)
        self.lookup_text.insert("end", formatted)
        self.lookup_text.configure(state="disabled")

    def _clear_lookup_panel(self):
        """Clear the lookup panel."""
        self.lookup_text.configure(state="normal")
        self.lookup_text.delete("1.0", "end")
        self.lookup_text.configure(state="disabled")

    def _format_lookup_text(self, word):
        """Return a formatted lookup string for a word using CEDICT indices.

        Centralizes cedict parsing so callers can reuse the same formatting.
        """
        parts = []
        if not lookup_cedict:
            return "CEDICT not available"

        try:
            word_entry, char_matches = lookup_cedict(word, self.word_index, self.char_def_index)
            if word_entry:
                parts.append(f"📖 {word_entry.get('simplified','')}\n({word_entry.get('traditional','')})\n")
                for d in word_entry.get('definitions', []):
                    parts.append(f"• {d}")
            elif char_matches:
                parts.append("Character breakdown:")
                for char, entry in char_matches:
                    parts.append(f"• {char}: {entry.get('simplified','')}")
            else:
                parts.append("No match found")
        except Exception:
            return "No match found"

        return "\n".join(parts)

    def _show_word_mode_popup(self, word):
        """Show a popup with mode selection for the clicked word."""
        popup = customtkinter.CTkToplevel(self)
        popup.geometry("400x200")
        popup.title(f"Select Mode for '{word}'")
        popup.attributes("-topmost", True)
        
        # Title with the word
        title_label = customtkinter.CTkLabel(
            popup, 
            text=f"Word: {word}", 
            font=("Mengshen-Handwritten", 16, "bold")
        )
        title_label.pack(pady=(10, 5))
        
        # Mode selection label
        mode_label = customtkinter.CTkLabel(
            popup, 
            text="Choose a mode:", 
            font=("Mengshen-Handwritten", 12)
        )
        mode_label.pack(pady=5)
        
        # Mode dropdown
        mode_var = customtkinter.StringVar(value=MODES[0])
        mode_dropdown = customtkinter.CTkOptionMenu(
            popup,
            values=MODES,
            variable=mode_var,
            font=("Mengshen-Handwritten", 11)
        )
        mode_dropdown.pack(pady=10, padx=20, fill="x")
        
        # Button frame
        button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")
        
        def on_select():
            selected_mode = mode_var.get()
            if self.word_click_callback:
                self.word_click_callback(word, selected_mode)
            popup.destroy()
        
        select_btn = customtkinter.CTkButton(
            button_frame,
            text="✓ Select",
            fg_color="green",
            command=on_select
        )
        select_btn.pack(side="left", padx=5, expand=True)
        
        cancel_btn = customtkinter.CTkButton(
            button_frame,
            text="✕ Cancel",
            fg_color="#942626",
            command=popup.destroy
        )
        cancel_btn.pack(side="left", padx=5, expand=True)

    def _default_word_click(self, word, selected_mode):
        """Default callback: open a Long_message_popup showing lookup + selected mode."""
        try:
            header = f"Mode: {selected_mode}\nWord: {word}\n\n"
            body = self._format_lookup_text(word)
            message = header + body
            popup = Long_message_popup(f"{word} — {selected_mode}", message, master=self, display_image=True, word_index=self.word_index, char_def_index=self.char_def_index, word_click_callback=None)
            popup.show()
        except Exception as e:
            print(f"Error opening default long popup: {e}")


class ThinkBox(customtkinter.CTkFrame):
    """Reusable collapsible thinking box component."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.think_visible = True

        think_header = customtkinter.CTkFrame(self, fg_color="transparent")
        think_header.pack(side="top", fill="x", pady=(0, 3))

        think_label = customtkinter.CTkLabel(think_header, text="🧠 Thinking", font=("Mengshen-Handwritten", 12, "bold"))
        think_label.pack(side="left")

        self.think_toggle_btn = customtkinter.CTkButton(think_header, text="▲", width=25, height=20, command=self._toggle_think_box)
        self.think_toggle_btn.pack(side="right", padx=(5, 0))

        self.think_box = customtkinter.CTkTextbox(self, wrap="word", font=("Mengshen-Handwritten", 12), height=3)
        self.think_box.insert("1.0", "")
        self.think_box.configure(state="disabled")
        self.think_box.pack(fill="both", expand=True)

    def append_think(self, new_text):
        """Thread-safe way to add thinking text to the think box."""
        try:
            self.think_box.configure(state="normal")
            self.think_box.insert("end", new_text)
            self.think_box.configure(state="disabled")
            self.think_box.see("end")
        except Exception:
            pass

    def _toggle_think_box(self):
        """Toggle visibility of the thinking box."""
        self.think_visible = not self.think_visible
        if self.think_visible:
            self.think_box.pack(fill="both", expand=True)
            self.think_toggle_btn.configure(text="▲")
        else:
            self.think_box.pack_forget()
            self.think_toggle_btn.configure(text="▼")

    def clear_think(self):
        """Clear the think box content."""
        self.think_box.configure(state="normal")
        self.think_box.delete("1.0", "end")
        self.think_box.configure(state="disabled")



class ControlPanel:
    def __init__(self, app_callback=None, ai_client:OllamaClient=OllamaClient()): 
        # ctk.set_default_color_theme("green")
        # theme from theme.json
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme(os.path.join(current_folder, "theme.json"))

        self.ai = ai_client
        # app_callback is a function passed from your main script to launch App()
        self.ai_opened = True  # Assume AI is loaded at start, can be changed based on actual state
        self.opened = False
        self.done = False
        self.app_callback = app_callback
        self.generate_callback = None  # Callback to generate explanation for clipboard text
        self.mode_index = 1
        self.response_mode = MODES[self.mode_index]
        self.current_clipboard_text = ""  # Store the actual clipboard text
        self.long_clipboard_warning = False
        self.thinking_enabled = getattr(self.ai, "think", False)
        self.show_thinking = True
        
        self.root = ctk.CTk()
        self.root.title("Monitor")
        self.root.resizable(width=True, height=True)
        self.root.wm_attributes("-topmost", True)
        self.status_text = "Unknown"

        # --- Top line: status + clipboard ---
        self.top_line_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.top_line_frame.pack(side="top", fill="x", padx=10, pady=5)

        self.top_line_label = ctk.CTkLabel(
            self.top_line_frame,
            text="AI Unknown, 📋 (No clipboard text)",
            text_color="gray",
            anchor="w",
            justify="left",
            cursor="hand2"
        )
        self.top_line_label.pack(side="left", fill="x", expand=True)
        self.top_line_label.bind("<Button-1>", self._on_clipboard_click)

        # Session context input (compact mode)
        self.session_context = ""
        try:
            self.session_entry = ctk.CTkEntry(self.top_line_frame, width=220)
            self.session_entry.insert(0, "")
            self.session_entry.pack(side="right", padx=(5,0))

            self.session_send = ctk.CTkButton(self.top_line_frame, text="💬", width=40, command=lambda: self._set_session_context())
            self.session_send.pack(side="right", padx=(5,0))
        except Exception:
            self.session_entry = None
            self.session_send = None

        self.top_line_font = tkfont.Font(font=self.top_line_label.cget("font"))

        # --- Buttons Frame ---
        self.buttons_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.buttons_frame.pack(side="top", fill="x", padx=10, pady=5)

        self.state_btn = ctk.CTkButton(
            self.buttons_frame,
            text="▶️",
            fg_color="green",
            width=50,
            command=self.toggle_state
        )
        self.state_btn.pack(side="left", padx=5)

        self.app_btn = ctk.CTkButton(
            self.buttons_frame,
            text="📱",
            width=50,
            command=self.open_app
        )
        self.app_btn.pack(side="left", padx=5)

        self.advanced_visible = False
        self.toggle_advanced_btn = ctk.CTkButton(
            self.buttons_frame,
            text="▼",
            width=50,
            command=self.toggle_advanced
        )
        self.toggle_advanced_btn.pack(side="left", padx=5)

        self.exit_btn = ctk.CTkButton(
            self.buttons_frame,
            text="❌",
            fg_color="#942626",
            hover_color="#731d1d",
            width=50,
            command=self.cancel
        )
        self.exit_btn.pack(side="left", padx=5)

        self.advanced_frame = ctk.CTkFrame(self.root, fg_color="transparent")

        self.ai_btn = ctk.CTkButton(
            self.advanced_frame,
            text="🤖 Unload",
            fg_color="#4a4a4a",
            command=self.toggle_ai
        )
        self.ai_btn.pack(side="top", fill="x", pady=5)

        self.think_btn = ctk.CTkButton(
            self.advanced_frame,
            text=f"🧠 {'On' if self.thinking_enabled else 'Off'}",
            fg_color="#4a4a4a",
            command=self.toggle_thinking
        )
        self.think_btn.pack(side="top", fill="x", pady=5)

        self.show_think_btn = ctk.CTkButton(
            self.advanced_frame,
            text=f"👁️ {'Show' if self.show_thinking else 'Hide'}",
            fg_color="#4a4a4a",
            command=self.toggle_show_thinking
        )
        self.show_think_btn.pack(side="top", fill="x", pady=5)

        self.mode_menu = ctk.CTkOptionMenu(
            self.advanced_frame,
            values=MODES,
            command=self.set_mode
        )
        self.mode_menu.set(self.response_mode)
        self.mode_menu.pack(side="top", fill="x", pady=5)

        self.root.bind("<Configure>", self._on_root_configure)
    def update_ai_status(self, status_text, color):
        """Thread-safe UI update for AI status"""
        self.status_text = status_text
        self.root.after(0, lambda: self._update_top_line(color=color))
    
    def update_clipboard_display(self, text, is_valid_chinese=False, too_long=False):
        """Update the clipboard display label. Thread-safe."""
        if too_long:
            self.current_clipboard_text = ""
            self.clipboard_is_chinese = False
            self.long_clipboard_warning = True
        else:
            self.current_clipboard_text = text
            self.clipboard_is_chinese = is_valid_chinese
            self.long_clipboard_warning = False
        self.root.after(0, lambda: self._update_top_line())

    def _set_session_context(self):
        try:
            if self.session_entry:
                self.session_context = self.session_entry.get()
                self.update_ai_status(f"Session set", "gray")
        except Exception:
            pass

    def _update_top_line(self, color=None):
        status_text = self.status_text or "Unknown"
        if getattr(self, 'long_clipboard_warning', False):
            clip_text = "(long text ignored)"
            icon = "⚠️"
        else:
            clip_text = self.current_clipboard_text or "(No clipboard text)"
            icon = "🔤" if getattr(self, 'clipboard_is_chinese', False) else "📋"
        base_text = f"AI {status_text}, {icon} "

        label_width = self.top_line_label.winfo_width() or self.top_line_frame.winfo_width()
        if label_width <= 0:
            self.top_line_label.configure(text=base_text + clip_text, text_color=color or "gray")
            return

        ellipsis = "..."
        available_pixels = max(label_width - self.top_line_font.measure(base_text + ellipsis) - 10, 0)
        clipped_text = clip_text
        if self.top_line_font.measure(clip_text) > available_pixels:
            clipped_text = ""
            for i in range(len(clip_text)):
                if self.top_line_font.measure(clip_text[:i + 1]) > available_pixels:
                    clipped_text = clip_text[:i] + ellipsis
                    break
            if not clipped_text:
                clipped_text = ellipsis

        self.top_line_label.configure(text=base_text + clipped_text, text_color=color or "gray")

    def _on_root_configure(self, event):
        self._update_top_line()
    
    def _on_clipboard_click(self, event):
        """Handle click on clipboard display - generate explanation."""
        if self.current_clipboard_text and self.generate_callback:
            try:
                self.generate_callback(self.current_clipboard_text)
            except Exception as e:
                tkmb.showerror("Error", f"Failed to generate explanation: {e}")
    def load_ai(self):
        """Calls the AI client to load the model into VRAM"""
        def task():
            self.update_ai_status("Loading...", "orange")
            if self.ai.manage_model("load"):
                self.update_ai_status("Loaded (VRAM Occupied)", "green")
        threading.Thread(target=task, daemon=True).start()
    def unload_ai(self):
        """Calls the AI client to clear VRAM"""
        def task():
            self.update_ai_status("Unloading...", "orange")
            if self.ai.manage_model("unload"):
                self.update_ai_status("Unloaded (VRAM Free)", "gray")
        threading.Thread(target=task, daemon=True).start()
    def toggle_ai(self):
        """Toggles between loading and unloading the AI model"""
        if self.ai_opened:
            self.unload_ai()
            self.ai_opened = False
            self.ai_btn.configure(text="🤖 Load", fg_color="#4a4a4a")
        else:
            self.load_ai()
            self.ai_opened = True
            self.ai_btn.configure(text="🤖 Unload", fg_color="#4a4a4a")

    def toggle_thinking(self):
        """Toggle the Ollama thinking option."""
        self.thinking_enabled = not self.thinking_enabled
        if hasattr(self.ai, 'think'):
            self.ai.think = self.thinking_enabled
        label = "🧠 On" if self.thinking_enabled else "🧠 Off"
        color = "green" if self.thinking_enabled else "#4a4a4a"
        self.think_btn.configure(text=label, fg_color=color)

    def toggle_show_thinking(self):
        """Toggle whether to show thinking in responses."""
        self.show_thinking = not self.show_thinking
        label = "👁️ Show" if self.show_thinking else "👁️ Hide"
        color = "green" if self.show_thinking else "#4a4a4a"
        self.show_think_btn.configure(text=label, fg_color=color)

    def toggle_state(self):
        """Switches between Start and Pause states"""
        self.opened = not self.opened
        if self.opened:
            self.state_btn.configure(text="⏸️", fg_color="orange")
            self.update_ai_status("Running", "green")
        else:
            self.state_btn.configure(text="▶️", fg_color="green")
            self.update_ai_status("Paused", "gray")
    def set_mode(self, mode):
        """Set the response mode from dropdown."""
        self.response_mode = mode
        print(f"Response Mode: {self.response_mode}")
    
    def toggle_advanced(self):
        """Toggle visibility of advanced options."""
        if self.advanced_visible:
            self.advanced_frame.pack_forget()
            self.toggle_advanced_btn.configure(text="▼")
            self.advanced_visible = False
            # Show compact session entry when advanced is collapsed
            try:
                if self.session_entry:
                    self.session_entry.pack(side="right", padx=(5,0))
                if self.session_send:
                    self.session_send.pack(side="right", padx=(5,0))
            except Exception:
                pass
        else:
            self.advanced_frame.pack(after=self.buttons_frame, side="top", fill="x", padx=10, pady=5)
            self.toggle_advanced_btn.configure(text="▲")
            self.advanced_visible = True
            # Hide compact session entry when advanced is expanded
            try:
                if self.session_entry:
                    self.session_entry.pack_forget()
                if self.session_send:
                    self.session_send.pack_forget()
            except Exception:
                pass
    def open_app(self):
        """Triggers the main App launch without blocking the control panel"""
        if self.app_callback:
            # Execute callback directly - should be thread-safe if properly designed
            # (e.g., launching in a separate thread internally)
            try:
                self.app_callback()
            except Exception as e:
                tkmb.showerror("Error", f"Failed to open app: {e}")

    def show(self):
        self.root.mainloop()

    def cancel(self):
        self.done = True
        self.root.destroy()
def popup_message(title, message):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    tkmb.showinfo(title, message)
    root.destroy()
class Long_message_popup:
    def __init__(self, title, message, master, display_image=True, word_index=None, char_def_index=None, word_click_callback=None):
        # master may be a ControlPanel (with .root) or a widget; determine parent for Toplevel
        parent = getattr(master, 'root', master)
        # Use Toplevel and link it to the parent
        self.long_popup = customtkinter.CTkToplevel(parent)
        self.long_popup.geometry("900x400")
        self.long_popup.title(title)
        
        # Ensure it stays on top
        self.long_popup.attributes("-topmost", True)
        
        title_label = customtkinter.CTkLabel(self.long_popup, text=title, font=("Mengshen-Handwritten", 24, "bold"))
        title_label.pack(pady=(5, 5))
        
        # Main content frame (image + text + side panel)
        content_frame = customtkinter.CTkFrame(self.long_popup, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        if display_image:
            # Add a random image (1.png-5.png) 
            img_num = random.randint(1, 5)
            try:
                img_path = os.path.join(repo_folder, ".misc", "long_response", f"{img_num}.png")
                img = Image.open(img_path)
                img_size = img.size
                max_size = (150, 150)
                scale_factor = min(max_size[0] / img_size[0], max_size[1] / img_size[1])
                new_size = (int(img_size[0] * scale_factor), int(img_size[1] * scale_factor))
                photo = customtkinter.CTkImage(img, size=new_size)
                img_label = customtkinter.CTkLabel(content_frame, image=photo, text="")
                img_label.image = photo
                img_label.pack(side="left", padx=5, pady=0)
            except Exception as e:
                print(f"Error loading image: {e}")

        # Text box and side panel container
        text_panel_frame = customtkinter.CTkFrame(content_frame, fg_color="transparent")
        text_panel_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        # Input and Thinking boxes above the main text area
        input_frame = customtkinter.CTkFrame(text_panel_frame, fg_color="transparent")
        input_frame.pack(side="top", fill="x", padx=5, pady=(0,5))

        self.input_box = customtkinter.CTkTextbox(input_frame, wrap="word", font=("Mengshen-Handwritten", 16), height=3)
        self.input_box.insert("1.0", message)
        self.input_box.configure(state="normal")
        self.input_box.pack(side="left", fill="both", expand=True, padx=(0,5))

        # Use reusable ThinkBox component
        self.think_component = ThinkBox(input_frame)
        self.think_component.pack(side="left", fill="both", expand=True, padx=(5,0))

        self.text_box = customtkinter.CTkTextbox(text_panel_frame, wrap="word", font=("Mengshen-Handwritten", 20))
        self.text_box.insert("1.0", message)
        self.text_box.configure(state="disabled")
        self.text_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Use reusable LookupPanel component
        self.lookup_panel = LookupPanel(text_panel_frame, word_index=word_index, char_def_index=char_def_index, word_click_callback=word_click_callback)
        self.lookup_panel.pack(side="right", fill="y", padx=5, pady=5, ipadx=10, ipady=10)
        self.lookup_panel.pack_propagate(False)
        self.lookup_panel.configure(width=180)
        
        # Bind hover events to all text boxes
        if lookup_cedict and extract_chinese_word_at_position:
            self.lookup_panel.bind_text_box(self.input_box)
            self.lookup_panel.bind_text_box(self.text_box)
            self.lookup_panel.bind_text_box(self.think_component.think_box)
    
    def _bind_hover_events(self):
        """(Deprecated - now handled by LookupPanel.bind_text_box())"""
        pass

    def append_think(self, new_text):
        """Thread-safe way to add thinking text to the think box (delegates to ThinkBox component)."""
        try:
            self.think_component.append_think(new_text)
        except Exception:
            pass
    
    def append_text(self, new_text):
        """Thread-safe way to add text to the box."""
        self.text_box.configure(state="normal")
        self.text_box.insert("end", new_text)
        self.text_box.configure(state="disabled")

        self.text_box.see("end") # Auto-scroll to bottom
    
    def show(self):
        # No mainloop here! Toplevel uses the master's loop.
        self.long_popup.focus_set()

    def add_button(self, text, command):
        btn = customtkinter.CTkButton(self.long_popup, text=text, command=command)
        btn.pack(pady=10)
import customtkinter as ctk


class ReviewFrame(ctk.CTkFrame):
    """Refactored from your original ReviewUI class"""
    def __init__(self, master, reviewer, **kwargs):
        super().__init__(master, **kwargs)
        self.reviewer = reviewer
        self._setup_ui()
        self._load_words()

    def _setup_ui(self):
        # Title
        self.title = ctk.CTkLabel(
            self, text="📚 Word Review", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title.pack(pady=10)
        
        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.pack()
        
        # Word card frame
        card = ctk.CTkFrame(self)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.word_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=36, weight="bold"), wraplength=400)
        self.word_label.pack(pady=(30, 10))
        
        self.trans_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=24), text_color="green")
        self.trans_label.pack(pady=10)
        
        self.example_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=14, slant="italic"), text_color="gray", wraplength=400)
        self.example_label.pack(pady=10)
        
        # Review buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        self.hard_btn = ctk.CTkButton(btn_frame, text="Hard", fg_color="orange", command=lambda: self._review("hard"))
        self.hard_btn.pack(side="left", padx=5, expand=True)
        
        self.good_btn = ctk.CTkButton(btn_frame, text="Good", fg_color="green", command=lambda: self._review("good"))
        self.good_btn.pack(side="left", padx=5, expand=True)

        # Navigation
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

class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, ai_client, db, control_panel=None, **kwargs):
        super().__init__(master, **kwargs)
        self.ai = ai_client
        self.db = db
        self.control_panel = control_panel
        self.is_generating = False
        
        # CEDICT indices
        self.word_index = {}
        self.char_def_index = {}
        try:
            from lib.ccedict import load_cedict_entries
            _, self.word_index, _, self.char_def_index = load_cedict_entries("cedict_ts.u8")
        except Exception:
            pass
        
        # Configure grid weights for flexibility
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Daily Challenge row
        self.grid_rowconfigure(2, weight=1) # Words Summary row

        # Title
        self.label = ctk.CTkLabel(self, text="Welcome Back", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.grid(row=0, column=0, pady=(20, 10), sticky="n")

        # --- Daily AI Challenge Section ---
        self.insight_card = ctk.CTkFrame(self, fg_color=("gray90", "gray15"))
        self.insight_card.grid(row=1, column=0, padx=40, pady=10, sticky="nsew")
        self.insight_card.grid_columnconfigure(0, weight=1)  # Main content fills
        self.insight_card.grid_columnconfigure(1, weight=0)  # Sidebar is fixed width
        self.insight_card.grid_rowconfigure(1, weight=1)

        self.insight_title = ctk.CTkLabel(self.insight_card, text="✨ Daily AI Challenge", font=ctk.CTkFont(weight="bold"))
        self.insight_title.grid(row=0, column=0, columnspan=2, pady=5)
        
        # Textbox set to sticky "nsew" to fill the card
        self.insight_text = ctk.CTkTextbox(self.insight_card, wrap="word", font=("Mengshen-Handwritten", 14), height=100)
        self.insight_text.configure(state="disabled")
        self.insight_text.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")
        
        # Reusable ThinkBox for challenge thinking
        self.think_challenge = ThinkBox(self.insight_card)
        self.think_challenge.grid(row=2, column=0, pady=5, padx=10, sticky="ew")
        
        # Reusable LookupPanel for challenge (side column)
        self.lookup_challenge = LookupPanel(self.insight_card, word_index=self.word_index, char_def_index=self.char_def_index)
        self.lookup_challenge.grid(row=1, column=1, rowspan=2, pady=10, padx=5, sticky="nsew")
        self.lookup_challenge.pack_propagate(False)
        self.lookup_challenge.configure(width=150)
        if lookup_cedict and extract_chinese_word_at_position:
            self.lookup_challenge.bind_text_box(self.insight_text)

        # --- Words Summary Section ---
        self.summary_card = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        self.summary_card.grid(row=2, column=0, padx=40, pady=10, sticky="nsew")
        self.summary_card.grid_columnconfigure(0, weight=1)  # Main content fills
        self.summary_card.grid_columnconfigure(1, weight=0)  # Sidebar is fixed width
        self.summary_card.grid_rowconfigure(1, weight=1)
        
        self.summary_title = ctk.CTkLabel(self.summary_card, text="📚 Words Summary", font=ctk.CTkFont(weight="bold"))
        self.summary_title.grid(row=0, column=0, columnspan=2, pady=5)
        
        self.summary_text = ctk.CTkTextbox(self.summary_card, wrap="word", font=("Mengshen-Handwritten", 12), height=100)
        self.summary_text.configure(state="disabled")
        self.summary_text.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")
        
        # Reusable ThinkBox for summary
        self.think_summary = ThinkBox(self.summary_card)
        self.think_summary.grid(row=2, column=0, pady=5, padx=10, sticky="ew")
        
        # Reusable LookupPanel for summary (side column)
        self.lookup_summary = LookupPanel(self.summary_card, word_index=self.word_index, char_def_index=self.char_def_index)
        self.lookup_summary.grid(row=1, column=1, rowspan=2, pady=10, padx=5, sticky="nsew")
        self.lookup_summary.pack_propagate(False)
        self.lookup_summary.configure(width=150)
        if lookup_cedict and extract_chinese_word_at_position:
            self.lookup_summary.bind_text_box(self.summary_text)

        # --- Buttons Frame ---
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=3, column=0, pady=20)

        self.refresh_btn = ctk.CTkButton(self.button_frame, text="New Challenge", command=self.generate_challenge)
        self.refresh_btn.pack(side="left", padx=5)

        self.summary_btn = ctk.CTkButton(self.button_frame, text="Generate Summary", 
                                         command=self.generate_summary, state="disabled")
        self.summary_btn.pack(side="left", padx=5)

        self.last_words = []
    def append_text(self, text, box):
        """Thread-safe way to append text to the box."""
        box.configure(state="normal")
        box.insert("end", text)
        box.configure(state="disabled")
        box.see("end")  # Auto-scroll to bottom

    def _set_text(self, box, text):
        """Thread-safe way to replace the entire box content."""
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.see("1.0")

    def generate_challenge(self):
        """Generate a vocabulary challenge using AI (streaming)"""
        if self.is_generating:
            tkmb.showwarning("In Progress", "Already generating. Please wait.")
            return

        if not self.ai or not self.db:
            self._set_text(self.insight_text, "❌ AI Client or Database not available")
            return

        # fetch words on main thread to avoid cross-thread DB usage
        try:
            self.last_words = self.db.get_recent_words(limit=3)
        except Exception as e:
            self.last_words = []
            print(f"Error reading recent words: {e}")

        self.is_generating = True
        self.refresh_btn.configure(state="disabled")
        self.summary_btn.configure(state="disabled")

        # Clear previous content and show generating message
        self.insight_text.configure(state="normal")
        self.insight_text.delete("1.0", "end")
        self.insight_text.insert("1.0", "Generating challenge...")
        self.insight_text.configure(state="disabled")
        
        # Clear thinking box
        self.think_challenge.clear_think()

        # Determine thinking display flag from control_panel
        display_thinking = False
        if self.control_panel:
            display_thinking = getattr(self.control_panel, 'show_thinking', False)

        def generate():
            try:
                if not self.last_words:
                    final_text = "No words in database yet. Add some words first!"
                    self.after(0, lambda text=final_text: self._set_text(self.insight_text, text))
                else:
                    word_list = ", ".join([w[1] for w in self.last_words])
                    prompt = f"Word Blossom Mode: {word_list}"

                    full_response = ""
                    for chunk in self.ai.generate_response(prompt, display_thinking):
                        # Route __THINK__ prefixed chunks to think box
                        if chunk.startswith("__THINK__"):
                            thinking_text = chunk[len("__THINK__"):]
                            self.after(0, lambda text=thinking_text: self.think_challenge.append_think(text))
                        else:
                            full_response += chunk
                            self.after(0, lambda text=chunk: self.append_text(text, self.insight_text))

                    self.after(0, lambda: self.summary_btn.configure(state="normal"))

            except Exception as e:
                error_msg = f"Error generating challenge: {str(e)}"
                self.after(0, lambda msg=error_msg: self._set_text(self.insight_text, msg))
            finally:
                self.is_generating = False
                self.after(0, lambda: self.refresh_btn.configure(state="normal"))

        threading.Thread(target=generate, daemon=True).start()

    def generate_summary(self):
        """Generate a summary of the words used in the challenge"""
        if self.is_generating or not self.last_words:
            return

        self.is_generating = True
        self.refresh_btn.configure(state="disabled")
        
        # Clear previous content and show generating message
        self._set_text(self.summary_text, "Generating summary...")
        
        # Clear thinking box
        self.think_summary.clear_think()

        # Determine thinking display flag from control_panel
        display_thinking = False
        if self.control_panel:
            display_thinking = getattr(self.control_panel, 'show_thinking', False)

        def generate():
            try:
                word_list = ", ".join([w[1] for w in self.last_words])
                prompt = f"Summarize these words with Sparkle Notes Mode: {word_list}"

                self.after(0, lambda: self._set_text(self.summary_text, "Generating summary..."))

                full_summary = ""
                for chunk in self.ai.generate_response(prompt, display_thinking):
                    # Route __THINK__ prefixed chunks to think box
                    if chunk.startswith("__THINK__"):
                        thinking_text = chunk[len("__THINK__"):]
                        self.after(0, lambda text=thinking_text: self.think_summary.append_think(text))
                    else:
                        full_summary += chunk
                        self.after(0, lambda text=chunk: self.append_text(text, self.summary_text))

            except Exception as e:
                error_msg = f"Error generating summary: {str(e)}"
                self.after(0, lambda msg=error_msg: self._set_text(self.summary_text, msg))
            finally:
                self.is_generating = False
                self.after(0, lambda: self.refresh_btn.configure(state="normal"))

        threading.Thread(target=generate, daemon=True).start()

class App(ctk.CTk):
    def __init__(self, reviewer, ai_client=None, db=None, control_panel=None):
        super().__init__()
        self.reviewer = reviewer
        self.ai_client = ai_client
        self.db = db
        self.control_panel = control_panel
        self.title("Vocabulary App")
        self.geometry("800x550")

        # Layout configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo = ctk.CTkLabel(self.sidebar, text="VocabMaster", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo.grid(row=0, column=0, padx=20, pady=20)

        self.btn_home = ctk.CTkButton(self.sidebar, text="Home", command=lambda: self.show_frame("home"))
        self.btn_home.grid(row=1, column=0, padx=20, pady=10)

        self.btn_review = ctk.CTkButton(self.sidebar, text="Review", command=lambda: self.show_frame("review"))
        self.btn_review.grid(row=2, column=0, padx=20, pady=10)

        # Initialize Frames
        self.frames = {}
        self.frames["home"] = HomeFrame(self, self.ai_client, self.db, control_panel=self.control_panel, fg_color="transparent")
        self.frames["review"] = ReviewFrame(self, self.reviewer, fg_color="transparent")

        self.show_frame("home")

    def show_frame(self, page_name):
        # Hide all - use list() to avoid "dictionary changed size during iteration"
        for frame in list(self.frames.values()):
            frame.grid_forget()
        # Show selected
        self.frames[page_name].grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

if __name__ == "__main__":
    popup_message("Test Message", "This is a test message to verify the popup_message function is working correctly.")
    panel=ControlPanel()
    longpop=Long_message_popup("Test Long Popup", "This is a test of the long message popup. It should display this text and an image if enabled.", master=panel, display_image=True)
    longpop.show()
    panel.show()
