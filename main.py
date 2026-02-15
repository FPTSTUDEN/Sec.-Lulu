# simple_clipboard_monitor.py
import pyperclip
from lib.windows import popup_message, popup_long_message
import requests
import time
from datetime import datetime

# popup_message("Clipboard Monitor", "This program will monitor your clipboard for Chinese text and provide explanations. Press Ctrl+C to stop.")
class SimpleChineseLearner:
    def __init__(self):
        self.last_text = ""
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen2.5:7b"
    
    def get_explanation(self, text):
        prompt = f"""Please explain this Chinese text in English with detailed breakdown:

Text: "{text}"

Provide:
1. English and Chinese explanation
2. Word-by-word meaning
3. Example sentences
Use simple language and clear formatting.
"""
        
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
                        
                        explanation = self.get_explanation(current)
                        print(f"\nExplanation:\n{explanation}\n")
                        popup_long_message("Chinese Explanation", explanation)
                        
                        self.last_text = current
            except:
                pass
            
            time.sleep(1)

if __name__ == "__main__":
    learner = SimpleChineseLearner()
    learner.monitor()
    # learner.monitor_test()