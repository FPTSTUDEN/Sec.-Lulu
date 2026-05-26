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
from lib.windows import ControlPanel, App, Long_message_popup, PopupDataService, PopupSaveManager
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
        # Store CEDICT indices for use in get_explanation
        self.word_index = word_index
        self.char_index = char_index
        self.char_def_index = char_def_index
        # Services for popup operations (will be initialized in run())
        self.data_service = None
        self.save_manager = None
    
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
            self.app_window = App(reviewer, ai_client=self.ai, db=db, control_panel=self.control_panel)
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
            
            if self.control_panel:
                mode = self.control_panel.response_mode
            else:
                mode = "Sparkle Notes"

            if mode == "Lookup Only":
                print(f"Generating explanation for '{text}' in lookup-only mode...")
                word_match, char_matches = lookup_cedict(text, self.word_index, self.char_def_index)
                if word_match:
                    return f"{word_match['simplified']} ({word_match['traditional']}), Definitions: {'; '.join(word_match['definitions'])}"
                elif char_matches:
                    char_info = []
                    for char, entry in char_matches:
                        char_info.append(f"{char}: {entry['simplified']} ({entry['traditional']}), Definitions: {'; '.join(entry['definitions'])}")
                    return f"No direct match for '{text}'. Character breakdown:\n" + "\n".join(char_info)
                return f"No direct match found for '{text}'."

            print(f"Generating {mode} explanation for '{text}'...")
            base_prompt_fn = prompt_generator_for_mode(mode)
            # Include session context from the control panel if present
            session_ctx = getattr(self.control_panel, 'session_context', '') if self.control_panel else ''
            def prompt_fn_with_session(t, f):
                p = base_prompt_fn(t, f)
                if session_ctx:
                    return f"Session context: {session_ctx}\n\n{p}"
                return p

            display_thinking = getattr(self.control_panel, 'show_thinking', True)
            return self.ai.get_word_explanation(text, frequency, prompt_fn_with_session, display_thinking)
        finally:
            db.close()
    
    def _show_explanation_popup(self, text, explanation_generator, parent_node_id=None):
        """Handles the streaming update of the popup UI."""
        
        # Create the popup with data service for DB operations
        # Use passed parent_node_id, fallback to control panel tracking
        effective_parent_id = parent_node_id or getattr(self.control_panel, 'current_response_node_id', None)
        
        response_popup = Long_message_popup(
            "Explanation",
            text,
            master=self.control_panel,
            display_image=(self.control_panel.response_mode.lower() != "lookup only"),
            word_index=self.word_index,
            char_def_index=self.char_def_index,
            data_service=self.data_service,
            session_id=self.data_service.get_active_session_id() if self.data_service else None,
            parent_node_id=effective_parent_id,
            generate_explanation_callback=self._generate_for_word
        )
        # ... rest stays the same
        
        def stream_thread():
            full_explanation = ""
            try:
                for chunk in explanation_generator:
                    # Route thinking-marked chunks to the think box
                    if isinstance(chunk, str) and chunk.startswith("__THINK__"):
                        thinking = chunk[len("__THINK__"):]
                        full_explanation += thinking
                        self.control_panel.root.after(0, lambda t=thinking: response_popup.append_think(t))
                    else:
                        full_explanation += chunk
                        # Update the UI on the main thread
                        self.control_panel.root.after(0, lambda c=chunk: response_popup.append_text(c))

                # Once finished, enable the save button with PopupSaveManager
                self.control_panel.root.after(0, lambda: self._setup_save_button(response_popup, text, full_explanation))
            except Exception as e:
                print(f"Streaming error: {e}")

        threading.Thread(target=stream_thread, daemon=True).start()
        response_popup.show()

    def _setup_save_button(self, popup, word, explanation_text):
        """Setup save button using PopupSaveManager"""
        def save_logic():
            if self.save_manager:
                word_id = self.save_manager.save_word_with_prompt(
                    word, 
                    explanation_text,
                    parent_node_id=popup.current_node_id
                )
                if word_id:
                    print(f"✓ Word '{word}' saved successfully!")
            popup.long_popup.destroy()
            
        popup.add_button("💾 Save/Update word", save_logic)
    
    def _generate_for_word(self, text, mode=None, parent_node_id=None):
        """Generate explanation for a word and display in popup.
        
        Args:
            text: The word to explain
            mode: (optional) Response mode. If provided, temporarily override control_panel mode.
            parent_node_id: (optional) Parent content node ID for chain tracking
        """
        # Temporarily set control panel response mode if specified (for chained responses)
        original_mode = None
        if mode and self.control_panel:
            original_mode = self.control_panel.response_mode
            self.control_panel.response_mode = mode
        
        try:
            explanation = self.get_explanation(text)
            # Wrap string explanation in a generator if needed
            if isinstance(explanation, str):
                explanation = (explanation,)
            self._show_explanation_popup(text, explanation, parent_node_id=parent_node_id)
        finally:
            # Restore original mode if we changed it
            if original_mode and self.control_panel:
                self.control_panel.response_mode = original_mode
    
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
            # Update display even when paused
            if current:
                if len(current) > MAX_CLIPBOARD_TEXT_LEN:
                    self.control_panel.update_clipboard_display(current, False, too_long=True)
                else:
                    is_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in current)
                    self.control_panel.update_clipboard_display(current, is_chinese)
            self.control_panel.root.after(1000, self._poll_clipboard)
            return
        
        # Initialize last_clipboard_text
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
        
        # Ignore too-long clipboard contents to avoid registering oversized data
        if current and len(current) > MAX_CLIPBOARD_TEXT_LEN:
            self.last_clipboard_text = current
            self.control_panel.update_clipboard_display(current, False, too_long=True)
            self.control_panel.root.after(1000, self._poll_clipboard)
            return

        # Check for new text
        if current and current != self.last_clipboard_text:
            self.last_clipboard_text = current
            is_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in current)
            self.control_panel.update_clipboard_display(current, is_chinese)
            
            if is_chinese:
                print(f"\n{'='*50}")
                print(f"Detected: {current}")
                print(f"{'='*50}")
                self._generate_for_word(current)
        
        # Schedule next poll
        self.control_panel.root.after(1000, self._poll_clipboard)
    
    def run(self):
        """Start the integrated application"""
        try:
            # Change to script directory for database access
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            # Start pre-loading in the background on startup
            threading.Thread(target=lambda: self.ai.manage_model("load"), daemon=True).start()
            
            # Initialize database and services
            if self.database is None:
                self.database = self.db_cls(self.db_path)
            
            # Create data service for popup DB operations
            self.data_service = PopupDataService(self.database)
            
            # Create the control panel (which will use data_service internally)
            self.control_panel = ControlPanel(
                app_callback=self.launch_vocab_app,
                ai_client=self.ai,
                db=self.database,
                data_service=self.data_service
            )
            
            # Create save manager for word save workflow (prompts user for translation)
            self.save_manager = PopupSaveManager(self.data_service, parent_widget=self.control_panel.root)
            
            # Set the callback for generating explanations when clipboard is clicked
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
