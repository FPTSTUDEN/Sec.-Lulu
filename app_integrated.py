"""
Integrated application combining ControlPanel and Vocabulary Learning App
Properly handles multiple Tkinter event loops without blocking
"""

import os
import threading
from lib.windows import ControlPanel, App
from lib.reviewer import WordReviewer
from lib.database import Database


class IntegratedApp:
    """Main application that coordinates ControlPanel and VocabApp"""
    
    def __init__(self, db_path="vocab.db"):
        self.db_path = db_path
        self.database = Database(db_path)
        self.reviewer = WordReviewer(db_path)
        self.app_window = None
        self.app_thread = None
    
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
    
    def run(self):
        """Start the integrated application"""
        try:
            # Change to script directory for database access
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            
            # Create control panel with callback to launch app
            control_panel = ControlPanel(app_callback=self.launch_vocab_app)
            
            print("=" * 50)
            print("Integrated Vocabulary Learning System")
            print("=" * 50)
            print("Control Panel started")
            print("Click 'Open Main App' to launch the vocabulary reviewer")
            print("=" * 50)
            
            # Show control panel (blocks until closed)
            control_panel.show()
            
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
