import sqlite3
import uuid
import time


def init_db(conn,cursor):
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
    conn.commit()

def add_word(conn, cursor, word, translation, example):
    now = int(time.time())
    wordid = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        wordid,
        word,
        translation,
        example,
        now,
        0,
        2.5,
        1,
        now + 86400
    ))
    conn.commit()
    return wordid
def get_word_id(conn, cursor, word):
    cursor.execute("""
        SELECT id FROM words WHERE word = ?
    """, (word,))
    result = cursor.fetchone()
    return result[0] if result else None
def get_word_stats(conn, cursor, word_id):
    cursor.execute("""
        SELECT review_count, ease_factor, interval, next_review FROM words WHERE id = ?
    """, (word_id,))
    word_stats={}
    row=cursor.fetchone()
    if row:
        word_stats["review_count"] = row[0]
        word_stats["ease_factor"] = row[1]
        word_stats["interval"] = row[2]
        word_stats["next_review"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(row[3]))
    return word_stats
def reset_reviews(conn, cursor):
    now = int(time.time())
    cursor.execute("""
        UPDATE words SET review_count = 0, ease_factor = 2.5, interval = 1, next_review = ?
    """, (now + 86400,))
    conn.commit()
def get_due_words(conn, cursor):
    now = int(time.time())
    cursor.execute("""
        SELECT * FROM words WHERE next_review <= ?
    """, (now,))
    return cursor.fetchall()
def update_review(conn, cursor, word_id, quality):
    cursor.execute("""
        SELECT review_count, ease_factor, interval FROM words WHERE id = ?
    """, (word_id,))
    review_count, ease_factor, interval = cursor.fetchone()
    
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
    conn.commit()
def reset(conn, cursor):
    cursor.execute("DELETE FROM words")
    conn.commit()
if __name__ == "__main__":
    conn = sqlite3.connect("vocab.db")
    cursor = conn.cursor()
    init_db(conn, cursor)
    noword=get_word_id(conn,cursor,"blablah")
    if noword: print("ok")
    add_word(conn, cursor, "manger", "to eat", "Je veux manger une pomme.")
