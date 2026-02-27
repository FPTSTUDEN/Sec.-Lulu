"""
Integrated application combining ControlPanel and Vocabulary Learning App
Properly handles multiple Tkinter event loops without blocking
"""

import os
import threading
import pyperclip
import requests
import time
from lib.windows import ControlPanel, App, Long_message_popup
from lib.reviewer import WordReviewer
from lib.db import VocabDatabase
from lib.learner_prompts import get_prompt


class IntegratedApp:
    """Main application that coordinates ControlPanel and VocabApp"""
    
    def __init__(self, db_path="vocab.db"):
        self.db_path = db_path
        self.database = None  # Will be created in the polling thread
        self.reviewer = WordReviewer(db_path)
        self.app_window = None
        self.app_thread = None
        self.last_clipboard_text = ""
        self.control_panel = None
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen2.5:7b"
    
    def launch_vocab_app(self):
        """Launch the vocabulary learning app in a separate thread"""
        if self.app_thread and self.app_thread.is_alive():
            print("App is already running")
            if self.app_window:
                self.app_window.lift()  # Bring window to front
            return
        
        # Create app in a new thread to avoid blocking ControlPanel
        self.app_thread = threading.Thread(target=self._run_vocab_app, daemon=False)
        self.app_thread.start()
    
    def _run_vocab_app(self):
        """Run the vocabulary app in a separate thread"""
        try:
            # Create a fresh WordReviewer in this thread to avoid SQLite thread-safety issues
            # SQLite connections cannot be shared across threads
            reviewer = WordReviewer(self.db_path)
            self.app_window = App(reviewer)
            self.app_window.mainloop()
        except Exception as e:
            print(f"Error launching app: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.app_window = None
    
    def get_explanation(self, text):
        """Get explanation from Ollama for detected Chinese text"""
        # Create a fresh database connection for this thread
        db = VocabDatabase(self.db_path)
        
        try:
            wordid = db.get_word_id(text)
            if wordid:
                db.update_review(wordid, 3)
                word_stats = db.get_word_stats(wordid)
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
        finally:
            db.close()
    
    def _show_explanation_popup(self, text, explanation):
        """Show explanation in separate thread to avoid blocking main loop"""
        def show_popup():
            response_popup = Long_message_popup("Explanation", explanation)
            
            def save_word():
                # Create a fresh database connection for this thread
                db = VocabDatabase(self.db_path)
                try:
                    db.add_word(text, explanation[:100], explanation[:100])
                    print(f"Saved: {text}")
                finally:
                    db.close()
                response_popup.long_popup.destroy()
            
            def close_popup():
                response_popup.long_popup.destroy()
            
            response_popup.add_button("Save word", save_word)
            response_popup.add_button("Close", close_popup)
            response_popup.show()
        
        thread = threading.Thread(target=show_popup, daemon=True)
        thread.start()
    
    def _poll_clipboard(self):
        """Poll clipboard for Chinese text - called via control_panel.root.after()"""
        if not self.control_panel or getattr(self.control_panel, "done", False):
            return
        
        try:
            current = pyperclip.paste()
        except Exception as e:
            print(f"Clipboard error: {e}")
            current = None
        
        # If monitoring is paused
        if not getattr(self.control_panel, "opened", True):
            self.last_clipboard_text = current or ""
            self.control_panel.root.after(1000, self._poll_clipboard)
            return
        
        # Initialize last_clipboard_text
        if self.last_clipboard_text == "":
            self.last_clipboard_text = current or ""
            self.control_panel.root.after(1000, self._poll_clipboard)
            return
        
        # Check for new Chinese text
        if current and current != self.last_clipboard_text:
            self.last_clipboard_text = current
            if any('\u4e00' <= ch <= '\u9fff' for ch in (current or "")):
                print(f"\n{'='*50}")
                print(f"Detected: {current}")
                print(f"{'='*50}")
                
                explanation = self.get_explanation(current)
                print(f"\nExplanation:\n{explanation}\n")
                
                # Show popup in separate thread
                self._show_explanation_popup(current, explanation)
        
        # Schedule next poll
        self.control_panel.root.after(1000, self._poll_clipboard)
    
    def run(self):
        """Start the integrated application"""
        try:
            # Change to script directory for database access
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            
            # Create control panel with callback to launch app
            self.control_panel = ControlPanel(app_callback=self.launch_vocab_app)
            
            print("=" * 50)
            print("Integrated Vocabulary Learning System")
            print("=" * 50)
            print("Control Panel started")
            print("Click 'Start' to begin clipboard monitoring")
            print("Click 'Open Main App' to launch the vocabulary reviewer")
            print("=" * 50)
            
            # Start clipboard polling integrated with ControlPanel's event loop
            self.control_panel.root.after(0, self._poll_clipboard)
            
            # Show control panel (blocks until closed)
            self.control_panel.show()
            
            # Cleanup
            if self.app_thread and self.app_thread.is_alive():
                print("Waiting for app to close...")
                self.app_thread.join(timeout=5)
            
            print("Application closed")
        
        except Exception as e:
            print(f"Error in integrated app: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Entry point"""
    app = IntegratedApp()
    app.run()


if __name__ == "__main__":
    main()
