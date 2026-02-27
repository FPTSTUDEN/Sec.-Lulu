import requests
import json

class OllamaClient:
    def __init__(self, model="qwen2.5:7b", host="http://localhost:11434"):
        self.host = host
        self.model = model
        self.url = f"{self.host}/api/generate"

    def generate_response(self, prompt, stream=False):
        """Sends a prompt to the local Ollama instance and returns the text response."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }
        
        try:
            response = requests.post(self.url, json=payload)
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                return f"Error: {response.status_code} - {response.text}"
        except requests.exceptions.ConnectionError:
            return "Could not connect to Ollama. Ensure the server is running on localhost:11434."

    def get_word_explanation(self, text, frequency, prompt_generator_func):
        """
        Specialized method for vocabulary learning.
        Uses a prompt generator function to format the request.
        """
        # prompt_generator_func refers to logic like get_prompt(text, frequency)
        prompt = prompt_generator_func(text, frequency)
        return self.generate_response(prompt)