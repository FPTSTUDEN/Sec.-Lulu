import sqlite3
import customtkinter as ctk
from datetime import datetime, timedelta
import tkinter.messagebox as tkmb

# Configure CustomTkinter
ctk.set_appearance_mode("dark")  # Can be "dark", "light", or "system"
ctk.set_default_color_theme("green")  # Can be "blue", "green", "dark-blue"

class VocabApp:
    def __init__(self):
        self.window = ctk.CTk()
        self.window.title("Vocabulary Learning System")
        self.window.geometry("1000x700")
        
        # Database connection
        self.conn = sqlite3.connect('vocab.db')
        self.create_tables()
        
        # Current word index for navigation
        self.current_words = []
        self.current_index = 0
        self.current_mode = "pending"  # "pending" or "learned"
        
        self.setup_ui()
        self.load_words()
        
    def create_tables(self):
        """Ensure the words table exists"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id TEXT PRIMARY KEY,
                word TEXT,
                translation TEXT,
                example_sentence TEXT,
                created_at INTEGER,
                review_count INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                interval INTEGER DEFAULT 1,
                next_review INTEGER
            )
        ''')
        self.conn.commit()
    
    def setup_ui(self):
        # Main container
        self.main_frame = ctk.CTkFrame(self.window)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header with title and stats
        self.header_frame = ctk.CTkFrame(self.main_frame)
        self.header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="📚 Vocabulary Learning System", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(side="left", padx=10)
        
        self.stats_label = ctk.CTkLabel(
            self.header_frame, 
            text="", 
            font=ctk.CTkFont(size=14)
        )
        self.stats_label.pack(side="right", padx=10)
        
        # Mode selection buttons
        self.mode_frame = ctk.CTkFrame(self.main_frame)
        self.mode_frame.pack(fill="x", padx=10, pady=5)
        
        self.pending_btn = ctk.CTkButton(
            self.mode_frame,
            text="📝 Pending Review",
            command=lambda: self.switch_mode("pending"),
            width=200
        )
        self.pending_btn.pack(side="left", padx=5, pady=5)
        
        self.learned_btn = ctk.CTkButton(
            self.mode_frame,
            text="✅ Learned Words",
            command=lambda: self.switch_mode("learned"),
            width=200
        )
        self.learned_btn.pack(side="left", padx=5, pady=5)
        
        # Search frame
        self.search_frame = ctk.CTkFrame(self.main_frame)
        self.search_frame.pack(fill="x", padx=10, pady=5)
        
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="Search words...",
            width=300
        )
        self.search_entry.pack(side="left", padx=5, pady=5)
        
        self.search_btn = ctk.CTkButton(
            self.search_frame,
            text="Search",
            command=self.search_words,
            width=100
        )
        self.search_btn.pack(side="left", padx=5, pady=5)
        
        self.clear_btn = ctk.CTkButton(
            self.search_frame,
            text="Clear",
            command=self.clear_search,
            width=100
        )
        self.clear_btn.pack(side="left", padx=5, pady=5)
        
        # Word display area
        self.display_frame = ctk.CTkFrame(self.main_frame)
        self.display_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Word card
        self.card_frame = ctk.CTkFrame(self.display_frame)
        self.card_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.word_label = ctk.CTkLabel(
            self.card_frame,
            text="",
            font=ctk.CTkFont(size=32, weight="bold"),
            wraplength=600
        )
        self.word_label.pack(pady=(30, 10))
        
        self.translation_label = ctk.CTkLabel(
            self.card_frame,
            text="",
            font=ctk.CTkFont(size=24),
            wraplength=600
        )
        self.translation_label.pack(pady=10)
        
        self.example_label = ctk.CTkLabel(
            self.card_frame,
            text="",
            font=ctk.CTkFont(size=16, slant="italic"),
            wraplength=600,
            text_color="gray70"
        )
        self.example_label.pack(pady=10)
        
        # Navigation and action buttons
        self.action_frame = ctk.CTkFrame(self.main_frame)
        self.action_frame.pack(fill="x", padx=10, pady=10)
        
        self.prev_btn = ctk.CTkButton(
            self.action_frame,
            text="◀ Previous",
            command=self.prev_word,
            width=150
        )
        self.prev_btn.pack(side="left", padx=5, pady=5)
        
        self.next_btn = ctk.CTkButton(
            self.action_frame,
            text="Next ▶",
            command=self.next_word,
            width=150
        )
        self.next_btn.pack(side="left", padx=5, pady=5)
        
        # Progress indicator
        self.progress_label = ctk.CTkLabel(
            self.action_frame,
            text="",
            font=ctk.CTkFont(size=14)
        )
        self.progress_label.pack(side="left", padx=20)
        
        # Review buttons (only shown in pending mode)
        self.review_frame = ctk.CTkFrame(self.action_frame)
        self.review_frame.pack(side="right", padx=5)
        
        self.hard_btn = ctk.CTkButton(
            self.review_frame,
            text="Hard",
            command=lambda: self.review_word("hard"),
            width=80,
            fg_color="orange",
            hover_color="darkorange"
        )
        self.hard_btn.pack(side="left", padx=2)
        
        self.good_btn = ctk.CTkButton(
            self.review_frame,
            text="Good",
            command=lambda: self.review_word("good"),
            width=80,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.good_btn.pack(side="left", padx=2)
        
        self.easy_btn = ctk.CTkButton(
            self.review_frame,
            text="Easy",
            command=lambda: self.review_word("easy"),
            width=80,
            fg_color="blue",
            hover_color="darkblue"
        )
        self.easy_btn.pack(side="left", padx=2)
        
        # Word list sidebar
        self.sidebar_frame = ctk.CTkFrame(self.main_frame, width=200)
        self.sidebar_frame.pack(side="right", fill="y", padx=(0, 10), pady=10)
        self.sidebar_frame.pack_propagate(False)
        
        self.sidebar_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Word List",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.sidebar_label.pack(pady=10)
        
        self.listbox_frame = ctk.CTkScrollableFrame(self.sidebar_frame)
        self.listbox_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
    def load_words(self):
        """Load words based on current mode"""
        cursor = self.conn.cursor()
        
        if self.current_mode == "pending":
            # Words that need review (next_review <= current time or NULL)
            current_time = int(datetime.now().timestamp())
            cursor.execute('''
                SELECT id, word, translation, example_sentence, review_count, 
                       ease_factor, interval, next_review
                FROM words 
                WHERE next_review IS NULL OR next_review <= ?
                ORDER BY next_review ASC
            ''', (current_time,))
        else:
            # Learned words (next_review in the future)
            current_time = int(datetime.now().timestamp())
            cursor.execute('''
                SELECT id, word, translation, example_sentence, review_count, 
                       ease_factor, interval, next_review
                FROM words 
                WHERE next_review > ?
                ORDER BY next_review DESC
            ''', (current_time,))
        
        self.current_words = cursor.fetchall()
        self.current_index = 0 if self.current_words else -1
        self.update_stats()
        self.update_word_display()
        self.update_word_list()
        
    def update_stats(self):
        """Update statistics display"""
        cursor = self.conn.cursor()
        
        # Total words
        cursor.execute("SELECT COUNT(*) FROM words")
        total = cursor.fetchone()[0]
        
        # Words pending review
        current_time = int(datetime.now().timestamp())
        cursor.execute("SELECT COUNT(*) FROM words WHERE next_review IS NULL OR next_review <= ?", (current_time,))
        pending = cursor.fetchone()[0]
        
        # Learned words
        cursor.execute("SELECT COUNT(*) FROM words WHERE next_review > ?", (current_time,))
        learned = cursor.fetchone()[0]
        
        self.stats_label.configure(
            text=f"Total: {total} | Pending: {pending} | Learned: {learned}"
        )
        
    def update_word_display(self):
        """Update the word display with current word"""
        if self.current_words and self.current_index >= 0:
            word_data = self.current_words[self.current_index]
            self.word_label.configure(text=word_data[1])  # word
            self.translation_label.configure(text=word_data[2])  # translation
            self.translation_label.configure(text_color="white")
            
            if word_data[3]:  # example_sentence
                self.example_label.configure(text=f'"{word_data[3]}"')
                self.example_label.configure(text_color="gray70")
            else:
                self.example_label.configure(text="")
            
            # Update progress
            self.progress_label.configure(
                text=f"{self.current_index + 1} / {len(self.current_words)}"
            )
            
            # Show/hide review buttons based on mode
            if self.current_mode == "pending":
                self.review_frame.pack(side="right", padx=5)
            else:
                self.review_frame.pack_forget()
        else:
            self.word_label.configure(text="No words found")
            self.translation_label.configure(text="")
            self.example_label.configure(text="")
            self.progress_label.configure(text="0 / 0")
            
    def update_word_list(self):
        """Update the sidebar word list"""
        # Clear existing buttons
        for widget in self.listbox_frame.winfo_children():
            widget.destroy()
        
        # Add word buttons
        for i, word_data in enumerate(self.current_words):
            btn = ctk.CTkButton(
                self.listbox_frame,
                text=word_data[1],  # word
                command=lambda idx=i: self.select_word(idx),
                height=30,
                fg_color="transparent" if i != self.current_index else None,
                text_color=("gray90", "gray90"),
                anchor="w"
            )
            btn.pack(fill="x", padx=2, pady=1)
    
    def select_word(self, index):
        """Select a word from the list"""
        self.current_index = index
        self.update_word_display()
        self.update_word_list()
    
    def switch_mode(self, mode):
        """Switch between pending and learned modes"""
        self.current_mode = mode
        self.load_words()
        
        # Update button appearances
        if mode == "pending":
            self.pending_btn.configure(fg_color=["#3a7ebf", "#1f538d"])
            self.learned_btn.configure(fg_color=["gray50", "gray30"])
        else:
            self.pending_btn.configure(fg_color=["gray50", "gray30"])
            self.learned_btn.configure(fg_color=["#3a7ebf", "#1f538d"])
    
    def prev_word(self):
        """Go to previous word"""
        if self.current_words and self.current_index > 0:
            self.current_index -= 1
            self.update_word_display()
            self.update_word_list()
    
    def next_word(self):
        """Go to next word"""
        if self.current_words and self.current_index < len(self.current_words) - 1:
            self.current_index += 1
            self.update_word_display()
            self.update_word_list()
    
    def review_word(self, quality):
        """Review the current word with given quality (hard, good, easy)"""
        if not self.current_words or self.current_index < 0:
            return
            
        word_data = self.current_words[self.current_index]
        word_id = word_data[0]
        current_ease = word_data[5]
        current_interval = word_data[6]
        review_count = word_data[4]
        
        # Map quality to factor
        quality_map = {
            "hard": 2,    # Hard: correct but difficult
            "good": 3,    # Good: correct
            "easy": 4     # Easy: correct and easy
        }
        
        quality_factor = quality_map.get(quality, 3)
        
        # SM-2 algorithm for spaced repetition
        if review_count == 0:
            # First review
            interval = 1
            ease_factor = 2.5
        else:
            # Update ease factor
            ease_factor = current_ease + (0.1 - (5 - quality_factor) * (0.08 + (5 - quality_factor) * 0.02))
            if ease_factor < 1.3:
                ease_factor = 1.3
            
            # Calculate new interval
            if quality_factor < 3:
                interval = 1  # Reset interval if response was "hard"
            else:
                interval = current_interval * ease_factor
        
        # Calculate next review date
        next_review = int((datetime.now() + timedelta(days=interval)).timestamp())
        
        # Update database
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE words 
            SET review_count = review_count + 1,
                ease_factor = ?,
                interval = ?,
                next_review = ?
            WHERE id = ?
        ''', (ease_factor, interval, next_review, word_id))
        self.conn.commit()
        
        # Show feedback
        next_date = datetime.fromtimestamp(next_review).strftime("%Y-%m-%d")
        tkmb.showinfo("Review Complete", 
                     f"Word will be reviewed again on: {next_date}")
        
        # Remove from current list and move to next
        self.current_words.pop(self.current_index)
        if self.current_index >= len(self.current_words):
            self.current_index = len(self.current_words) - 1
        
        self.update_stats()
        self.update_word_display()
        self.update_word_list()
        
        if not self.current_words:
            tkmb.showinfo("All Done!", "No more words pending review!")
    
    def search_words(self):
        """Search for words"""
        search_term = self.search_entry.get()
        if not search_term:
            return
            
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, word, translation, example_sentence, review_count, 
                   ease_factor, interval, next_review
            FROM words 
            WHERE word LIKE ? OR translation LIKE ? OR example_sentence LIKE ?
            ORDER BY word
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        self.current_words = cursor.fetchall()
        self.current_index = 0 if self.current_words else -1
        self.update_word_display()
        self.update_word_list()
    
    def clear_search(self):
        """Clear search and reload words"""
        self.search_entry.delete(0, 'end')
        self.load_words()
    
    def run(self):
        """Run the application"""
        self.window.mainloop()
    
    def __del__(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()

if __name__ == "__main__":
    app = VocabApp()
    app.run()