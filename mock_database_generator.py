'''
This file generates a mock database for testing purposes. It creates a SQLite database with the same schema as the production database and populates it with sample data. This allows us to test our application without affecting the real data.
'''
import sqlite3
import time
import uuid
from lib.db import VocabDatabase
class MockDatabaseGenerator(VocabDatabase):
    """Generates a mock database with sample data for testing."""
    
    def __init__(self, db_path="mock_vocab.db"):
        super().__init__(db_path)
        self._populate_mock_data()
    
    def _populate_mock_data(self):
        """Populate the database with sample words due now for review."""
        sample_words = [
            ("你好", "Hello", "你好！很高兴见到你。"),
            # ("谢谢", "Thank you", "谢谢你的帮助！"),
            # ("再见", "Goodbye", "再见！下次见。"),
            ("学习", "Study", "我喜欢学习中文。"),
            ("朋友", "Friend", "他是我的好朋友。")
        ]
        
        for word, translation, example in sample_words:
            # words are created 2 days from now to ensure they are due for review
            created_at = int(time.time()) - 2 * 86400
            word_id = str(uuid.uuid4())
            self.cursor.execute("""
                INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                word_id, word, translation, example, created_at,
                0,      # review_count
                2.5,    # ease_factor
                1,      # interval
                created_at + 86400  # next_review (1 day from creation)
            ))
        self.conn.commit()

if __name__ == "__main__":
    generator = MockDatabaseGenerator()
    print("Mock database generated with sample data.")
        