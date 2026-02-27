import tkinter as tk
import tkinter.messagebox as tkmb
import customtkinter
import os
import threading
from lib.localai import OllamaClient
current_folder = os.path.dirname(os.path.abspath(__file__))
# customtkinter.FontManager.load_font(os.path.join(current_folder, "Mengshen-HanSerif.ttf"))
customtkinter.FontManager.load_font(os.path.join(current_folder, "Mengshen-Handwritten.ttf"))
def popup_message(title, message):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    tkmb.showinfo(title, message)
    root.destroy()
class Long_message_popup:
    def __init__(self, title, message):
        long_popup = customtkinter.CTk()
        long_popup.geometry("600x300")
        # Title in bold with custom font
        title_label = customtkinter.CTkLabel(long_popup, text=title, font=("Mengshen-Handwritten", 20, "bold"))
        title_label.pack(pady=(5, 5))
        # Message in scrollable text box with custom font
        text_box = customtkinter.CTkTextbox(long_popup, wrap="word", font=("Mengshen-Handwritten", 16))
        text_box.insert("1.0", message)
        text_box.configure(state="disabled")  # Make it read-only
        text_box.pack(padx=20, pady=10, fill="both", expand=True)
        # label = customtkinter.CTkLabel(long_popup, text=message, wraplength=380, font=("Mengshen-Handwritten", 12))
        # label.pack(pady=20)
        self.long_popup = long_popup
    def show(self):
        self.long_popup.mainloop()
    def add_button(self, text, command):
        if command is None:
            command = self.long_popup.destroy
        btn = customtkinter.CTkButton(self.long_popup, text=text, command=command)
        btn.pack(pady=10)
import customtkinter as ctk

class ControlPanel:
    def __init__(self, app_callback=None): 
        # app_callback is a function passed from your main script to launch App()
        self.opened = False
        self.done = False
        self.app_callback = app_callback
        
        self.root = ctk.CTk()
        self.root.title("Monitor")
        self.root.resizable(width=False, height=False)
        self.root.wm_attributes("-topmost", True)
        
        # --- Responsive Start/Pause Button ---
        self.state_btn = ctk.CTkButton(
            self.root, 
            text="Start", 
            fg_color="green", 
            command=self.toggle_state
        )
        self.state_btn.pack(side="top", fill="x", padx=10, pady=5)
        
        # --- Open Main App Button ---
        self.app_btn = ctk.CTkButton(
            self.root, 
            text="Open Main App", 
            command=self.open_app
        )
        self.app_btn.pack(side="top", fill="x", padx=10, pady=5)

        # --- Exit Button ---
        self.exit_btn = ctk.CTkButton(
            self.root, 
            text="Exit", 
            fg_color="#942626", # Dark Red
            hover_color="#731d1d",
            command=self.cancel
        )
        self.exit_btn.pack(side="top", fill="x", padx=10, pady=5)

    def toggle_state(self):
        """Switches between Start and Pause states"""
        self.opened = not self.opened
        if self.opened:
            self.state_btn.configure(text="Pause", fg_color="orange")
            print("Status: Running")
        else:
            self.state_btn.configure(text="Start", fg_color="green")
            print("Status: Paused")

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
        self.insight_text.configure(font=("Mengshen-Handwritten", 14))
        self.is_generating = False
        
        # Title
        self.label = ctk.CTkLabel(self, text="Welcome Back", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=(20, 0))

        # AI Generated Insight Box
        self.insight_card = ctk.CTkFrame(self, fg_color=("gray90", "gray15"))
        self.insight_card.pack(fill="x", padx=40, pady=20)
        
        self.insight_title = ctk.CTkLabel(self.insight_card, text="✨ Daily AI Challenge", font=ctk.CTkFont(weight="bold"))
        self.insight_title.pack(pady=5)
        
        self.insight_text = ctk.CTkLabel(self.insight_card, text="Click 'New Challenge' to generate a challenge", wraplength=400)
        self.insight_text.pack(pady=10, padx=10)

        # Refresh Button for AI
        self.refresh_btn = ctk.CTkButton(self, text="New Challenge", command=self.generate_challenge)
        self.refresh_btn.pack(pady=10)

    def generate_challenge(self):
        """Generate a vocabulary challenge using AI"""
        if self.is_generating:
            tkmb.showwarning("In Progress", "Already generating a challenge. Please wait.")
            return

        if not self.ai or not self.db:
            self.insight_text.configure(text="❌ AI Client or Database not available")
            return

        # fetch words on main thread to avoid cross-thread DB usage
        try:
            words = self.db.get_recent_words(limit=3)
        except Exception as e:
            words = []
            print(f"Error reading recent words: {e}")

        self.is_generating = True
        self.refresh_btn.configure(state="disabled")
        self.insight_text.configure(text="Generating challenge...")

        def generate():
            try:
                if not words:
                    response = "No words in database yet. Add some words first!"
                else:
                    word_list = ", ".join([w[1] for w in words])
                    prompt = f"Write a very short, funny 2-sentence story using these words: {word_list}"
                    response = self.ai.generate_response(prompt)

                # Update UI in main thread
                self.after(0, lambda: self.insight_text.configure(text=response))
            except Exception as e:
                error_msg = f"Error generating challenge: {str(e)}"
                self.after(0, lambda: self.insight_text.configure(text=error_msg))
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
    panel.show()
    longpop=Long_message_popup("Test Long Message", "This is a long message to test the Long_message_popup class. It should wrap properly and use the custom font loaded from the Mengshen-Handwritten.ttf file. If you see this message clearly, it means the function is working correctly!"*5)
    longpop.show()
