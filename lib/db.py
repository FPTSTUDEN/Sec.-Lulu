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
import json
from lib.debug_utils import DEBUG_MODE, DebugLogger, trace_chain

DEBUG_MODE = False  # Set to True to enable detailed debug output
class VocabDatabase:
    """
    Unified interface for all vocabulary database operations.
    THREAD-SAFE: Each thread gets its own connection.
    """
    
    def __init__(self, db_path: str = "vocab.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._debug = DebugLogger("VocabDatabase")
        self._debug.info(f"Database initialized: {db_path}")
        self._init_schema()
    
    def _get_connection(self):
        """Get thread-local database connection with query logging."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            
            # Enable query logging in debug mode
            if DEBUG_MODE:
                def trace_query(sql, params=()):
                    self._debug.debug(f"SQL: {sql}")
                    if params:
                        self._debug.debug(f"Params: {params}")
                self._local.conn.set_trace_callback(trace_query)
        
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

        # ===== SESSION MANAGEMENT TABLES =====

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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT,
                created_at INTEGER,
                theme TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cluster_sessions (
                cluster_id INTEGER,
                session_id TEXT,
                FOREIGN KEY(cluster_id) REFERENCES session_clusters(id),
                FOREIGN KEY(session_id) REFERENCES learning_sessions(session_id)
            )
        """)
                # Content nodes - every piece of content that can be linked
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_type TEXT NOT NULL,  -- 'raw_text', 'sentence', 'query', 'response', 'word_lookup'
                content TEXT,
                title TEXT,
                metadata TEXT,  -- JSON string for additional data
                path_json TEXT,  -- JSON array of ancestor node IDs (fast chain retrieval)
                session_id TEXT,
                source_text_id TEXT,  -- Reference to original text source
                created_at INTEGER,
                FOREIGN KEY(session_id) REFERENCES learning_sessions(session_id)
            )
        """)

        # Content edges - relationships between nodes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_node_id INTEGER,
                to_node_id INTEGER,
                edge_type TEXT,  -- 'triggered_by', 'contains', 'clicked_from', 'refers_to'
                position_start INTEGER,
                position_end INTEGER,
                weight REAL DEFAULT 1.0,
                created_at INTEGER,
                FOREIGN KEY(from_node_id) REFERENCES content_nodes(id),
                FOREIGN KEY(to_node_id) REFERENCES content_nodes(id)
            )
        """)

        # Word occurrences in content nodes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id TEXT,
                content_node_id INTEGER,
                position_start INTEGER,
                position_end INTEGER,
                context_before TEXT,
                context_after TEXT,
                FOREIGN KEY(word_id) REFERENCES words(id),
                FOREIGN KEY(content_node_id) REFERENCES content_nodes(id)
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
    
        # ===== SESSION MANAGEMENT METHODS =====

    def create_session(self, session_type: str, source_name: str = None) -> str:
        """Create a new learning session. Returns session_id."""
        import uuid
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
        """End an active session."""
        cursor = self._get_cursor()
        cursor.execute("""
            UPDATE learning_sessions 
            SET end_time = ?, is_active = 0 
            WHERE session_id = ?
        """, (int(time.time()), session_id))
        self._get_connection().commit()

    def get_active_session(self) -> Optional[Dict]:
        """Get the currently active session."""
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
        """Link a word to a session."""
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
        """Get all words in a session."""
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
        """Get all sessions for browsing."""
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

    def find_related_sessions(self, session_id: str) -> List[Dict]:
        """Find sessions with overlapping vocabulary."""
        cursor = self._get_cursor()
        cursor.execute("""
            WITH session_words AS (
                SELECT word_id FROM session_words WHERE session_id = ?
            )
            SELECT DISTINCT ls.session_id, ls.session_type, ls.source_name, 
                COUNT(sw.word_id) as common_words
            FROM learning_sessions ls
            JOIN session_words sw ON ls.session_id = sw.session_id
            WHERE sw.word_id IN (SELECT word_id FROM session_words)
            AND ls.session_id != ?
            GROUP BY ls.session_id
            ORDER BY common_words DESC
            LIMIT 5
        """, (session_id, session_id))
        return [{
            "session_id": r[0],
            "session_type": r[1],
            "source_name": r[2],
            "common_words": r[3]
        } for r in cursor.fetchall()]

    def create_session_cluster(self, session_ids: List[str], theme: str = None) -> int:
        """Group multiple related sessions into a cluster."""
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO session_clusters (cluster_name, created_at, theme)
            VALUES (?, ?, ?)
        """, (f"Cluster_{now}", now, theme))
        cluster_id = cursor.lastrowid
        
        for session_id in session_ids:
            cursor.execute("""
                INSERT INTO cluster_sessions (cluster_id, session_id)
                VALUES (?, ?)
            """, (cluster_id, session_id))
        
        self._get_connection().commit()
        return cluster_id

    def get_session_clusters(self) -> List[Dict]:
        """Get all session clusters."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, cluster_name, created_at, theme
            FROM session_clusters
            ORDER BY created_at DESC
        """)
        return [{
            "id": r[0],
            "cluster_name": r[1],
            "created_at": r[2],
            "theme": r[3]
        } for r in cursor.fetchall()]
    # ===== CONTENT CHAIN METHODS =====

    def debug_print_chain(self, node_id: int):
        """Print detailed chain information for debugging"""
        self._debug.debug(f"=" * 60)
        self._debug.debug(f"CHAIN DEBUG for node_id={node_id}")
        
        # Get node
        node = self.get_content_node(node_id)
        if not node:
            self._debug.error(f"Node {node_id} not found!")
            return
        
        self._debug.debug(f"Node: type={node['node_type']}, title={node.get('title', 'N/A')[:50]}")
        self._debug.debug(f"Path JSON: {node.get('path_json', 'None')}")
        
        # Parse path
        path_ids = []
        if node.get('path_json'):
            try:
                path_ids = json.loads(node['path_json'])
                self._debug.debug(f"Parsed path IDs: {path_ids}")
            except:
                self._debug.error(f"Failed to parse path_json: {node['path_json']}")
        
        # Get ancestors
        self._debug.debug(f"Ancestors count: {len(path_ids)}")
        for i, aid in enumerate(reversed(path_ids)):
            ancestor = self.get_content_node(aid)
            if ancestor:
                self._debug.debug(f"  Ancestor {i}: id={aid}, type={ancestor['node_type']}, title={ancestor.get('title', 'N/A')[:40]}")
            else:
                self._debug.warning(f"  Ancestor {i}: id={aid} NOT FOUND!")
        
        # Get children
        children = self.get_node_children(node_id)
        self._debug.debug(f"Children count: {len(children)}")
        for child in children:
            self._debug.debug(f"  Child: id={child['id']}, type={child['node_type']}, title={child.get('title', 'N/A')[:40]}")
        
        # Check edges
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT from_node_id, to_node_id, edge_type, created_at 
            FROM content_edges 
            WHERE from_node_id=? OR to_node_id=?
            ORDER BY created_at
        """, (node_id, node_id))
        edges = cursor.fetchall()
        self._debug.debug(f"Edges involving node: {len(edges)}")
        for edge in edges:
            self._debug.debug(f"  Edge: {edge[0]} -> {edge[1]} ({edge[2]}) at {edge[3]}")
        
        self._debug.debug(f"=" * 60)
    
    @trace_chain
    def create_content_node(self, node_type: str, content: str, title: str = None,
                            parent_node_id: int = None, session_id: str = None,
                            metadata: Dict = None, source_text_id: str = None) -> int:
        """Create a content node with automatic JSON path building."""
        self._debug.debug(f"Creating content node: type={node_type}, parent={parent_node_id}, title={title[:50] if title else 'None'}")
        
        now = int(time.time())
        cursor = self._get_cursor()
        
        # Build path JSON from parent
        path_json = "[]"
        if parent_node_id:
            self._debug.debug(f"Building path from parent {parent_node_id}")
            cursor.execute("SELECT path_json FROM content_nodes WHERE id = ?", (parent_node_id,))
            row = cursor.fetchone()
            if row:
                parent_path = json.loads(row[0]) if row[0] else []
                path_json = json.dumps(parent_path + [parent_node_id])
                self._debug.debug(f"Parent path: {parent_path} -> New path: {path_json}")
            else:
                self._debug.warning(f"Parent node {parent_node_id} not found!")
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        cursor.execute("""
            INSERT INTO content_nodes (node_type, content, title, metadata, path_json, session_id, source_text_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (node_type, content[:5000], title, metadata_json, path_json, session_id, source_text_id, now))
        
        node_id = cursor.lastrowid
        self._debug.info(f"Created node {node_id}: type={node_type}")
        self._get_connection().commit()
        
        # Create edge to parent if parent exists
        if parent_node_id:
            self._debug.debug(f"Creating edge from {parent_node_id} -> {node_id}")
            self.create_content_edge(parent_node_id, node_id, 'triggered_by')
        
        # Debug: Print the chain after creation
        self.debug_print_chain(node_id)
        
        return node_id
    
    def create_content_edge(self, from_node_id: int, to_node_id: int, edge_type: str,
                            position_start: int = None, position_end: int = None, weight: float = 1.0) -> int:
        """Create a directed edge between two content nodes."""
        now = int(time.time())
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO content_edges (from_node_id, to_node_id, edge_type, position_start, position_end, weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_node_id, to_node_id, edge_type, position_start, position_end, weight, now))
        self._get_connection().commit()
        return cursor.lastrowid

    def get_content_node(self, node_id: int) -> Optional[Dict]:
        """Get a content node by ID."""
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT id, node_type, content, title, metadata, path_json, session_id, source_text_id, created_at
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
            "path_json": row[5],
            "session_id": row[6],
            "source_text_id": row[7],
            "created_at": row[8]
        }

    @trace_chain
    def get_content_chain(self, node_id: int, max_depth: int = 10) -> List[Dict]:
        """Get the full chain of ancestors for a node using JSON path."""
        self._debug.debug(f"Getting content chain for node {node_id}")
        
        node = self.get_content_node(node_id)
        if not node:
            self._debug.warning(f"Node {node_id} not found")
            return []
        
        chain = [node]
        
        # Parse the path JSON to get ancestor IDs
        path_ids = []
        if node.get('path_json'):
            try:
                path_ids = json.loads(node['path_json'])
                self._debug.debug(f"Path IDs from JSON: {path_ids} (length={len(path_ids)})")
            except json.JSONDecodeError as e:
                self._debug.error(f"Failed to parse path_json: {e}, value={node['path_json']}")
        
        # Fetch ancestors in reverse order (oldest first)
        ancestors_found = 0
        for ancestor_id in reversed(path_ids):
            self._debug.debug(f"Fetching ancestor {ancestor_id}")
            ancestor = self.get_content_node(ancestor_id)
            if ancestor:
                chain.insert(0, ancestor)
                ancestors_found += 1
                self._debug.debug(f"  Added ancestor: id={ancestor_id}, type={ancestor['node_type']}")
            else:
                self._debug.warning(f"  Ancestor {ancestor_id} not found in database!")
        
        self._debug.info(f"Chain for node {node_id}: {len(chain)} nodes total ({ancestors_found} ancestors + current)")
        
        # Log chain summary
        for i, node_in_chain in enumerate(chain):
            self._debug.debug(f"  Chain[{i}]: id={node_in_chain['id']}, type={node_in_chain['node_type']}, title={node_in_chain.get('title', 'N/A')[:40]}")
        
        return chain
    
    @trace_chain
    def get_node_children(self, node_id: int, edge_type: str = None) -> List[Dict]:
        """Get children nodes (what this node led to)."""
        self._debug.debug(f"Getting children for node {node_id}, edge_type={edge_type}")
        
        cursor = self._get_cursor()
        query = """
            SELECT cn.* FROM content_nodes cn
            JOIN content_edges ce ON cn.id = ce.to_node_id
            WHERE ce.from_node_id = ?
        """
        params = [node_id]
        if edge_type:
            query += " AND ce.edge_type = ?"
            params.append(edge_type)
        query += " ORDER BY ce.created_at"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        children = []
        for row in rows:
            child = {
                "id": row[0],
                "node_type": row[1],
                "content": row[2],
                "title": row[3],
                "created_at": row[8]
            }
            children.append(child)
            self._debug.debug(f"  Child found: id={child['id']}, type={child['node_type']}")
        
        self._debug.info(f"Found {len(children)} children for node {node_id}")
        return children
    
    @trace_chain
    def record_word_occurrence(self, word_id: str, content_node_id: int,
                            position_start: int, position_end: int,
                            context_before: str = "", context_after: str = ""):
        """Record where a word appears in a content node."""
        cursor = self._get_cursor()
        cursor.execute("""
            INSERT INTO word_occurrences (word_id, content_node_id, position_start, position_end, context_before, context_after)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (word_id, content_node_id, position_start, position_end, context_before[:50], context_after[:50]))
        self._get_connection().commit()

    def find_word_occurrences(self, word: str) -> List[Dict]:
        """Find all occurrences of a word across content nodes."""
        word_id = self.get_word_id(word)
        if not word_id:
            return []
        
        cursor = self._get_cursor()
        cursor.execute("""
            SELECT wo.*, cn.node_type, cn.title, cn.content
            FROM word_occurrences wo
            JOIN content_nodes cn ON wo.content_node_id = cn.id
            WHERE wo.word_id = ?
            ORDER BY cn.created_at DESC
        """, (word_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "content_node_id": row[1],
                "node_type": row[8],
                "title": row[9],
                "context": row[6] + row[7] if row[6] or row[7] else None,
                "position_start": row[3],
                "position_end": row[4]
            })
        return results

    def find_connected_words(self, word: str, max_hops: int = 2) -> List[Dict]:
        """
        Find words connected to this word through content chains.
        Uses the JSON path relationships.
        """
        word_id = self.get_word_id(word)
        if not word_id:
            return []
        
        cursor = self._get_cursor()
        # Find all content nodes containing this word
        cursor.execute("""
            SELECT DISTINCT cn.id, cn.path_json
            FROM word_occurrences wo
            JOIN content_nodes cn ON wo.content_node_id = cn.id
            WHERE wo.word_id = ?
        """, (word_id,))
        
        related_words = {}
        
        for row in cursor.fetchall():
            content_node_id = row[0]
            path_json = row[1]
            
            # Find other words in same or connected content nodes
            cursor2 = self._get_cursor()
            cursor2.execute("""
                SELECT DISTINCT w.word, COUNT(*) as strength
                FROM word_occurrences wo2
                JOIN words w ON wo2.word_id = w.id
                WHERE wo2.content_node_id = ?
                AND w.id != ?
                GROUP BY w.word
                ORDER BY strength DESC
                LIMIT 10
            """, (content_node_id, word_id))
            
            for r in cursor2.fetchall():
                related_words[r[0]] = related_words.get(r[0], 0) + r[1]
        
        # Sort by strength
        sorted_words = sorted(related_words.items(), key=lambda x: x[1], reverse=True)
        return [{"word": w, "strength": s} for w, s in sorted_words[:10]]

    def get_last_content_node_id(self) -> Optional[int]:
        """Get the ID of the most recently created content node."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM content_nodes ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()