"""
Unified node-based database API.
Everything is a node. Clean and simple.
"""

import sqlite3
import time
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VocabDatabase:
    """Unified node-based database. Every piece of content is a node."""

    def __init__(self, db_path: str = "vocab.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_schema()

    def _get_connection(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _get_cursor(self):
        return self._get_connection().cursor()

    def _init_schema(self):
        """Create the unified nodes table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_type TEXT NOT NULL,
                content TEXT,
                title TEXT,
                parent_id INTEGER,
                session_id INTEGER,
                created_at INTEGER,
                translation TEXT,
                priority INTEGER DEFAULT 2,
                tags TEXT,
                review_count INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                interval INTEGER DEFAULT 1,
                next_review INTEGER,
                metadata TEXT,
                FOREIGN KEY(parent_id) REFERENCES nodes(id)
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent ON nodes(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON nodes(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON nodes(node_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON nodes(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_next_review ON nodes(next_review)")

        conn.commit()
        conn.close()
        logger.info("Database schema initialized")

    # ========== CORE NODE OPERATIONS ==========

    def create_node(self, node_type: str, content: str = "", title: str = None,
                    parent_id: int = None, session_id: int = None,
                    translation: str = None, priority: int = 2,
                    tags: List[str] = None, metadata: Dict = None) -> int:
        """Create a node. Returns node ID."""
        now = int(time.time())
        tags_str = ",".join(tags) if tags else None
        metadata_str = str(metadata) if metadata else None
        
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO nodes (node_type, content, title, parent_id, session_id, created_at,
                              translation, priority, tags, metadata, review_count, ease_factor, interval, next_review)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (node_type, content[:5000] if content else None, title, parent_id, session_id, now,
              translation, priority, tags_str, metadata_str, 0, 2.5, 1, now + 86400))
        
        node_id = cursor.lastrowid
        self._get_connection().commit()
        return node_id

    def get_node(self, node_id: int) -> Optional[Dict]:
        """Get node by ID."""
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_node(self, node_id: int, **kwargs):
        """Update node fields."""
        cursor = self._get_cursor()
        fields = []
        values = []
        for key, value in kwargs.items():
            if key == 'tags' and isinstance(value, list):
                value = ",".join(value)
            if key == 'metadata' and isinstance(value, dict):
                value = str(value)
            fields.append(f"{key} = ?")
            values.append(value)
        if not fields:
            return
        values.append(node_id)
        cursor.execute(f"UPDATE nodes SET {', '.join(fields)} WHERE id = ?", values)
        self._get_connection().commit()

    def delete_node(self, node_id: int):
        """Delete node and all descendants."""
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM nodes WHERE id = ? OR parent_id = ?", (node_id, node_id))
        self._get_connection().commit()

    # ========== QUERY METHODS ==========

    def get_children(self, node_id: int, node_type: str = None) -> List[Dict]:
        """Get children of a node."""
        cursor = self._get_cursor()
        if node_type:
            cursor.execute("""
                SELECT * FROM nodes WHERE parent_id = ? AND node_type = ?
                ORDER BY created_at ASC
            """, (node_id, node_type))
        else:
            cursor.execute("""
                SELECT * FROM nodes WHERE parent_id = ?
                ORDER BY created_at ASC
            """, (node_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_parent(self, node_id: int) -> Optional[Dict]:
        """Get parent of a node."""
        node = self.get_node(node_id)
        if not node or not node.get('parent_id'):
            return None
        return self.get_node(node['parent_id'])

    def get_chain(self, node_id: int) -> List[Dict]:
        """Get full chain from root to node."""
        cursor = self._get_cursor()
        cursor.execute("""
            WITH RECURSIVE chain AS (
                SELECT * FROM nodes WHERE id = ?
                UNION ALL
                SELECT n.* FROM nodes n JOIN chain c ON n.id = c.parent_id
            )
            SELECT * FROM chain ORDER BY created_at ASC
        """, (node_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_nodes(self, limit: int = 20, node_type: str = None) -> List[Dict]:
        """Get most recent nodes."""
        cursor = self._get_cursor()
        if node_type:
            cursor.execute("""
                SELECT * FROM nodes WHERE node_type = ?
                ORDER BY created_at DESC LIMIT ?
            """, (node_type, limit))
        else:
            cursor.execute("SELECT * FROM nodes ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_last_node_id(self) -> Optional[int]:
        """Get most recent node ID."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM nodes ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        return row['id'] if row else None

    # ========== WORD-RELATED METHODS (Convenience wrappers) ==========

    def create_word(self, word: str, translation: str, example: str = "",
                    session_id: int = None, parent_id: int = None) -> int:
        """Create a word node."""
        return self.create_node(
            node_type='word',
            content=word,
            title=word,
            translation=translation,
            example_sentence=example,
            session_id=session_id,
            parent_id=parent_id
        )

    def get_word(self, word: str) -> Optional[Dict]:
        """Get word node by word text."""
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM nodes WHERE node_type = 'word' AND content = ?", (word,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_word_id(self, word: str) -> Optional[int]:
        """Get word ID by word text."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM nodes WHERE node_type = 'word' AND content = ?", (word,))
        row = cursor.fetchone()
        return row['id'] if row else None

    def get_due_words(self, limit: int = 50) -> List[Dict]:
        """Get words due for review."""
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT * FROM nodes
            WHERE node_type = 'word' AND (next_review <= ? OR next_review IS NULL)
            ORDER BY next_review ASC LIMIT ?
        """, (now, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_words(self, limit: int = 10) -> List[Dict]:
        """Get most recently added words."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT * FROM nodes
            WHERE node_type = 'word'
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def update_word_review(self, word_id: int, quality: int) -> str:
        """Update review using SM-2 algorithm. Returns next review date."""
        node = self.get_node(word_id)
        if not node:
            return None

        review_count = node['review_count'] + 1
        ease_factor = node['ease_factor']
        interval = node['interval']

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
        
        self.update_node(word_id,
                        review_count=review_count,
                        ease_factor=ease_factor,
                        interval=interval,
                        next_review=next_review)
        
        return datetime.fromtimestamp(next_review).strftime('%Y-%m-%d')

    # ========== SESSION METHODS ==========

    def create_session(self, session_type: str, source_name: str = None) -> int:
        """Create a session node."""
        title = f"{session_type}: {source_name}" if source_name else session_type
        return self.create_node('session', content=title, title=title)

    def get_active_session(self) -> Optional[Dict]:
        """Get most recent session."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT * FROM nodes WHERE node_type = 'session'
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            return None
        
        session = dict(row)
        # Count words in this session
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE session_id = ? AND node_type = 'word'", (session['id'],))
        session['word_count'] = cursor.fetchone()[0]
        return session

    def get_session_words(self, session_id: int) -> List[Dict]:
        """Get all words in a session."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT * FROM nodes
            WHERE session_id = ? AND node_type = 'word'
            ORDER BY created_at ASC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_sessions(self, limit: int = 20) -> List[Dict]:
        """Get all sessions."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT * FROM nodes WHERE node_type = 'session'
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        sessions = []
        for row in cursor.fetchall():
            session = dict(row)
            cursor2 = self._get_cursor()
            cursor2.execute("SELECT COUNT(*) FROM nodes WHERE session_id = ? AND node_type = 'word'", (session['id'],))
            session['word_count'] = cursor2.fetchone()[0]
            sessions.append(session)
        return sessions

    # ========== CONTENT NODE METHODS ==========

    def create_content_node(self, node_type: str, content: str, title: str = None,
                            parent_id: int = None, session_id: int = None,
                            metadata: Dict = None) -> int:
        """Create a content node (query, response, raw_text, etc.)."""
        return self.create_node(
            node_type=node_type,
            content=content,
            title=title or content[:50],
            parent_id=parent_id,
            session_id=session_id,
            metadata=metadata
        )

    def record_word_occurrence(self, word: str, content_node_id: int):
        """Record that a word appeared in content (creates reference)."""
        word_node = self.get_word(word)
        if word_node:
            # Link word to content as parent reference
            self.update_node(word_node['id'], parent_id=content_node_id)

    def find_related_words(self, word: str, max_hops: int = 2) -> List[Dict]:
        """Find words that appear in same contexts."""
        cursor = self._get_cursor()
        # Find content nodes containing this word
        cursor.execute("""
            SELECT DISTINCT parent_id
            FROM nodes
            WHERE content LIKE ? AND node_type != 'word'
            LIMIT 10
        """, (f"%{word}%",))
        parent_ids = [row['parent_id'] for row in cursor.fetchall() if row['parent_id']]

        if not parent_ids:
            return []

        # Find other words under same parents
        placeholders = ",".join(["?"] * len(parent_ids))
        cursor.execute(f"""
            SELECT DISTINCT n.content as word, COUNT(*) as frequency
            FROM nodes n
            WHERE n.parent_id IN ({placeholders})
            AND n.node_type = 'word'
            AND n.content != ?
            GROUP BY n.content
            ORDER BY frequency DESC
            LIMIT 10
        """, parent_ids + [word])
        return [dict(row) for row in cursor.fetchall()]

    # ========== UTILITIES ==========

    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()