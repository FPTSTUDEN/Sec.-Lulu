import requests
import json
#qwen2.5:7b
class OllamaClient:
    def __init__(self, model="xiaoxi", host="http://localhost:11434"):
        self.host = host
        self.model = model
        self.url = f"{self.host}/api/generate"
        self.think = False
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
    def generate_response(self, prompt, display_thinking=True):
        """Yields text chunks from Ollama in real-time."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "think": self.think,
            "stream": True  # Force streaming
        }
        
        try:
            # Use stream=True in the requests call
            response = requests.post(self.url, json=payload, stream=True, timeout=120)
            response.raise_for_status()

            in_thinking = False
            buffer = ""
            start_tag = "<think>"
            end_tag = "</think>"
            min_tail = max(len(start_tag), len(end_tag)) - 1

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    print("[localai] JSON decode failed for line:", repr(line))
                    continue

                token = chunk.get("response", "")
                thinking_token = chunk.get("reasoning", "") or chunk.get("thinking", "") or chunk.get("thoughts", "")
                # print("[localai] received chunk: response=", repr(token), "thinking=", repr(thinking_token), "done=", chunk.get("done", False))
                if not token and not thinking_token:
                    if chunk.get("done", False):
                        break
                    continue

                if display_thinking:
                    if thinking_token:
                        # Prefix thinking output so callers can route it separately
                        yield "__THINK__" + thinking_token
                    if token:
                        # print("[localai] yield response:", repr(token))
                        yield token
                else:
                    # When hiding thinking, only yield response, skip thinking
                    if token:
                        # print("[localai] yield response (thinking hidden):", repr(token))
                        yield token
                    # Skip thinking_token entirely
        except Exception as e:
            yield f"\n[Error: {e}]"

    def get_word_explanation(self, text, frequency, prompt_generator_func, display_thinking=True):
        """Now returns a generator instead of a static string."""
        prompt = prompt_generator_func(text, frequency)
        return self.generate_response(prompt, display_thinking)