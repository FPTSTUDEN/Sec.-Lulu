"""
Centralized vocabulary database management.
All database operations go through this module for consistency and maintainability.
"""

import sqlite3
import uuid
import time
import threading
from typing import List, Tuple, Optional, Dict
from datetime import datetime, timedelta


class VocabDatabase:
    """
    Unified interface for all vocabulary database operations.
    THREAD-SAFE: Each thread gets its own connection.
    """
    
    def __init__(self, db_path: str = "vocab.db"):
        """Initialize database path and create local storage."""
        self.db_path = db_path
        self._local = threading.local()
        self._init_schema()
    
    def _get_connection(self):
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _get_cursor(self):
        """Get cursor from thread-local connection."""
        return self._get_connection().cursor()
    
    def _init_schema(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Existing words table
        cursor.execute("""
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
        
        # ===== SENTENCE ANALYSIS TABLES (matching AI fields) =====
        
        # Content container
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentence_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT UNIQUE,
                title TEXT,
                original_text TEXT,
                created_at INTEGER,
                total_sentences INTEGER,
                estimated_level TEXT
            )
        """)
        
        # Individual sentences - fields match AI Whisper output
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyzed_sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER,
                sentence_index INTEGER,
                original TEXT,
                simplified_paraphrase TEXT,
                translation TEXT,
                why_matters TEXT,
                remember_hook TEXT,
                difficulty INTEGER DEFAULT 3,
                mastered BOOLEAN DEFAULT 0,
                created_at INTEGER,
                FOREIGN KEY(analysis_id) REFERENCES sentence_analyses(id) ON DELETE CASCADE
            )
        """)
        
        # Key words extracted from sentences (with insights)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentence_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sentence_id INTEGER,
                word TEXT,
                pinyin TEXT,
                insight TEXT,
                importance_score REAL DEFAULT 0.5,
                FOREIGN KEY(sentence_id) REFERENCES analyzed_sentences(id) ON DELETE CASCADE
            )
        """)
        
        # Priority notes on sentences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentence_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sentence_id INTEGER,
                note_text TEXT,
                priority INTEGER DEFAULT 2,
                tags TEXT,
                is_pinned BOOLEAN DEFAULT 0,
                created_at INTEGER,
                updated_at INTEGER,
                FOREIGN KEY(sentence_id) REFERENCES analyzed_sentences(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ===== EXISTING WORD METHODS (keep as is) =====
    
    def add_word(self, word: str, translation: str, example: str = "") -> str:
        """
        Add a new word to the database.
        
        Returns the word ID.
        """
        now = int(time.time())
        word_id = str(uuid.uuid4())
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (word_id, word, translation, example, now, 0, 2.5, 1, now + 86400))
        self._get_connection().commit()
        return word_id
    
    def get_word_id(self, word: str) -> Optional[str]:
        """Get ID of a word by its text."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM words WHERE word = ?", (word,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_due_words(self) -> List[Tuple]:
        """
        Get all words that are due for review (next_review <= now).
        Returns list of tuples with full word data.
        """
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM words WHERE next_review <= ? ORDER BY next_review ASC", (now,))
        return cursor.fetchall()
    
    def get_recent_words(self, limit: int = 5) -> List[Tuple]:
        """
        Get most recently added words.
        Returns list of tuples with full word data.
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM words ORDER BY created_at DESC LIMIT ?", (limit,))
        return cursor.fetchall()
    
    def get_word_stats(self, word_id: str) -> Dict:
        cursor = self._get_cursor()
        cursor.execute("SELECT review_count, ease_factor, interval, next_review FROM words WHERE id = ?", (word_id,))
        row = cursor.fetchone()
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
        cursor = self._get_cursor()
        cursor.execute("SELECT review_count, ease_factor, interval FROM words WHERE id = ?", (word_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        review_count, ease_factor, interval = row
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
        cursor.execute("""
            UPDATE words SET review_count = ?, ease_factor = ?, interval = ?, next_review = ? WHERE id = ?
        """, (review_count, ease_factor, interval, next_review, word_id))
        self._get_connection().commit()
        return datetime.fromtimestamp(next_review).strftime('%Y-%m-%d')
    
    def reset_all_reviews(self):
        """Reset all review statistics (for testing/reset)."""
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("UPDATE words SET review_count = 0, ease_factor = 2.5, interval = 1, next_review = ?", (now + 86400,))
        self._get_connection().commit()
    
    def delete_all_words(self):
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM words")
        self._get_connection().commit()
    
    # ===== SENTENCE ANALYSIS METHODS (matching AI fields) =====
    
    def create_sentence_analysis(self, content_id: str, title: str, original_text: str, 
                                   total_sentences: int, estimated_level: str) -> int:
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO sentence_analyses (content_id, title, original_text, created_at, total_sentences, estimated_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (content_id, title, original_text[:500], now, total_sentences, estimated_level))
        self._get_connection().commit()
        return cursor.lastrowid
    
    def get_sentence_analysis(self, content_id: str) -> Optional[Dict]:
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, content_id, title, original_text, created_at, total_sentences, estimated_level
            FROM sentence_analyses WHERE content_id = ?
        """, (content_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "content_id": row[1],
            "title": row[2],
            "original_text": row[3],
            "created_at": row[4],
            "total_sentences": row[5],
            "estimated_level": row[6]
        }
    
    def save_analyzed_sentence(self, analysis_id: int, sentence_index: int, original: str,
                                translation: str, why_matters: str, remember_hook: str,
                                simplified_paraphrase: str = "", difficulty: int = 3) -> int:
        """Save an analyzed sentence with all AI whisper fields."""
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO analyzed_sentences (
                analysis_id, sentence_index, original, simplified_paraphrase, 
                translation, why_matters, remember_hook, difficulty, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (analysis_id, sentence_index, original, simplified_paraphrase, 
              translation, why_matters, remember_hook, difficulty, now))
        self._get_connection().commit()
        return cursor.lastrowid
    
    def save_sentence_keyword(self, sentence_id: int, word: str, pinyin: str, insight: str, importance: float = 0.5):
        """Save a keyword extracted from a sentence with its insight."""
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO sentence_keywords (sentence_id, word, pinyin, insight, importance_score)
            VALUES (?, ?, ?, ?, ?)
        """, (sentence_id, word, pinyin, insight, importance))
        self._get_connection().commit()
    
    def get_sentences_by_analysis(self, analysis_id: int) -> List[Dict]:
        """Get all sentences with all AI fields."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, sentence_index, original, simplified_paraphrase, translation, 
                   why_matters, remember_hook, difficulty, mastered
            FROM analyzed_sentences
            WHERE analysis_id = ?
            ORDER BY sentence_index
        """, (analysis_id,))
        
        sentences = []
        for row in cursor.fetchall():
            sentence = {
                "id": row[0],
                "sentence_index": row[1],
                "original": row[2],
                "simplified_paraphrase": row[3] or "",
                "translation": row[4] or "",
                "why_matters": row[5] or "",
                "remember_hook": row[6] or "",
                "difficulty": row[7],
                "mastered": bool(row[8]),
                "keywords": self._get_sentence_keywords(row[0]),
                "notes": self._get_sentence_notes(row[0])
            }
            sentences.append(sentence)
        return sentences
    
    def _get_sentence_keywords(self, sentence_id: int) -> List[Dict]:
        """Get keywords for a sentence."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT word, pinyin, insight, importance_score
            FROM sentence_keywords
            WHERE sentence_id = ?
            ORDER BY importance_score DESC
        """, (sentence_id,))
        return [{"word": r[0], "pinyin": r[1], "insight": r[2], "importance": r[3]} 
                for r in cursor.fetchall()]
    
    def _get_sentence_notes(self, sentence_id: int) -> List[Dict]:
        """Get notes for a sentence."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, note_text, priority, tags, is_pinned, created_at, updated_at
            FROM sentence_notes
            WHERE sentence_id = ?
            ORDER BY is_pinned DESC, priority ASC, created_at DESC
        """, (sentence_id,))
        return [{
            "id": r[0],
            "note_text": r[1],
            "priority": r[2],
            "tags": r[3].split(",") if r[3] else [],
            "is_pinned": bool(r[4]),
            "created_at": r[5],
            "updated_at": r[6]
        } for r in cursor.fetchall()]
    
    def add_sentence_note(self, sentence_id: int, note_text: str, priority: int, tags: List[str], is_pinned: bool) -> int:
        now = int(time.time())
        tags_str = ",".join(tags)
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO sentence_notes (sentence_id, note_text, priority, tags, is_pinned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sentence_id, note_text, priority, tags_str, is_pinned, now, now))
        self._get_connection().commit()
        return cursor.lastrowid
    
    def update_sentence_note(self, note_id: int, note_text: str, priority: int, tags: List[str], is_pinned: bool):
        now = int(time.time())
        tags_str = ",".join(tags)
        cursor = self._get_cursor()
        cursor.execute("""
            UPDATE sentence_notes SET note_text = ?, priority = ?, tags = ?, is_pinned = ?, updated_at = ?
            WHERE id = ?
        """, (note_text, priority, tags_str, is_pinned, now, note_id))
        self._get_connection().commit()
    
    def delete_sentence_note(self, note_id: int):
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM sentence_notes WHERE id = ?", (note_id,))
        self._get_connection().commit()
    
    def toggle_sentence_mastered(self, sentence_id: int, mastered: bool):
        cursor = self._get_cursor()
        cursor.execute("UPDATE analyzed_sentences SET mastered = ? WHERE id = ?", (1 if mastered else 0, sentence_id))
        self._get_connection().commit()
    
    def get_all_sentence_analyses(self, limit: int = 20) -> List[Dict]:
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, content_id, title, created_at, total_sentences, estimated_level
            FROM sentence_analyses ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        return [{
            "id": r[0],
            "content_id": r[1],
            "title": r[2],
            "created_at": r[3],
            "total_sentences": r[4],
            "estimated_level": r[5]
        } for r in cursor.fetchall()]
    
    def delete_sentence_analysis(self, analysis_id: int):
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM sentence_analyses WHERE id = ?", (analysis_id,))
        self._get_connection().commit()
    
    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()