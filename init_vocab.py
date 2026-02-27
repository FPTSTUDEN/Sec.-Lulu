"""
Helper script to initialize the database with test vocabulary data
Run this before starting the main app to have sample words to review
"""

import os
import sys
from lib.database import Database
from lib.profile_manager import add_word
import sqlite3


def add_test_words(db_path="vocab.db"):
    """Add test vocabulary words to the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Sample vocabulary words
    test_words = [
        ("manger", "to eat", "Je veux manger une pomme."),
        ("boire", "to drink", "Je bois de l'eau."),
        ("parler", "to speak", "Tu parles français?"),
        ("écrire", "to write", "Elle écrit un livre."),
        ("lire", "to read", "Nous lisons un journal."),
        ("comprendre", "to understand", "Je comprends le français."),
        ("venir", "to come", "Ils viennent demain."),
        ("aller", "to go", "Où vas-tu?"),
        ("pouvoir", "can/to be able", "Je peux t'aider."),
        ("vouloir", "to want", "Je veux du café."),
    ]
    
    from lib.profile_manager import get_word_id
    
    added = 0
    for word, translation, example in test_words:
        # Check if word already exists
        if not get_word_id(conn, cursor, word):
            add_word(conn, cursor, word, translation, example)
            added += 1
            print(f"Added: {word}")
    
    conn.close()
    print(f"\n✓ Total words added: {added}")
    return added


def show_database_status(db_path="vocab.db"):
    """Show current database status"""
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM words")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM words WHERE next_review IS NULL OR next_review <= strftime('%s', 'now')")
    due = cursor.fetchone()[0]
    
    print(f"\nDatabase Status ({db_path}):")
    print(f"  Total words: {total}")
    print(f"  Words due for review: {due}")
    
    conn.close()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=" * 50)
    print("Vocabulary Database Initializer")
    print("=" * 50)
    
    # Show current status
    show_database_status()
    
    # Ask user if they want to add test data
    if len(sys.argv) > 1 and sys.argv[1] == "--add-test":
        print("\nAdding test vocabulary words...")
        add_test_words()
    else:
        print("\nRun with --add-test flag to add sample vocabulary")
        print("Example: python init_vocab.py --add-test")
    
    show_database_status()
