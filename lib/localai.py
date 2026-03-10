import requests
import json
#qwen2.5:7b
class OllamaClient:
    def __init__(self, model="xiaoxi", host="http://localhost:11434"):
        self.host = host
        self.model = model
        self.url = f"{self.host}/api/generate"
    def manage_model(self, action="load"):
        """
        Loads or unloads the model from VRAM.
        action="load": keep_alive=-1 (stays forever)
        action="unload": keep_alive=0 (leaves immediately)
        """
        # Setting keep_alive to 0 with an empty prompt unloads the model
        keep_alive = -1 if action == "load" else 0
        payload = {
            "model": self.model,
            "prompt": "", 
            "keep_alive": keep_alive
        }
        try:
            print(f"Action '{action}' sent to Ollama for model '{self.model}'...")
            response=requests.post(self.url, json=payload, timeout=60)
            return response.status_code == 200
        except Exception as e:
            print(f"Model management failed: {e}")
            return False
    def generate_response(self, prompt):
        """Yields text chunks from Ollama in real-time."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True  # Force streaming
        }
        
        try:
            # Use stream=True in the requests call
            response = requests.post(self.url, json=payload, stream=True)
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    token = chunk.get('response', '')
                    yield token  # Yield each piece of text
                    if chunk.get('done', False):
                        break
        except Exception as e:
            yield f"\n[Error: {e}]"

    def get_word_explanation(self, text, frequency, prompt_generator_func):
        """Now returns a generator instead of a static string."""
        prompt = prompt_generator_func(text, frequency)
        return self.generate_response(prompt)