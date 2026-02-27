from app_integrated import IntegratedApp
from lib.profile_manager import add_word, get_due_words

app = IntegratedApp()
print("IntegratedApp created")

# add a test word
app.database = None  # not using database class now; we want to use profile_manager directly
# ensure db exists
from lib.profile_manager import init_db, conn, cursor

# careful: profile_manager doesn't expose conn globally. let's open one here
import sqlite3
conn = sqlite3.connect("vocab.db")
cursor = conn.cursor()
init_db(conn, cursor)

wordid = add_word(conn, cursor, "testword","translation","example")
print(f"Added word id {wordid}")
print("Due words:", get_due_words(conn, cursor))
