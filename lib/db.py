"""
Simplified vocabulary database management with clean chain tracking.
Uses parent_id instead of complex JSON paths and edges.
"""

import sqlite3
import uuid
import time
import threading
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import json
import logging

# Simple logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VocabDatabase:
    """Unified interface for all vocabulary database operations."""
    
    def __init__(self, db_path: str = "vocab.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_schema()
    
    def _get_connection(self):
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_schema(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Words table (unchanged)
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
        
        # SIMPLIFIED: Content nodes with parent_id only
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_type TEXT NOT NULL,
                content TEXT,
                title TEXT,
                metadata TEXT,
                parent_id INTEGER,  -- Simple parent reference, no JSON!
                session_id TEXT,
                source_text_id TEXT,
                created_at INTEGER,
                FOREIGN KEY(parent_id) REFERENCES content_nodes(id) ON DELETE SET NULL
            )
        """)
        
        # Create index for fast chain queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent ON content_nodes(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON content_nodes(session_id)")
        
        # Word occurrences (simplified)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id TEXT,
                content_node_id INTEGER,
                position_start INTEGER,
                position_end INTEGER,
                FOREIGN KEY(word_id) REFERENCES words(id),
                FOREIGN KEY(content_node_id) REFERENCES content_nodes(id) ON DELETE CASCADE
            )
        """)
        
        # Session tables (unchanged from your original)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                session_type TEXT,
                source_name TEXT,
                start_time INTEGER,
                end_time INTEGER,
                is_active BOOLEAN DEFAULT 1,
                word_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                word_id TEXT,
                added_at INTEGER,
                FOREIGN KEY(session_id) REFERENCES learning_sessions(session_id),
                FOREIGN KEY(word_id) REFERENCES words(id)
            )
        """)
        
        # Sentence analysis tables (unchanged)
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
        logger.info("Database schema initialized")
    
    # ===== SIMPLIFIED CONTENT CHAIN METHODS =====
    
    def create_content_node(self, node_type: str, content: str, title: str = None,
                            parent_node_id: int = None, session_id: str = None,
                            metadata: Dict = None, source_text_id: str = None) -> int:
        """Create a content node with simple parent reference."""
        now = int(time.time())
        cursor = self._get_cursor()
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        cursor.execute("""
            INSERT INTO content_nodes (node_type, content, title, metadata, parent_id, session_id, source_text_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (node_type, content[:5000], title, metadata_json, parent_node_id, session_id, source_text_id, now))
        
        node_id = cursor.lastrowid
        self._get_connection().commit()
        
        logger.debug(f"Created node {node_id}: type={node_type}, parent={parent_node_id}")
        return node_id
    
    def get_content_node(self, node_id: int) -> Optional[Dict]:
        """Get a content node by ID."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, node_type, content, title, metadata, parent_id, session_id, source_text_id, created_at
            FROM content_nodes WHERE id = ?
        """, (node_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "node_type": row[1],
            "content": row[2],
            "title": row[3],
            "metadata": json.loads(row[4]) if row[4] else {},
            "parent_id": row[5],
            "session_id": row[6],
            "source_text_id": row[7],
            "created_at": row[8]
        }
    
    def get_content_chain(self, node_id: int) -> List[Dict]:
        """
        Get the full chain of ancestors for a node using recursive CTE.
        Returns list from oldest ancestor to current node.
        """
        cursor = self._get_cursor()
        
        # Recursive CTE to build the chain
        cursor.execute("""
            WITH RECURSIVE chain AS (
                -- Start with the current node
                SELECT id, node_type, content, title, metadata, parent_id, 
                       session_id, source_text_id, created_at, 0 as depth
                FROM content_nodes WHERE id = ?
                
                UNION ALL
                
                -- Recursively get parents
                SELECT cn.id, cn.node_type, cn.content, cn.title, cn.metadata,
                       cn.parent_id, cn.session_id, cn.source_text_id, cn.created_at,
                       chain.depth + 1
                FROM content_nodes cn
                JOIN chain ON cn.id = chain.parent_id
            )
            SELECT * FROM chain ORDER BY depth DESC
        """, (node_id,))
        
        chain = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"Chain for node {node_id}: {len(chain)} nodes")
        return chain
    
    def get_node_children(self, node_id: int, node_type: str = None) -> List[Dict]:
        """Get all children nodes (what this node led to)."""
        cursor = self._get_cursor()
        
        if node_type:
            cursor.execute("""
                SELECT id, node_type, content, title, created_at
                FROM content_nodes
                WHERE parent_id = ? AND node_type = ?
                ORDER BY created_at
            """, (node_id, node_type))
        else:
            cursor.execute("""
                SELECT id, node_type, content, title, created_at
                FROM content_nodes
                WHERE parent_id = ?
                ORDER BY created_at
            """, (node_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_node_parent(self, node_id: int) -> Optional[Dict]:
        """Get the immediate parent of a node."""
        node = self.get_content_node(node_id)
        if not node or not node.get('parent_id'):
            return None
        return self.get_content_node(node['parent_id'])
    
    def get_subtree(self, root_node_id: int, max_depth: int = 10) -> List[Dict]:
        """Get entire subtree starting from a root node."""
        cursor = self._get_cursor()
        cursor.execute("""
            WITH RECURSIVE subtree AS (
                SELECT id, node_type, content, title, parent_id, created_at, 0 as depth
                FROM content_nodes WHERE id = ?
                
                UNION ALL
                
                SELECT cn.id, cn.node_type, cn.content, cn.title, cn.parent_id, cn.created_at, depth + 1
                FROM content_nodes cn
                JOIN subtree ON cn.parent_id = subtree.id
                WHERE depth + 1 <= ?
            )
            SELECT * FROM subtree ORDER BY depth, created_at
        """, (root_node_id, max_depth))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def record_word_occurrence(self, word_id: str, content_node_id: int,
                                position_start: int = 0, position_end: int = None):
        """Record where a word appears in content."""
        if position_end is None:
            position_end = position_start
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO word_occurrences (word_id, content_node_id, position_start, position_end)
            VALUES (?, ?, ?, ?)
        """, (word_id, content_node_id, position_start, position_end))
        self._get_connection().commit()
    
    def find_word_occurrences(self, word: str) -> List[Dict]:
        """Find all occurrences of a word across content."""
        word_id = self.get_word_id(word)
        if not word_id:
            return []
        
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT wo.content_node_id, cn.node_type, cn.title, wo.position_start, wo.position_end
            FROM word_occurrences wo
            JOIN content_nodes cn ON wo.content_node_id = cn.id
            WHERE wo.word_id = ?
            ORDER BY cn.created_at DESC
        """, (word_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_last_content_node_id(self) -> Optional[int]:
        """Get the ID of the most recently created content node."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM content_nodes ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None
    
    # ===== WORD METHODS (unchanged from your original) =====
    
    def add_word(self, word: str, translation: str, example: str = "") -> str:
        now = int(time.time())
        word_id = str(uuid.uuid4())
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (word_id, word, translation, example, now, 0, 2.5, 1, now + 86400))
        self._get_connection().commit()
        return word_id
    
    def get_word_id(self, word: str) -> Optional[str]:
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM words WHERE word = ?", (word,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_due_words(self) -> List[Tuple]:
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM words WHERE next_review <= ? ORDER BY next_review ASC", (now,))
        return cursor.fetchall()
    
    def get_recent_words(self, limit: int = 5) -> List[Tuple]:
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM words ORDER BY created_at DESC LIMIT ?", (limit,))
        return cursor.fetchall()
    
    def update_review(self, word_id: str, quality: int) -> Optional[str]:
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
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("UPDATE words SET review_count = 0, ease_factor = 2.5, interval = 1, next_review = ?", (now + 86400,))
        self._get_connection().commit()
    
    def delete_all_words(self):
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM words")
        self._get_connection().commit()
    
    # ===== SESSION METHODS (unchanged) =====
    
    def create_session(self, session_type: str, source_name: str = None) -> str:
        session_id = str(uuid.uuid4())[:8]
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO learning_sessions (session_id, session_type, source_name, start_time, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (session_id, session_type, source_name, now))
        self._get_connection().commit()
        return session_id
    
    def end_session(self, session_id: str):
        cursor = self._get_cursor()
        cursor.execute("""
            UPDATE learning_sessions 
            SET end_time = ?, is_active = 0 
            WHERE session_id = ?
        """, (int(time.time()), session_id))
        self._get_connection().commit()
    
    def get_active_session(self) -> Optional[Dict]:
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT session_id, session_type, source_name, start_time, word_count
            FROM learning_sessions
            WHERE is_active = 1
            ORDER BY start_time DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "session_id": row[0],
            "session_type": row[1],
            "source_name": row[2],
            "start_time": row[3],
            "word_count": row[4]
        }
    
    def add_word_to_session(self, session_id: str, word_id: str):
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO session_words (session_id, word_id, added_at)
            VALUES (?, ?, ?)
        """, (session_id, word_id, int(time.time())))
        cursor.execute("""
            UPDATE learning_sessions 
            SET word_count = (SELECT COUNT(*) FROM session_words WHERE session_id = ?)
            WHERE session_id = ?
        """, (session_id, session_id))
        self._get_connection().commit()
    
    def get_session_words(self, session_id: str) -> List[Dict]:
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT w.word, w.translation, sw.added_at
            FROM session_words sw
            JOIN words w ON sw.word_id = w.id
            WHERE sw.session_id = ?
            ORDER BY sw.added_at
        """, (session_id,))
        return [{"word": r[0], "translation": r[1], "added_at": r[2]} for r in cursor.fetchall()]
    
    def get_all_sessions(self, limit: int = 20) -> List[Dict]:
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT session_id, session_type, source_name, start_time, end_time, word_count
            FROM learning_sessions
            ORDER BY start_time DESC
            LIMIT ?
        """, (limit,))
        return [{
            "session_id": r[0],
            "session_type": r[1],
            "source_name": r[2],
            "start_time": r[3],
            "end_time": r[4],
            "word_count": r[5]
        } for r in cursor.fetchall()]
    
    def _get_cursor(self):
        return self._get_connection().cursor()
    
    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()