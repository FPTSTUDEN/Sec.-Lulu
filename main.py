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
from lib.windows import ControlPanel, App, Long_message_popup, PopupDataService, PopupSaveManager, LearningContext, AsyncWorker
from lib.reviewer import WordReviewer
from lib.db import VocabDatabase
from lib.learner_prompts import get_prompt, prompt_generator_for_mode
from lib.localai import OllamaClient
from lib.ccedict import load_cedict_entries, lookup_cedict
from mock_database_generator import MockDatabaseGenerator

MAX_CLIPBOARD_TEXT_LEN = 180

# Load CEDICT entries and build indices at startup
_, word_index, char_index, char_def_index = load_cedict_entries("cedict_ts.u8")

class IntegratedApp:
    """Main application that coordinates ControlPanel and VocabApp"""
    
    def __init__(self, db_path="vocab.db", use_mock=False):
        if use_mock and db_path == "vocab.db":
            db_path = "mock_vocab.db"

        self.db_path = db_path
        self.use_mock = use_mock
        self.database = None
        self.context = None
        self.db_cls = MockDatabaseGenerator if use_mock else VocabDatabase
        self.reviewer = WordReviewer(db_path, db_cls=self.db_cls)
        self.app_window = None
        self.app_thread = None
        self.last_clipboard_text = ""
        self.control_panel = None
        self.ai = OllamaClient()
        self.word_index = word_index
        self.char_index = char_index
        self.char_def_index = char_def_index
        self.data_service = None
        self.save_manager = None
        self.async_worker = None  # Will be initialized after control panel
    
    def launch_vocab_app(self):
        if self.app_thread and self.app_thread.is_alive():
            print("App is already running")
            if self.app_window:
                self.app_window.lift()
            return
        
        self.app_thread = threading.Thread(target=self._run_vocab_app, daemon=False)
        self.app_thread.start()
    
    def _run_vocab_app(self):
        try:
            reviewer = WordReviewer(self.db_path, db_cls=self.db_cls)
            db = self.db_cls(self.db_path)
            self.app_window = App(reviewer, ai_client=self.ai, db=db, control_panel=self.control_panel, context=self.context)
            self.app_window.mainloop()
        except Exception as e:
            print(f"Error launching app: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.app_window = None
    
    def get_explanation_generator(self, text):
        """Returns a generator for streaming AI response."""
        db = self.db_cls(self.db_path)
        
        try:
            wordid = db.get_word_id(text)
            if wordid:
                db.update_review(wordid, 3)
                word_stats = db.get_word_stats(wordid)
                frequency = word_stats.get("review_count", 1) if word_stats else 1
            else:
                frequency = 1
            
            if self.control_panel:
                mode = self.control_panel.response_mode
            else:
                mode = "Sparkle Notes"

            if mode == "Lookup Only":
                # Return a generator directly (not a function)
                word_match, char_matches = lookup_cedict(text, self.word_index, self.char_def_index)
                if word_match:
                    result = f"{word_match['simplified']} ({word_match['traditional']}), Definitions: {'; '.join(word_match['definitions'])}"
                elif char_matches:
                    char_info = []
                    for char, entry in char_matches:
                        char_info.append(f"{char}: {entry['simplified']} ({entry['traditional']}), Definitions: {'; '.join(entry['definitions'])}")
                    result = f"No direct match for '{text}'. Character breakdown:\n" + "\n".join(char_info)
                else:
                    result = f"No direct match found for '{text}'."
                
                # Return generator directly
                def single_chunk_generator():
                    yield result
                return single_chunk_generator()

            print(f"Generating {mode} explanation for '{text}'...")
            base_prompt_fn = prompt_generator_for_mode(mode)
            session_ctx = getattr(self.control_panel, 'session_context', '') if self.control_panel else ''
            
            def prompt_fn_with_session(t, f):
                p = base_prompt_fn(t, f)
                if session_ctx:
                    return f"Session context: {session_ctx}\n\n{p}"
                return p

            display_thinking = getattr(self.control_panel, 'show_thinking', True)
            
            # Return the generator directly (not wrapped in lambda)
            return lambda: self.ai.generate_response(
                prompt_fn_with_session(text, frequency), 
                display_thinking
            )
        finally:
            db.close()
                
    def _generate_for_word(self, text, mode=None, context=None):
        original_mode = None
        if mode and self.control_panel:
            original_mode = self.control_panel.response_mode
            self.control_panel.response_mode = mode
        
        try:
            generator_func = self.get_explanation_generator(text)
            if context:
                self.context = context
            self._show_explanation_popup(text, generator_func)
        finally:
            if original_mode and self.control_panel:
                self.control_panel.response_mode = original_mode
    
    def _show_explanation_popup(self, text, generator_func):
        if not self.context:
            self.context = LearningContext(self.database)
        
        response_popup = Long_message_popup(
            "Explanation",
            text,
            master=self.control_panel,
            display_image=(self.control_panel.response_mode.lower() != "lookup only"),
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service,
            context=self.context,
            generate_explanation_callback=self._generate_for_word
        )
        
        # generator_func is already a generator, call it to get the generator
        # But wait - get_explanation_generator returns a FUNCTION that returns a generator
        # Let's check what we actually have...
        if callable(generator_func):
            # It's a function that returns a generator
            generator = generator_func()
        else:
            # It's already a generator
            generator = generator_func
        
        # Start streaming using the generator
        response_popup.start_streaming(generator, text)
        response_popup.show()

    def _poll_clipboard(self):
        if not self.control_panel or getattr(self.control_panel, "done", False):
            return
        
        try:
            current = pyperclip.paste()
        except Exception as e:
            print(f"Clipboard error: {e}")
            current = None
        
        if not getattr(self.control_panel, "opened", True):
            self.last_clipboard_text = current or ""
            if current:
                if len(current) > MAX_CLIPBOARD_TEXT_LEN:
                    self.control_panel.update_clipboard_display(current, False, too_long=True)
                else:
                    is_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in current)
                    self.control_panel.update_clipboard_display(current, is_chinese)
            self.control_panel.root.after(1000, self._poll_clipboard)
            return
        
        if self.last_clipboard_text == "":
            self.last_clipboard_text = current or ""
            if current:
                if len(current) > MAX_CLIPBOARD_TEXT_LEN:
                    self.control_panel.update_clipboard_display(current, False, too_long=True)
                else:
                    is_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in current)
                    self.control_panel.update_clipboard_display(current, is_chinese)
            self.control_panel.root.after(1000, self._poll_clipboard)
            return
        
        if current and len(current) > MAX_CLIPBOARD_TEXT_LEN:
            self.last_clipboard_text = current
            self.control_panel.update_clipboard_display(current, False, too_long=True)
            self.control_panel.root.after(1000, self._poll_clipboard)
            return

        if current and current != self.last_clipboard_text:
            self.last_clipboard_text = current
            is_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in current)
            self.control_panel.update_clipboard_display(current, is_chinese)
            
            if is_chinese:
                print(f"\n{'='*50}")
                print(f"Detected: {current}")
                print(f"{'='*50}")
                self._generate_for_word(current)
        
        self.control_panel.root.after(1000, self._poll_clipboard)
    
    def run(self):
        try:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            threading.Thread(target=lambda: self.ai.manage_model("load"), daemon=True).start()
            
            if self.database is None:
                self.database = self.db_cls(self.db_path)
            
            self.data_service = PopupDataService(self.database)
            
            self.context = LearningContext(self.database)
            self.context.active_session_id = self.data_service.get_active_session_id()
            
            self.control_panel = ControlPanel(
                app_callback=self.launch_vocab_app,
                ai_client=self.ai,
                db=self.database,
                data_service=self.data_service,
                context=self.context
            )
            
            self.async_worker = AsyncWorker(self.control_panel.root)
            
            self.save_manager = PopupSaveManager(self.data_service, parent_widget=self.control_panel.root, context=self.context)
            
            self.control_panel.generate_callback = self._generate_for_word
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
            
            threading.Thread(target=initial_load, daemon=True).start()
            self.control_panel.root.after(0, self._poll_clipboard)
            
            self.control_panel.show()
            
            if self.app_thread and self.app_thread.is_alive():
                print("Waiting for app to close...")
                self.app_thread.join(timeout=5)
            
            print("Application closed")
        
        except Exception as e:
            print(f"Error in integrated app: {e}")
            import traceback
            traceback.print_exc()


def main():
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