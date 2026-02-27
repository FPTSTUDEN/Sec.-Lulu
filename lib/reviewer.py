"""
Core word reviewing logic using unified VocabDatabase.
"""
from typing import Optional, Tuple, List
from lib.db import VocabDatabase


class WordReviewer:
    """Manages vocabulary review sessions using a database class.

    The reviewer is designed for dependency injection so that tests or the
    integrated application can supply either the real `VocabDatabase` or a
    mock/subclass.  Only the interface defined in `VocabDatabase` is required.
    """
    
    def __init__(self, db_path: str = "vocab.db", db_cls=VocabDatabase):
        # db_cls must provide the same API as VocabDatabase
        self.db = db_cls(db_path)
        self.words = []
        self.current_index = -1
        self.quality_map = {"hard": 2, "good": 3, "easy": 4}
    
    def load_review_words(self):
        """Load all words due for review."""
        self.words = self.db.get_due_words()
        self.current_index = 0 if self.words else -1
    
    def get_current_word(self) -> Optional[Tuple]:
        """Return current word tuple or None."""
        if self.words and 0 <= self.current_index < len(self.words):
            return self.words[self.current_index]
        return None
    
    def get_progress(self) -> str:
        """Return progress string."""
        if not self.words:
            return "No words to review"
        return f"Word {self.current_index + 1} of {len(self.words)}"
    
    def has_words(self) -> bool:
        """Check if words remain."""
        return len(self.words) > 0
    
    def next_word(self) -> bool:
        """Move to next word."""
        if self.current_index < len(self.words) - 1:
            self.current_index += 1
            return True
        return False
    
    def review_current(self, quality: str) -> Optional[str]:
        """Mark word as reviewed and return next review date."""
        word = self.get_current_word()
        if not word:
            return None
        
        word_id = word[0]
        quality_factor = self.quality_map.get(quality, 3)
        next_date = self.db.update_review(word_id, quality_factor)
        
        self.words.pop(self.current_index)
        if self.current_index >= len(self.words) and self.current_index > 0:
            self.current_index -= 1
        
        return next_date
    
    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()
    
    def __del__(self):
        """Ensure cleanup."""
        self.close()
