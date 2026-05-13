"""
CEDICT lookup utility - centralized Chinese dictionary parsing and lookup.
Provides fast lookup for words and character-level fallbacks.
"""

import sqlite3
import json
import os

def parse_cedict_line(line):
    """Parse a single CEDICT line into a structured entry dict."""
    if line.startswith("#"):
        return None
    
    trad, simp, rest = line.split(" ", 2)
    pinyin = rest.split("]")[0][1:]
    defs = rest.split("/")[1:-1]
    
    return {
        "traditional": trad,
        "simplified": simp,
        "pinyin": pinyin,
        "definitions": defs
    }


def create_cedict_db(cedict_path="cedict_ts.u8", db_path="cedict.db"):
    """Create SQLite database from CEDICT text file."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY,
        traditional TEXT,
        simplified TEXT,
        pinyin TEXT,
        definitions TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS word_index (
        word TEXT PRIMARY KEY,
        entry_id INTEGER
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS char_index (
        char TEXT,
        entry_id INTEGER,
        PRIMARY KEY (char, entry_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS char_def_index (
        char TEXT PRIMARY KEY,
        entry_id INTEGER
    )''')
    
    # Load and insert data
    with open(cedict_path, encoding="utf-8") as f:
        for line in f:
            entry = parse_cedict_line(line)
            if entry:
                # Insert entry
                c.execute('''INSERT INTO entries (traditional, simplified, pinyin, definitions)
                           VALUES (?, ?, ?, ?)''',
                         (entry["traditional"], entry["simplified"], entry["pinyin"], json.dumps(entry["definitions"])))
                entry_id = c.lastrowid
                
                simp = entry["simplified"]
                
                # Word index
                c.execute('INSERT OR REPLACE INTO word_index (word, entry_id) VALUES (?, ?)', (simp, entry_id))
                c.execute('INSERT OR REPLACE INTO word_index (word, entry_id) VALUES (?, ?)', (entry["traditional"], entry_id))
                
                # Char index
                for char in simp:
                    c.execute('INSERT OR IGNORE INTO char_index (char, entry_id) VALUES (?, ?)', (char, entry_id))
                
                # Char def index (only single chars)
                if len(simp) == 1:
                    c.execute('INSERT OR REPLACE INTO char_def_index (char, entry_id) VALUES (?, ?)', (simp, entry_id))
    
    conn.commit()
    conn.close()


def load_cedict_entries(cedict_path="cedict_ts.u8", db_path="cedict.db"):
    """Load and index all CEDICT entries for fast lookup. Uses SQLite cache if available."""
    if not os.path.exists(db_path):
        print("Creating CEDICT SQLite database...")
        create_cedict_db(cedict_path, db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Load entries
    entries = []
    c.execute('SELECT id, traditional, simplified, pinyin, definitions FROM entries')
    for row in c.fetchall():
        entry = {
            "traditional": row[1],
            "simplified": row[2],
            "pinyin": row[3],
            "definitions": json.loads(row[4])
        }
        entries.append(entry)
    
    # Build indices
    word_index = {}
    char_index = {}
    char_def_index = {}
    
    # Word index
    c.execute('SELECT word, entry_id FROM word_index')
    for word, entry_id in c.fetchall():
        word_index[word] = entries[entry_id - 1]  # entries list is 0-based
    
    # Char index
    c.execute('SELECT char, entry_id FROM char_index')
    for char, entry_id in c.fetchall():
        if char not in char_index:
            char_index[char] = []
        char_index[char].append(entries[entry_id - 1])
    
    # Char def index
    c.execute('SELECT char, entry_id FROM char_def_index')
    for char, entry_id in c.fetchall():
        char_def_index[char] = entries[entry_id - 1]
    
    conn.close()
    return entries, word_index, char_index, char_def_index


def lookup_cedict(word, word_index, char_def_index):
    """
    Lookup a word in CEDICT indices.
    Returns (word_entry, char_matches) tuple:
    - word_entry: Direct match entry for the word, or None
    - char_matches: List of (char, entry) tuples for individual CHARACTER definitions only (not phrases)
    
    Args:
        word: Word to lookup
        word_index: Index of all words
        char_def_index: Index of ONLY single-character definitions
    """
    # Try direct word lookup
    if word in word_index:
        return word_index[word], []
    
    # Fallback: character-level lookup using ONLY single-character definitions
    char_matches = []
    for char in word:
        if char in char_def_index:
            entry = char_def_index[char]
            char_matches.append((char, entry))
    
    return None, char_matches


def extract_chinese_word_at_position(text, position, word_index):
    """
    Extract the longest valid Chinese word from the dictionary starting at the given position.
    Uses greedy longest-match: tries 1 char, 2 chars, 3 chars, etc. from position forward.
    Returns the longest matching word and its start/end indices in the text.
    
    Args:
        text: Full text to search in
        position: Starting position (cursor position)
        word_index: Dictionary of valid words from CEDICT
    
    Returns:
        (word, start, end) tuple. Returns (None, -1, -1) if no match found.
    """
    # Check if position is within text
    if position >= len(text):
        return None, -1, -1
    
    char = text[position]
    if not is_chinese_char(char):
        return None, -1, -1
    
    # Greedy longest-match: try progressively longer substrings
    longest_word = None
    longest_end = position
    
    # Try matching up to 20 characters ahead (reasonable max for Chinese phrases)
    max_length = 20
    for length in range(1, min(max_length + 1, len(text) - position + 1)):
        candidate = text[position:position + length]
        
        # All characters must be CJK
        if not all(is_chinese_char(c) for c in candidate):
            break  # Stop if we hit non-CJK character
        
        # Check if this candidate is in the dictionary
        if candidate in word_index:
            longest_word = candidate
            longest_end = position + length
    
    if longest_word:
        return longest_word, position, longest_end
    
    # Fallback: return single character if it's in the dictionary
    if text[position] in word_index:
        return text[position], position, position + 1
    
    return None, -1, -1


def is_chinese_char(char):
    """Check if a character is a CJK unified ideograph."""
    code = ord(char)
    return 0x4E00 <= code <= 0x9FFF
