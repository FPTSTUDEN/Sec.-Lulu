"""
Ultra-minimal vocabulary database with backward compatibility.
Single-table design: everything is a node.
Old method names are preserved as wrappers.
"""

import sqlite3
import uuid
import time
import threading
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VocabDatabase:
    """Unified interface - everything is a node. Backward compatible."""

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

    def _get_cursor(self):
        return self._get_connection().cursor()

    def _init_schema(self):
        """Create the single-table schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # The one table to rule them all
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                content TEXT,
                parent_id INTEGER,
                session_id INTEGER,
                title TEXT,
                created_at INTEGER,
                translation TEXT,
                priority INTEGER DEFAULT 2,
                tags TEXT,
                review_count INTEGER DEFAULT 0,
                ease_factor REAL DEFAULT 2.5,
                interval INTEGER DEFAULT 1,
                next_review INTEGER,
                example_sentence TEXT,
                FOREIGN KEY(parent_id) REFERENCES nodes(id),
                FOREIGN KEY(session_id) REFERENCES nodes(id)
            )
        """)

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent ON nodes(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON nodes(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON nodes(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON nodes(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_next_review ON nodes(next_review)")

        conn.commit()
        conn.close()
        logger.info("Database schema initialized")

    # ===== CORE NODE OPERATIONS =====

    def create_node(self, node_type: str, content: str = "", title: str = None,
                    parent_id: int = None, session_id: int = None,
                    translation: str = None, priority: int = 2, tags: List[str] = None,
                    example_sentence: str = None) -> int:
        """Create any node. Returns node ID."""
        now = int(time.time())
        tags_str = ",".join(tags) if tags else None
        cursor = self._get_cursor()

        cursor.execute("""
            INSERT INTO nodes (type, content, title, parent_id, session_id, created_at,
                              translation, priority, tags, example_sentence,
                              review_count, ease_factor, interval, next_review)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (node_type, content[:5000] if content else None, title, parent_id, session_id, now,
              translation, priority, tags_str, example_sentence,
              0, 2.5, 1, now + 86400))

        node_id = cursor.lastrowid
        self._get_connection().commit()
        return node_id

    def get_node(self, node_id: int) -> Optional[Dict]:
        """Get a node by ID."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, type, content, title, parent_id, session_id, created_at,
                   translation, priority, tags, example_sentence,
                   review_count, ease_factor, interval, next_review
            FROM nodes WHERE id = ?
        """, (node_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "type": row[1],
            "content": row[2],
            "title": row[3],
            "parent_id": row[4],
            "session_id": row[5],
            "created_at": row[6],
            "translation": row[7],
            "priority": row[8],
            "tags": row[9].split(",") if row[9] else [],
            "example_sentence": row[10],
            "review_count": row[11],
            "ease_factor": row[12],
            "interval": row[13],
            "next_review": row[14]
        }

    def update_node(self, node_id: int, **kwargs):
        """Update node fields."""
        cursor = self._get_cursor()
        fields = []
        values = []
        for key, value in kwargs.items():
            if key == 'tags' and isinstance(value, list):
                value = ",".join(value)
            fields.append(f"{key} = ?")
            values.append(value)
        if not fields:
            return
        values.append(node_id)
        cursor.execute(f"UPDATE nodes SET {', '.join(fields)} WHERE id = ?", values)
        self._get_connection().commit()

    def delete_node(self, node_id: int):
        """Delete a node and all its children."""
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM nodes WHERE id = ? OR parent_id = ?", (node_id, node_id))
        self._get_connection().commit()

    # ===== BACKWARD COMPATIBLE: WORD METHODS =====

    def add_word(self, word: str, translation: str, example: str = "") -> str:
        """Backward compatible: add word returns string ID."""
        node_id = self.create_node('word', content=word, translation=translation,
                                   example_sentence=example, title=word)
        return str(node_id)

    def get_word_id(self, word: str) -> Optional[str]:
        """Backward compatible: get word ID as string."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM nodes WHERE type = 'word' AND content = ?", (word,))
        row = cursor.fetchone()
        return str(row[0]) if row else None

    def get_due_words(self) -> List[Tuple]:
        """Backward compatible: returns list of tuples with full word data."""
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, content, translation, example_sentence, created_at,
                   review_count, ease_factor, interval, next_review
            FROM nodes
            WHERE type = 'word' AND (next_review <= ? OR next_review IS NULL)
            ORDER BY next_review ASC
        """, (now,))
        rows = cursor.fetchall()
        # Convert to tuple format expected by old code
        return [tuple(row) for row in rows]

    def get_recent_words(self, limit: int = 5) -> List[Tuple]:
        """Backward compatible: returns list of tuples."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, content, translation, example_sentence, created_at,
                   review_count, ease_factor, interval, next_review
            FROM nodes
            WHERE type = 'word'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [tuple(row) for row in rows]

    def get_word_stats(self, word_id: str) -> Dict:
        """Backward compatible: get word stats."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT review_count, ease_factor, interval, next_review
            FROM nodes WHERE id = ? AND type = 'word'
        """, (int(word_id),))
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
        """Backward compatible: update review using SM-2."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT review_count, ease_factor, interval, next_review
            FROM nodes WHERE id = ? AND type = 'word'
        """, (int(word_id),))
        row = cursor.fetchone()
        if not row:
            return None

        review_count, ease_factor, interval, _ = row
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
            UPDATE nodes
            SET review_count = ?, ease_factor = ?, interval = ?, next_review = ?
            WHERE id = ?
        """, (review_count, ease_factor, interval, next_review, int(word_id)))
        self._get_connection().commit()

        return datetime.fromtimestamp(next_review).strftime('%Y-%m-%d')

    def reset_all_reviews(self):
        """Reset all review statistics."""
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            UPDATE nodes
            SET review_count = 0, ease_factor = 2.5, interval = 1, next_review = ?
            WHERE type = 'word'
        """, (now + 86400,))
        self._get_connection().commit()

    def delete_all_words(self):
        """Delete all word nodes."""
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM nodes WHERE type = 'word'")
        self._get_connection().commit()

    # ===== BACKWARD COMPATIBLE: SESSION METHODS =====

    def create_session(self, session_type: str, source_name: str = None) -> str:
        """Backward compatible: create session returns session_id string."""
        title = f"{session_type}: {source_name}" if source_name else session_type
        node_id = self.create_node('session', title=title, content=title)
        return f"session_{node_id}"

    def get_active_session(self) -> Optional[Dict]:
        """Backward compatible: get most recently used session."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, title, created_at
            FROM nodes
            WHERE type = 'session'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            return None
        # Count words in this session
        cursor2 = self._get_cursor()
        cursor2.execute("SELECT COUNT(*) FROM nodes WHERE session_id = ? AND type = 'word'", (row[0],))
        word_count = cursor2.fetchone()[0]
        return {
            "session_id": f"session_{row[0]}",
            "session_type": row[1].split(":")[0] if row[1] else "General",
            "source_name": row[1].split(":")[1] if row[1] and ":" in row[1] else None,
            "start_time": row[2],
            "word_count": word_count
        }

    def end_session(self, session_id: str):
        """Backward compatible: no-op (sessions don't end in minimal schema)."""
        pass

    def add_word_to_session(self, session_id: str, word_id: str):
        """Backward compatible: link word to session."""
        session_int_id = int(session_id.split("_")[1]) if session_id.startswith("session_") else int(session_id)
        word_int_id = int(word_id)
        cursor = self._get_cursor()
        cursor.execute("UPDATE nodes SET session_id = ? WHERE id = ?", (session_int_id, word_int_id))
        self._get_connection().commit()

    def get_session_words(self, session_id: str) -> List[Dict]:
        """Backward compatible: get words in session."""
        session_int_id = int(session_id.split("_")[1]) if session_id.startswith("session_") else int(session_id)
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, content as word, translation, created_at
            FROM nodes
            WHERE session_id = ? AND type = 'word'
            ORDER BY created_at ASC
        """, (session_int_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_sessions(self, limit: int = 20) -> List[Dict]:
        """Backward compatible: get all sessions."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, title, created_at
            FROM nodes
            WHERE type = 'session'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        sessions = []
        for row in cursor.fetchall():
            cursor2 = self._get_cursor()
            cursor2.execute("SELECT COUNT(*) FROM nodes WHERE session_id = ? AND type = 'word'", (row[0],))
            word_count = cursor2.fetchone()[0]
            sessions.append({
                "session_id": f"session_{row[0]}",
                "session_type": row[1].split(":")[0] if row[1] else "General",
                "source_name": row[1].split(":")[1] if row[1] and ":" in row[1] else None,
                "start_time": row[2],
                "end_time": 0,
                "word_count": word_count
            })
        return sessions

    # ===== CHAIN METHODS (for ChainViewer) =====

    def get_content_chain(self, node_id: int) -> List[Dict]:
        """Get full chain from root to node (ancestors + current)."""
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

    def get_content_node(self, node_id: int) -> Optional[Dict]:
        """Alias for get_node."""
        return self.get_node(node_id)

    def get_node_children(self, node_id: int, edge_type: str = None) -> List[Dict]:
        """Get children of a node."""
        cursor = self._get_cursor()
        if edge_type:
            cursor.execute("""
                SELECT id, type as node_type, content, title, created_at
                FROM nodes WHERE parent_id = ? AND type = ?
                ORDER BY created_at ASC
            """, (node_id, edge_type))
        else:
            cursor.execute("""
                SELECT id, type as node_type, content, title, created_at
                FROM nodes WHERE parent_id = ?
                ORDER BY created_at ASC
            """, (node_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_node_parent(self, node_id: int) -> Optional[Dict]:
        """Get parent of a node."""
        node = self.get_node(node_id)
        if not node or not node.get('parent_id'):
            return None
        return self.get_node(node['parent_id'])

    def get_subtree(self, root_node_id: int, max_depth: int = 10) -> List[Dict]:
        """Get entire subtree."""
        cursor = self._get_cursor()
        cursor.execute("""
            WITH RECURSIVE subtree AS (
                SELECT id, type as node_type, content, title, parent_id, created_at, 0 as depth
                FROM nodes WHERE id = ?
                UNION ALL
                SELECT n.id, n.type, n.content, n.title, n.parent_id, n.created_at, depth + 1
                FROM nodes n
                JOIN subtree s ON n.parent_id = s.id
                WHERE depth + 1 <= ?
            )
            SELECT * FROM subtree ORDER BY depth, created_at
        """, (root_node_id, max_depth))
        return [dict(row) for row in cursor.fetchall()]

    def create_content_node(self, node_type: str, content: str, title: str = None,
                            parent_node_id: int = None, session_id: str = None,
                            metadata: Dict = None, source_text_id: str = None) -> int:
        """Create content node (for chain compatibility)."""
        session_int_id = int(session_id.split("_")[1]) if session_id and session_id.startswith("session_") else session_id
        return self.create_node(node_type, content=content, title=title,
                                parent_id=parent_node_id, session_id=session_int_id,
                                tags=list(metadata.keys()) if metadata else None)

    def get_last_content_node_id(self) -> Optional[int]:
        """Get most recent node ID."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM nodes ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None

    def find_connected_words(self, word: str, max_hops: int = 2) -> List[Dict]:
        """Find words connected through shared parents."""
        cursor = self._get_cursor()
        # Find nodes containing this word
        cursor.execute("""
            SELECT DISTINCT parent_id
            FROM nodes
            WHERE content LIKE ? AND type != 'word'
            LIMIT 10
        """, (f"%{word}%",))
        parent_ids = [row[0] for row in cursor.fetchall() if row[0]]

        if not parent_ids:
            return []

        # Find other words under same parents
        placeholders = ",".join(["?"] * len(parent_ids))
        cursor.execute(f"""
            SELECT DISTINCT n.content as word, COUNT(*) as strength
            FROM nodes n
            WHERE n.parent_id IN ({placeholders})
            AND n.type = 'word'
            AND n.content != ?
            GROUP BY n.content
            ORDER BY strength DESC
            LIMIT 10
        """, parent_ids + [word])
        return [{"word": row[0], "strength": row[1]} for row in cursor.fetchall()]

    def find_word_occurrences(self, word: str) -> List[Dict]:
        """Find where a word appears."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, type as node_type, title, created_at
            FROM nodes
            WHERE content LIKE ? AND type != 'word'
            LIMIT 20
        """, (f"%{word}%",))
        return [dict(row) for row in cursor.fetchall()]

    def record_word_occurrence(self, word_id: str, content_node_id: int,
                                position_start: int = 0, position_end: int = None,
                                context_before: str = "", context_after: str = ""):
        """Record word occurrence (simplified - just create a reference)."""
        # In minimal schema, we just ensure the word is linked to the content
        word_int_id = int(word_id)
        cursor = self._get_cursor()
        # Check if already linked
        cursor.execute("""
            SELECT id FROM nodes WHERE id = ? AND parent_id = ?
        """, (word_int_id, content_node_id))
        if not cursor.fetchone():
            cursor.execute("""
                UPDATE nodes SET parent_id = ? WHERE id = ?
            """, (content_node_id, word_int_id))
            self._get_connection().commit()

    # ===== SENTENCE ANALYSIS METHODS (backward compatible stubs) =====

    def create_sentence_analysis(self, content_id: str, title: str, original_text: str,
                                   total_sentences: int, estimated_level: str) -> int:
        """Stub for compatibility."""
        node_id = self.create_node('analysis', content=original_text[:500], title=title,
                                   tags=['sentence_analysis'])
        return node_id

    def save_analyzed_sentence(self, analysis_id: int, sentence_index: int, original: str,
                                translation: str, why_matters: str, remember_hook: str,
                                simplified_paraphrase: str = "", difficulty: int = 3) -> int:
        """Stub for compatibility."""
        node_id = self.create_node('sentence', content=original, translation=translation,
                                   parent_id=analysis_id, title=f"Sentence {sentence_index}",
                                   tags=[f"difficulty:{difficulty}"])
        return node_id

    def save_sentence_keyword(self, sentence_id: int, word: str, pinyin: str,
                               insight: str, importance: float = 0.5):
        """Stub for compatibility."""
        self.create_node('keyword', content=word, title=word,
                         parent_id=sentence_id, translation=insight)

    def get_sentences_by_analysis(self, analysis_id: int) -> List[Dict]:
        """Stub for compatibility."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, content as original, translation, created_at
            FROM nodes
            WHERE parent_id = ? AND type = 'sentence'
            ORDER BY created_at
        """, (analysis_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_sentence_analyses(self, limit: int = 20) -> List[Dict]:
        """Stub for compatibility."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, title, created_at
            FROM nodes
            WHERE type = 'analysis'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [{"id": row[0], "title": row[1], "created_at": row[2]} for row in cursor.fetchall()]

    def delete_sentence_analysis(self, analysis_id: int):
        """Stub for compatibility."""
        self.delete_node(analysis_id)

    def toggle_sentence_mastered(self, sentence_id: int, mastered: bool):
        """Stub for compatibility."""
        self.update_node(sentence_id, tags=['mastered'] if mastered else [])

    # ===== NOTE METHODS =====

    def add_sentence_note(self, sentence_id: int, note_text: str, priority: int,
                           tags: List[str], is_pinned: bool) -> int:
        """Add note to a sentence/node."""
        return self.create_node('note', content=note_text, parent_id=sentence_id,
                                priority=priority, tags=tags)

    def update_sentence_note(self, note_id: int, note_text: str, priority: int,
                              tags: List[str], is_pinned: bool):
        """Update a note."""
        self.update_node(note_id, content=note_text, priority=priority, tags=tags)

    def delete_sentence_note(self, note_id: int):
        """Delete a note."""
        self.delete_node(note_id)

    # ===== UTILITIES =====

    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()