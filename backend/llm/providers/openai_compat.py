# llm/providers/openai_compat.py
"""Any /chat/completions-compatible endpoint: OpenAI, Azure, vLLM, Ollama, LiteLLM proxy."""
import requests

from llm.base import LLMError

_TIMEOUT_SECONDS = 60


class OpenAICompatProvider:
    def __init__(self, api_key: str, base_url: str, model: str, temperature: float | None = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        try:
            response = requests.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json=payload,
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Network error calling LLM endpoint: {e}") from e
        if response.status_code != 200:
            raise LLMError(f"LLM API error {response.status_code}: {response.text[:500]}")
        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
            # AttributeError covers content=None (e.g. a tool-call-only reply)
            raise LLMError(f"Unexpected LLM response structure: {e}", retryable=False) from e
