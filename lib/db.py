"""
Centralized vocabulary database management.
All database operations go through this module for consistency and maintainability.
"""

import sqlite3
import uuid
import time
from typing import List, Tuple, Optional, Dict
from datetime import datetime, timedelta


class VocabDatabase:
    """
    Unified interface for all vocabulary database operations.
    Manages SQLite connections and all word review logic.
    Thread-safe: each instance has its own connection.
    """
    
    def __init__(self, db_path: str = "vocab.db"):
        """Initialize database connection and schema."""
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_schema()
    
    def _init_schema(self):
        """Create tables if they don't exist."""
        self.cursor.execute("""
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
        """)
        self.conn.commit()
    
    # ===== ADD/RETRIEVE OPERATIONS =====
    
    def add_word(self, word: str, translation: str, example: str = "") -> str:
        """
        Add a new word to the database.
        
        Returns the word ID.
        """
        now = int(time.time())
        word_id = str(uuid.uuid4())
        self.cursor.execute("""
            INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            word_id, word, translation, example, now,
            0,      # review_count
            2.5,    # ease_factor
            1,      # interval
            now + 86400  # next_review (1 day from now)
        ))
        self.conn.commit()
        return word_id
    
    def get_word_id(self, word: str) -> Optional[str]:
        """Get ID of a word by its text."""
        self.cursor.execute("SELECT id FROM words WHERE word = ?", (word,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    # ===== REVIEW OPERATIONS =====
    
    def get_due_words(self) -> List[Tuple]:
        """
        Get all words that are due for review (next_review <= now).
        Returns list of tuples with full word data.
        """
        now = int(time.time())
        self.cursor.execute("""
            SELECT * FROM words 
            WHERE next_review IS NULL OR next_review <= ?
            ORDER BY next_review ASC
        """, (now,))
        return self.cursor.fetchall()
    
    def get_recent_words(self, limit: int = 5) -> List[Tuple]:
        """
        Get most recently added words.
        Returns list of tuples with full word data.
        """
        self.cursor.execute("""
            SELECT * FROM words 
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()
    
    def get_word_stats(self, word_id: str) -> Dict[str, Optional[str]]:
        """Get review statistics for a word."""
        self.cursor.execute("""
            SELECT review_count, ease_factor, interval, next_review 
            FROM words WHERE id = ?
        """, (word_id,))
        row = self.cursor.fetchone()
        
        if not row:
            return {}
        
        return {
            "review_count": row[0],
            "ease_factor": row[1],
            "interval": row[2],
            "next_review": datetime.fromtimestamp(row[3]).strftime('%Y-%m-%d %H:%M:%S') if row[3] else None
        }
    
    def update_review(self, word_id: str, quality: int) -> Optional[str]:
        """
        Mark a word as reviewed using SM-2 algorithm.
        
        Args:
            word_id: ID of word to review
            quality: Quality score (1-5, where 3+ is "passing")
        
        Returns:
            Next review date string.
        """
        # Fetch current stats
        self.cursor.execute("""
            SELECT review_count, ease_factor, interval FROM words WHERE id = ?
        """, (word_id,))
        row = self.cursor.fetchone()
        if not row:
            return None
        
        review_count, ease_factor, interval = row
        
        # SM-2 algorithm calculations
        review_count += 1
        if quality < 3:
            interval = 1
        else:
            if review_count == 1:
                interval = 1
            elif review_count == 2:
                interval = 6
            else:
                interval = int(interval * ease_factor)
            
            ease_factor += (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            if ease_factor < 1.3:
                ease_factor = 1.3
        
        next_review = int(time.time()) + interval * 86400
        
        # Update database
        self.cursor.execute("""
            UPDATE words 
            SET review_count = ?, ease_factor = ?, interval = ?, next_review = ?
            WHERE id = ?
        """, (review_count, ease_factor, interval, next_review, word_id))
        self.conn.commit()
        
        # Return formatted date
        return datetime.fromtimestamp(next_review).strftime('%Y-%m-%d')
    
    # ===== MAINTENANCE OPERATIONS =====
    
    def reset_all_reviews(self):
        """Reset all review statistics (for testing/reset)."""
        now = int(time.time())
        self.cursor.execute("""
            UPDATE words 
            SET review_count = 0, ease_factor = 2.5, interval = 1, next_review = ?
        """, (now + 86400,))
        self.conn.commit()
    
    def delete_all_words(self):
        """Delete all words from the database."""
        self.cursor.execute("DELETE FROM words")
        self.conn.commit()
    
    # ===== CONNECTION MANAGEMENT =====
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __del__(self):
        """Ensure connection is closed."""
        self.close()
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
