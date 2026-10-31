import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

class BudgetExceededError(RuntimeError):
    """Raised when LLM invocation exceeds the configured budget limit in USD."""
    def __init__(self, current_cost: float, max_budget: float):
        self.current_cost = current_cost
        self.max_budget = max_budget
        super().__init__(
            f"LLM budget limit exceeded: total cost ${current_cost:.5f} "
            f"has reached or exceeded the configured budget cap of ${max_budget:.5f}."
        )

class LLMClient:
    """
    Lightweight, dependency-free unified LLM client with:
    - OpenAI / OpenAI-compatible (GPT-4o, etc.)
    - Anthropic Claude 3.5 Sonnet
    - Google Gemini
    - Mock mode (for offline E2E unit testing)
    - Token tracking and USD cost estimation
    - Hard budget limit enforcement
    """

    MODEL_PRICING: Dict[str, Dict[str, float]] = {
        # Rates per 1,000,000 tokens (USD)
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "default": {"input": 2.50, "output": 10.00},
    }

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        max_budget_usd: Optional[float] = None
    ):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.getenv("AUTOHEAL_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")
        
        # Token and cost guardrails
        env_budget = os.getenv("AUTOHEAL_MAX_BUDGET_USD")
        self.max_budget_usd: Optional[float] = (
            max_budget_usd if max_budget_usd is not None
            else (float(env_budget) if env_budget else None)
        )
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Rough estimation of token count (~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: Optional[str] = None
    ) -> float:
        """Calculates estimated USD cost for given prompt and completion tokens."""
        target_model = (model or self.model).lower()
        rates = self.MODEL_PRICING.get(target_model, self.MODEL_PRICING["default"])
        input_cost = (prompt_tokens / 1_000_000.0) * rates["input"]
        output_cost = (completion_tokens / 1_000_000.0) * rates["output"]
        return input_cost + output_cost

    def track_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: Optional[str] = None
    ) -> float:
        """Increments token counters and accumulated USD cost."""
        cost = self.calculate_cost(prompt_tokens, completion_tokens, model)
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost_usd += cost
        return cost

    def check_budget(self) -> None:
        """Raises BudgetExceededError if accumulated cost exceeds max_budget_usd."""
        if self.max_budget_usd is not None and self.total_cost_usd >= self.max_budget_usd:
            raise BudgetExceededError(self.total_cost_usd, self.max_budget_usd)

    def get_usage(self) -> Dict[str, Any]:
        """Returns a snapshot of current token consumption and cost."""
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "max_budget_usd": self.max_budget_usd,
        }

    def reset_usage(self) -> None:
        """Resets token consumption and cost counters to zero."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Invokes the selected LLM provider and returns the raw string response."""
        self.check_budget()

        if not self.api_key:
            resp = self._mock_fallback(system_prompt, user_prompt)
        elif self.provider == "anthropic":
            resp = self._call_anthropic(system_prompt, user_prompt, temperature)
        elif self.provider == "gemini":
            resp = self._call_gemini(system_prompt, user_prompt, temperature)
        else:
            resp = self._call_openai(system_prompt, user_prompt, temperature)

        self.check_budget()
        return resp

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
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            p_tokens = usage.get("prompt_tokens", self.estimate_tokens(system + user))
            c_tokens = usage.get("completion_tokens", self.estimate_tokens(content))
            self.track_usage(p_tokens, c_tokens)
            return content

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
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            p_tokens = usage.get("input_tokens", self.estimate_tokens(system + user))
            c_tokens = usage.get("output_tokens", self.estimate_tokens(content))
            self.track_usage(p_tokens, c_tokens)
            return content

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
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            p_tokens = usage.get("promptTokenCount", self.estimate_tokens(system + user))
            c_tokens = usage.get("candidatesTokenCount", self.estimate_tokens(content))
            self.track_usage(p_tokens, c_tokens)
            return content

    def _mock_fallback(self, system: str, user: str) -> str:
        """Deterministic mock responses for test environments without real LLM credentials."""
        mock_resp = "MOCK_RESPONSE: No API key provided."
        p_tokens = self.estimate_tokens(system + user)
        c_tokens = self.estimate_tokens(mock_resp)
        self.track_usage(p_tokens, c_tokens)
        return mock_resp
