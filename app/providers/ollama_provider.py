
import requests

class OllamaProvider:
    def __init__(self, model: str):
        self.model = model
        self.base = "http://localhost:11434/api/chat"

    def infer(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "format": "json"
        }
        r = requests.post(self.base, json=payload, timeout=180)
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]
