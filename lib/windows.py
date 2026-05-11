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
    
    def update_clipboard_display(self, text, is_valid_chinese=False):
        """Update the clipboard display label. Thread-safe."""
        self.current_clipboard_text = text
        self.clipboard_is_chinese = is_valid_chinese
        self.root.after(0, lambda: self._update_top_line())

    def _update_top_line(self, color=None):
        status_text = self.status_text or "Unknown"
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
        else:
            self.advanced_frame.pack(after=self.buttons_frame, side="top", fill="x", padx=10, pady=5)
            self.toggle_advanced_btn.configure(text="▲")
            self.advanced_visible = True
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
    def __init__(self, title, message, master: ControlPanel, display_image=True, word_index=None, char_def_index=None):
        # Use Toplevel and link it to the master (ControlPanel)
        self.long_popup = customtkinter.CTkToplevel(master.root)
        self.long_popup.geometry("800x350")
        self.long_popup.title(title)
        
        # Store CEDICT indices for hover lookup
        self.word_index = word_index or {}
        self.char_def_index = char_def_index or {}
        self.last_looked_up_word = None
        
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
        
        self.text_box = customtkinter.CTkTextbox(text_panel_frame, wrap="word", font=("Mengshen-Handwritten", 20))
        self.text_box.insert("1.0", message)
        self.text_box.configure(state="disabled")
        self.text_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Side panel for Chinese word lookup results
        self.lookup_panel = customtkinter.CTkFrame(text_panel_frame, fg_color=("gray85", "gray25"), corner_radius=8)
        self.lookup_panel.pack(side="right", fill="y", padx=5, pady=5, ipadx=10, ipady=10)
        self.lookup_panel.pack_propagate(False)
        self.lookup_panel.configure(width=180)
        
        lookup_title = customtkinter.CTkLabel(self.lookup_panel, text="📖 Lookup", font=("Mengshen-Handwritten", 14, "bold"), text_color="orange")
        lookup_title.pack(pady=5)
        
        self.lookup_text = customtkinter.CTkTextbox(self.lookup_panel, wrap="word", font=("Mengshen-Handwritten", 12), height=120)
        self.lookup_text.configure(state="disabled")
        self.lookup_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Bind mouse motion to text box for hover lookup
        if lookup_cedict and extract_chinese_word_at_position:
            self._bind_hover_events()
    
    def _bind_hover_events(self):
        """Bind mouse motion events to the text box for hover-based lookup."""
        try:
            # Get the underlying Tkinter Text widget from CTkTextbox
            underlying_text = self.text_box._textbox
            underlying_text.bind("<Motion>", self._on_text_motion)
            underlying_text.bind("<Leave>", self._on_text_leave)
        except Exception as e:
            print(f"Error binding hover events: {e}")
    
    def _on_text_motion(self, event):
        """Handle mouse motion over text box - perform lookup on Chinese words."""
        try:
            # Get the underlying text widget
            text_widget = event.widget
            
            # Get the character index at mouse position
            index = text_widget.index(f"@{event.x},{event.y}")
            if not index:
                return
            
            # Extract line and column from index
            line, col = map(int, index.split("."))
            
            # Get the full text to search
            text_content = text_widget.get("1.0", "end-1c")
            
            # Convert line.col index to absolute position in text
            lines = text_content.split("\n")
            abs_pos = sum(len(lines[i]) + 1 for i in range(line - 1)) + col
            
            # Ensure we're within bounds
            if abs_pos >= len(text_content):
                return
            
            # Normalize position: Tkinter @x,y can land on the boundary AFTER a character.
            # If the character at abs_pos is not Chinese but the one before it is,
            # use abs_pos - 1 to start from the actual hovered character.
            if abs_pos > 0 and not is_chinese_char(text_content[abs_pos]):
                if is_chinese_char(text_content[abs_pos - 1]):
                    abs_pos = abs_pos - 1
            
            # Extract the Chinese word at this position
            word, start_pos, end_pos = extract_chinese_word_at_position(text_content, abs_pos, self.word_index)
            
            if word and word != self.last_looked_up_word:
                self.last_looked_up_word = word
                self._update_lookup_panel(word)
        except Exception as e:
            pass  # Silently ignore hover errors
    
    def _on_text_leave(self, event):
        """Clear lookup panel when mouse leaves text box."""
        self.last_looked_up_word = None
        self._clear_lookup_panel()
    
    def _update_lookup_panel(self, word):
        """Update the lookup panel with CEDICT information for the given word."""
        self.lookup_text.configure(state="normal")
        self.lookup_text.delete("1.0", "end")
        
        # Perform CEDICT lookup
        word_entry, char_matches = lookup_cedict(word, self.word_index, self.char_def_index)
        
        if word_entry:
            # Direct word match found
            simplified = word_entry.get("simplified", "")
            traditional = word_entry.get("traditional", "")
            pinyin = word_entry.get("pinyin", "")
            definitions = word_entry.get("definitions", [])
            
            # Format output
            output = f"词: {simplified}\n"
            if traditional != simplified:
                output += f"繁: {traditional}\n"
            output += f"拼: {pinyin}\n"
            if definitions:
                output += f"义: {'; '.join(definitions[:2])}"  # Show first 2 definitions
            
            self.lookup_text.insert("1.0", output)
        elif char_matches:
            # Character-level matches
            output = f"词组: {word}\n\n"
            for char, entry in char_matches[:3]:  # Show first 3 characters
                char_pinyin = entry.get("pinyin", "")
                char_defs = entry.get("definitions", [])
                output += f"{char}: {char_pinyin}\n"
                if char_defs:
                    output += f"  {char_defs[0][:30]}\n"
            self.lookup_text.insert("1.0", output)
        else:
            self.lookup_text.insert("1.0", f"未找到:\n{word}")
        
        self.lookup_text.configure(state="disabled")
    
    def _clear_lookup_panel(self):
        """Clear the lookup panel."""
        self.lookup_text.configure(state="normal")
        self.lookup_text.delete("1.0", "end")
        self.lookup_text.configure(state="disabled")
    
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
    def __init__(self, master, ai_client, db, **kwargs):
        super().__init__(master, **kwargs)
        self.ai = ai_client
        self.db = db
        self.is_generating = False
        
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
        self.insight_card.grid_columnconfigure(0, weight=1)
        self.insight_card.grid_rowconfigure(1, weight=1)

        self.insight_title = ctk.CTkLabel(self.insight_card, text="✨ Daily AI Challenge", font=ctk.CTkFont(weight="bold"))
        self.insight_title.grid(row=0, column=0, pady=5)
        
        # Textbox set to sticky "nsew" to fill the card
        self.insight_text = ctk.CTkTextbox(self.insight_card, wrap="word", font=("Mengshen-Handwritten", 14), height=100)
        self.insight_text.configure(state="disabled")
        self.insight_text.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")

        # --- Words Summary Section ---
        self.summary_card = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        self.summary_card.grid(row=2, column=0, padx=40, pady=10, sticky="nsew")
        self.summary_card.grid_columnconfigure(0, weight=1)
        self.summary_card.grid_rowconfigure(1, weight=1)
        
        self.summary_title = ctk.CTkLabel(self.summary_card, text="📚 Words Summary", font=ctk.CTkFont(weight="bold"))
        self.summary_title.grid(row=0, column=0, pady=5)
        
        self.summary_text = ctk.CTkTextbox(self.summary_card, wrap="word", font=("Mengshen-Handwritten", 12), height=100)
        self.summary_text.configure(state="disabled")
        self.summary_text.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")

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

        def generate():
            try:
                if not self.last_words:
                    final_text = "No words in database yet. Add some words first!"
                    self.after(0, lambda text=final_text: self._set_text(self.insight_text, text))
                else:
                    word_list = ", ".join([w[1] for w in self.last_words])
                    prompt = f"Word Blossom Mode: {word_list}"

                    full_response = ""
                    for chunk in self.ai.generate_response(prompt):
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

        def generate():
            try:
                word_list = ", ".join([w[1] for w in self.last_words])
                prompt = f"Summarize these words with Sparkle Notes Mode: {word_list}"

                self.after(0, lambda: self._set_text(self.summary_text, "Generating summary..."))

                full_summary = ""
                for chunk in self.ai.generate_response(prompt):
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
    def __init__(self, reviewer, ai_client=None, db=None):
        super().__init__()
        self.reviewer = reviewer
        self.ai_client = ai_client
        self.db = db
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
        self.frames["home"] = HomeFrame(self, self.ai_client, self.db, fg_color="transparent")
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
