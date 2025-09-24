
import os, requests

class OpenAIProvider:
    def __init__(self, model: str):
        self.model = model
        self.base = "https://api.openai.com/v1/chat/completions"
        self.key = os.environ.get("OPENAI_API_KEY","")
        if not self.key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

    def infer(self, system: str, user: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        }
        r = requests.post(self.base, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
