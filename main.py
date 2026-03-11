"""
Integrated application combining ControlPanel and Vocabulary Learning App
Properly handles multiple Tkinter event loops without blocking
"""

import os
import threading
import pyperclip
import requests
import time
from PIL import Image
from lib.windows import ControlPanel, App, Long_message_popup
from lib.reviewer import WordReviewer
from lib.db import VocabDatabase
from lib.learner_prompts import get_prompt, get_short_prompt
from lib.localai import OllamaClient
from mock_database_generator import MockDatabaseGenerator

def parse_cedict_line(line):
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
def lookup_cedict(word, entries):
    '''Returns the definition for a given word. If the word is not found, returns definitions of individual characters.'''
    for entry in entries:
        if entry["simplified"] == word or entry["traditional"] == word:
            return entry, []
    # If not found, try character-level lookup
    char_matches = []
    for char in word:
        for entry in entries:
            if entry["simplified"] == char or entry["traditional"] == char:
                char_matches.append((char, entry))
                break
    return None, char_matches
    
with open("cedict_ts.u8", encoding="utf-8") as f:
    entries = [parse_cedict_line(l) for l in f if parse_cedict_line(l)]

class IntegratedApp:
    """Main application that coordinates ControlPanel and VocabApp"""
    
    def __init__(self, db_path="vocab.db", use_mock=False):
        # allow a special default when using mock
        if use_mock and db_path == "vocab.db":
            db_path = "mock_vocab.db"

        self.db_path = db_path
        self.use_mock = use_mock
        self.database = None  # Will be created in the polling thread
        # pass the db class through to the reviewer so it uses the same type
        self.db_cls = MockDatabaseGenerator if use_mock else VocabDatabase
        self.reviewer = WordReviewer(db_path, db_cls=self.db_cls)
        self.app_window = None
        self.app_thread = None
        self.last_clipboard_text = ""
        self.control_panel = None
        self.ai = OllamaClient()
    
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
            # Create a fresh WordReviewer and Database connection in this thread to avoid SQLite thread-safety issues
            # SQLite connections cannot be shared across threads
            reviewer = WordReviewer(self.db_path, db_cls=self.db_cls)
            db = self.db_cls(self.db_path)
            self.app_window = App(reviewer, ai_client=self.ai, db=db)
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
        db = self.db_cls(self.db_path)
        
        try:
            wordid = db.get_word_id(text)
            if wordid:
                db.update_review(wordid, 3)
                word_stats = db.get_word_stats(wordid)
                frequency = word_stats.get("review_count", 1) if word_stats else 1
            else:
                frequency = 1
            
            # prompt = get_prompt(text, frequency)
            if self.control_panel and self.control_panel.response_mode == "detailed":
                print(f"Generating detailed explanation for '{text}' (review count: {frequency})...")
                # exit()
                return self.ai.get_word_explanation(text, frequency, get_prompt)
            elif self.control_panel and self.control_panel.response_mode == "simple":
                print(f"Generating concise explanation for '{text}'...")
                # exit()
                return self.ai.get_word_explanation(text, frequency, get_short_prompt)
            else:
                print(f"Generating explanation for '{text}' in lookup-only mode...")
                word_match, char_matches = lookup_cedict(text, entries)
                if word_match:
                    return f"{word_match['simplified']} ({word_match['traditional']}), Definitions: {'; '.join(word_match['definitions'])}"
                elif char_matches:
                    char_info = []
                    for char, entry in char_matches:
                        char_info.append(f"{char}: {entry['simplified']} ({entry['traditional']}), Definitions: {'; '.join(entry['definitions'])}")
                    return f"No direct match for '{text}'. Character breakdown:\n" + "\n".join(char_info)
        finally:
            db.close()
    
    def _show_explanation_popup(self, text, explanation_generator):
        """Handles the streaming update of the popup UI."""
        
        # Create the popup immediately (ensure Long_message_popup is modified to allow updates)
        # We pass empty string initially
        # print(self.control_panel.response_mode)
        response_popup = Long_message_popup("Explanation", "", master=self.control_panel, display_image=(self.control_panel.response_mode != "lookup_only"))
        
        def stream_thread():
            full_explanation = ""
            try:
                for chunk in explanation_generator:
                    full_explanation += chunk
                    # Update the UI on the main thread
                    self.control_panel.root.after(0, lambda c=chunk: response_popup.append_text(c))
                
                # Once finished, enable the save button logic
                self.control_panel.root.after(0, lambda: self._setup_save_button(response_popup, text, full_explanation))
            except Exception as e:
                print(f"Streaming error: {e}")

        threading.Thread(target=stream_thread, daemon=True).start()
        response_popup.show()

    def _setup_save_button(self, popup, text, final_text):
        def save_logic():
            db = self.db_cls(self.db_path)
            # ... (your existing save logic) ...
            db.close()
            popup.long_popup.destroy()
            
        popup.add_button("Save/Update word", save_logic)
    
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
                # print(f"\nExplanation:\n{explanation}\n")
                
                # Show popup in separate thread
                self._show_explanation_popup(current, explanation)
        
        # Schedule next poll
        self.control_panel.root.after(1000, self._poll_clipboard)
    
    def run(self):
        """Start the integrated application"""
        try:
            # Change to script directory for database access
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            # Start pre-loading in the background on startup
            threading.Thread(target=lambda: self.ai.manage_model("load"), daemon=True).start()
            
            # Pass the AI client so the UI can trigger unloads
            self.control_panel = ControlPanel(
                app_callback=self.launch_vocab_app, 
                ai_client=self.ai
            )
            print("=" * 50)
            print("Integrated Vocabulary Learning System")
            print("=" * 50)
            print("Control Panel started")
            print("Click 'Start' to begin clipboard monitoring")
            print("Click 'Open Main App' to launch the vocabulary reviewer")
            print("=" * 50)
            def initial_load():
                self.control_panel.update_ai_status("Loading Model...", "orange")
                if self.ai.manage_model("load"):
                    self.control_panel.update_ai_status("Ready (GPU)", "green")
                else:
                    self.control_panel.update_ai_status("Load Failed", "red")

            # Start the pre-load thread
            threading.Thread(target=initial_load, daemon=True).start()
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
    """Entry point with simple CLI options."""
    import argparse

    parser = argparse.ArgumentParser(description="Integrated vocab app")
    parser.add_argument("--use-mock", action="store_true",
                        help="Use the mock database implementation")
    parser.add_argument("--db-path", default="vocab.db",
                        help="Path to database file (overrides default)")
    args = parser.parse_args()

    app = IntegratedApp(db_path=args.db_path, use_mock=args.use_mock)
    print(f"Using {'mock' if args.use_mock else 'real'} database at {app.db_path}")
    app.run()


if __name__ == "__main__":
    main()
