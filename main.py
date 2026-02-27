import pyperclip
from lib.windows import *
from lib.db import VocabDatabase
from lib.learner_prompts import *
import requests
import time
import os
import threading

class SimpleChineseLearner:
    def __init__(self, db):
        self.last_text = ""
        self.db = db
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen2.5:7b"
    
    def get_explanation(self, text):
        wordid = self.db.get_word_id(text)
        print(wordid)
        if wordid:
            self.db.update_review(wordid, 3)  # Assume user is having trouble
            word_stats = self.db.get_word_stats(wordid)
            frequency = word_stats.get("review_count", 1) if word_stats else 1
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
                if not self.last_text:
                    self.last_text = current
                    continue
                if current and current != self.last_text:
                    self.last_text = current
                    if any('\u4e00' <= char <= '\u9fff' for char in current):
                        print(f"\n{'='*50}")
                        print(f"Detected: {current}")
                        print(f"{'='*50}")
            except:
                pass
            time.sleep(1)

    def _show_explanation_popup(self, text, explanation):
        """Show explanation in separate thread to avoid blocking main loop"""
        def show_popup():
            response_popup = Long_message_popup("Explanation", explanation)
            
            def save_word():
                self.db.add_word(text, explanation[:100], explanation[:100])
                print(f"Saved: {text}")
                response_popup.long_popup.destroy()
            
            def close_popup():
                response_popup.long_popup.destroy()
            
            response_popup.add_button("Save word", save_word)
            response_popup.add_button("Close", close_popup)
            response_popup.show()
        
        thread = threading.Thread(target=show_popup, daemon=True)
        thread.start()

    def monitor(self):
        print("Monitoring clipboard for Chinese text...")
        print("Press Ctrl+C to stop\n")
        panel = ControlPanel()
        
        def poll():
            try:
                current = pyperclip.paste()
            except Exception as e:
                print(e)
                current = None

            if getattr(panel, "done", False):
                print("Exiting...")
                try:
                    panel.root.destroy()
                except Exception:
                    pass
                return

            if not getattr(panel, "opened", True):
                self.last_text = current
                panel.root.after(1000, poll)
                return

            if self.last_text == "":
                self.last_text = current
                panel.root.after(1000, poll)
                return

            if current and current != self.last_text:
                self.last_text = current
                if any('\u4e00' <= ch <= '\u9fff' for ch in (current or "")):
                    print(f"\n{'='*50}")
                    print(f"Detected: {current}")
                    print(f"{'='*50}")

                    explanation = self.get_explanation(current)
                    print(f"\nExplanation:\n{explanation}\n")
                    
                    # Show popup in separate thread
                    self._show_explanation_popup(current, explanation)

            panel.root.after(1000, poll)

        panel.root.after(0, poll)
        panel.show()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    db = VocabDatabase("vocab.db")
    learner = SimpleChineseLearner(db)
    learner.monitor()