import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

class LLMClient:
    """
    Lightweight, dependency-free unified LLM client supporting:
    - OpenAI / OpenAI-compatible (GPT-4o, etc.)
    - Anthropic Claude 3.5 Sonnet
    - Google Gemini
    - Mock mode (for offline E2E unit testing)
    """

    def __init__(self, provider: str = "openai", model: str = "gpt-4o", api_key: Optional[str] = None):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.getenv("AUTOHEAL_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Invokes the selected LLM provider and returns the raw string response."""
        if not self.api_key:
            return self._mock_fallback(system_prompt, user_prompt)

        if self.provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt, temperature)
        elif self.provider == "gemini":
            return self._call_gemini(system_prompt, user_prompt, temperature)
        else:
            return self._call_openai(system_prompt, user_prompt, temperature)

    def _call_openai(self, system: str, user: str, temp: float) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "temperature": temp,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _call_anthropic(self, system: str, user: str, temp: float) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": self.model or "claude-3-5-sonnet-20241022",
            "system": system,
            "temperature": temp,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": user}]
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]

    def _call_gemini(self, system: str, user: str, temp: float) -> str:
        model_name = self.model or "gemini-1.5-pro"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"temperature": temp}
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _mock_fallback(self, system: str, user: str) -> str:
        """Deterministic mock responses for test environments without real LLM credentials."""
        return "MOCK_RESPONSE: No API key provided."
