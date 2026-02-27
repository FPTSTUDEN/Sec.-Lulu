"""
Simple database handler for vocabulary
"""
import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional

class Database:
    def __init__(self, db_path='vocab.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database table"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
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
    
    def get_words_for_review(self) -> List[Tuple]:
        """Get words that need review"""
        current_time = int(datetime.now().timestamp())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, word, translation, example_sentence, 
                       review_count, ease_factor, interval, next_review
                FROM words 
                WHERE next_review IS NULL OR next_review <= ?
                ORDER BY next_review ASC
            ''', (current_time,))
            return cursor.fetchall()
    
    def update_word_review(self, word_id: str, review_count: int, 
                          ease_factor: float, interval: int, next_review: int):
        """Update word after review"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE words 
                SET review_count = ?, ease_factor = ?, 
                    interval = ?, next_review = ?
                WHERE id = ?
            ''', (review_count, ease_factor, interval, next_review, word_id))