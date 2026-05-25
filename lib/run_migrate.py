# migrate_to_chains.py
import sqlite3
import json

def migrate():
    conn = sqlite3.connect("vocab.db")
    cursor = conn.cursor()
    
    # Check if tables exist and create if needed
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_type TEXT NOT NULL,
            content TEXT,
            title TEXT,
            metadata TEXT,
            path_json TEXT,
            session_id TEXT,
            source_text_id TEXT,
            created_at INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_node_id INTEGER,
            to_node_id INTEGER,
            edge_type TEXT,
            position_start INTEGER,
            position_end INTEGER,
            weight REAL DEFAULT 1.0,
            created_at INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id TEXT,
            content_node_id INTEGER,
            position_start INTEGER,
            position_end INTEGER,
            context_before TEXT,
            context_after TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()