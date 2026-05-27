"""
Integrated application combining ControlPanel and Vocabulary Learning App
"""

import os
import threading
import pyperclip
import time
from lib.windows import ControlPanel, App, PopupDataService, PopupSaveManager
from lib.streaming_popup import StreamingPopup
from lib.chain import ChainManager
from lib.reviewer import WordReviewer
from lib.db import VocabDatabase
from lib.learner_prompts import prompt_generator_for_mode
from lib.localai import OllamaClient
from lib.ccedict import load_cedict_entries
from lib.async_utils import run_async
from mock_database_generator import MockDatabaseGenerator

MAX_CLIPBOARD_TEXT_LEN = 180

# Load CEDICT entries
_, word_index, char_index, char_def_index = load_cedict_entries("cedict_ts.u8")


class IntegratedApp:
    def __init__(self, db_path="vocab.db", use_mock=False):
        if use_mock and db_path == "vocab.db":
            db_path = "mock_vocab.db"

        self.db_path = db_path
        self.use_mock = use_mock
        self.database = None
        self.chain_mgr = None
        self.db_cls = MockDatabaseGenerator if use_mock else VocabDatabase
        self.reviewer = WordReviewer(db_path, db_cls=self.db_cls)
        self.app_window = None
        self.app_thread = None
        self.last_clipboard_text = ""
        self.control_panel = None
        self.ai = OllamaClient()
        self.word_index = word_index
        self.char_def_index = char_def_index
        self.data_service = None
        self.save_manager = None
    
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
            self.app_window = App(reviewer, ai_client=self.ai, db=db, 
                                  control_panel=self.control_panel, context=self.chain_mgr)
            self.app_window.mainloop()
        except Exception as e:
            print(f"Error launching app: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.app_window = None
    
    def _on_word_detected(self, word: str):
        """Called when a Chinese word is detected in clipboard."""
        print(f"\n{'='*50}")
        print(f"📖 Word detected: {word}")
        print(f"{'='*50}")
        
        mode = self.control_panel.response_mode if self.control_panel else "Sparkle Notes"
        print(f"   Mode: {mode}")
        
        show_image = (mode.lower() != "lookup only")
        
        StreamingPopup(
            word=word,
            master=self.control_panel.root if self.control_panel else None,
            chain_mgr=self.chain_mgr,
            ai_client=self.ai,
            mode=mode,
            display_image=show_image,
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service,
            on_save_callback=self._on_word_saved,
            show_thinking=self.control_panel.show_thinking if self.control_panel else True
        )
    
    def _on_word_saved(self, word: str, word_id: str):
        """Called when a word is saved to vocabulary."""
        print(f"✓ Word '{word}' saved with ID: {word_id}")
        if self.control_panel and self.data_service:
            session_id = self.data_service.get_active_session_id()
            if session_id:
                self.database.add_word_to_session(session_id, word_id)
    
    def _poll_clipboard(self):
        """Poll clipboard for Chinese text."""
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
                self._on_word_detected(current)
        
        self.control_panel.root.after(1000, self._poll_clipboard)
    
    def run(self):
        try:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            
            # Start pre-loading AI in background
            def preload_ai():
                self.ai.manage_model("load")
            threading.Thread(target=preload_ai, daemon=True).start()
            
            # Initialize database
            if self.database is None:
                self.database = self.db_cls(self.db_path)
            
            # Create data service
            self.data_service = PopupDataService(self.database)
            
            # Create chain manager
            active_session_id = self.data_service.get_active_session_id()
            self.chain_mgr = ChainManager(self.database, session_id=active_session_id)
            
            # Create control panel
            self.control_panel = ControlPanel(
                app_callback=self.launch_vocab_app,
                ai_client=self.ai,
                db=self.database,
                data_service=self.data_service,
                context=self.chain_mgr
            )
            
            # Create save manager
            self.save_manager = PopupSaveManager(self.data_service, 
                                                  parent_widget=self.control_panel.root, 
                                                  context=self.chain_mgr)
            
            print("=" * 50)
            print("Integrated Vocabulary Learning System")
            print("=" * 50)
            print("Control Panel started")
            print("Click 'Start' to begin clipboard monitoring")
            print("Click 'Open Main App' to launch the vocabulary reviewer")
            print("=" * 50)
            
            # Update AI status
            self.control_panel.update_ai_status("Ready", "green")
            
            # Start clipboard polling
            self.control_panel.root.after(0, self._poll_clipboard)
            
            # Show control panel
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