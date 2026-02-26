# simple_clipboard_monitor.py
import pyperclip
from lib.windows import *
from lib.profile_manager import *
from lib.learner_prompts import *
import requests
import time
import os
# from datetime import datetime


# popup_message("Clipboard Monitor", "This program will monitor your clipboard for Chinese text and provide explanations. Press Ctrl+C to stop.")
class SimpleChineseLearner:
    def __init__(self):
        self.last_text = ""
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen2.5:7b"
    
    def get_explanation(self, text):
        wordid=get_word_id(conn, cursor, text)
        print(wordid)
        if wordid:
            update_review(conn, cursor, wordid, 3) # Assume user is having trouble remembering the word
            word_stats = get_word_stats(conn, cursor, wordid)
            frequency = word_stats["review_count"] if word_stats else 1
        else:
            frequency = 1
        prompt = get_prompt(text, frequency)
        try:
            response = requests.post(self.ollama_url, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            })
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                return f"Error: {response.status_code} - {response.text}"
        except:
            return "Could not connect to Ollama"
    def monitor_test(self):
        print("Monitoring clipboard for Chinese text...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            try:
                current = pyperclip.paste()
                #skip first run
                if not self.last_text:
                    self.last_text = current
                    continue
                if current and current != self.last_text:
                    self.last_text = current
                    # Check if contains Chinese characters
                    if any('\u4e00' <= char <= '\u9fff' for char in current):
                        print(f"\n{'='*50}")
                        print(f"Detected: {current}")
                        print(f"{'='*50}")
            except:
                pass
            time.sleep(1)

    def monitor(self):
        print("Monitoring clipboard for Chinese text...")
        print("Press Ctrl+C to stop\n")
        panel=ControlPanel()
        # Start polling driven by the GUI event loop (no blocking sleeps)
        def poll():
            try:
                current = pyperclip.paste()
            except Exception:
                current = None

            # If Exit was pressed, destroy the panel and stop polling
            if getattr(panel, "done", False):
                print("Exiting...")
                try:
                    panel.root.destroy()
                except Exception:
                    pass
                return

            # If paused, update last_text to avoid catching up old contents
            if not getattr(panel, "opened", True):
                self.last_text = current
                panel.root.after(1000, poll)
                return

            # Skip the very first observed value: initialize last_text on first run
            if self.last_text == "":
                self.last_text = current
                panel.root.after(1000, poll)
                return

            # Only handle new clipboard contents
            if current and current != self.last_text:
                # update last_text early to avoid duplicate processing while popups run
                self.last_text = current
                if any('\u4e00' <= ch <= '\u9fff' for ch in (current or "")):
                    print(f"\n{'='*50}")
                    print(f"Detected: {current}")
                    print(f"{'='*50}")

                    explanation = self.get_explanation(current)
                    print(f"\nExplanation:\n{explanation}\n")

                    Response_popup = Long_message_popup("Explanation", explanation)
                    Response_popup.add_button("Save word", lambda: add_word(conn, cursor, current, explanation[:100], explanation[:100]))
                    Response_popup.add_button("Close", None)

                    Response_popup.show()

            # schedule next poll
            panel.root.after(1000, poll)

        panel.root.after(0, poll)
        panel.show()

if __name__ == "__main__":
    # Changes execution path 
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Connect to database
    conn = sqlite3.connect("vocab.db")
    cursor = conn.cursor()
    init_db(conn, cursor)
    learner = SimpleChineseLearner()
    learner.monitor()
    # learner.monitor_test()