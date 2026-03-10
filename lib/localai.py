import requests
import json
#qwen2.5:7b
class OllamaClient:
    def __init__(self, model="xiaoxi", host="http://localhost:11434"):
        self.host = host
        self.model = model
        self.url = f"{self.host}/api/generate"

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