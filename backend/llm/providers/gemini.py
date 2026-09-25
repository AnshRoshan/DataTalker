# llm/providers/gemini.py
"""Google Gemini via the public generateContent REST API (no SDK, matches pre-refactor)."""
import requests

from llm.base import LLMError, credential_rejection

_TIMEOUT_SECONDS = 60

_KEY_HINT = (
    "Google rejected the configured Gemini key. Set a valid GEMINI_API_KEY in "
    "backend/.env, or switch providers (LLM_PROVIDER=openrouter|openai)."
)


class GeminiProvider:
    def __init__(self, api_key: str, model: str, temperature: float | None = None):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def complete(self, system: str, user: str) -> str:
        # Gemini has a dedicated systemInstruction field, but the pre-refactor code
        # inlined the system prompt into the single user turn; keep that behavior.
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}]
        }
        if self.temperature is not None:
            payload["generationConfig"] = {"temperature": self.temperature}
        try:
            response = requests.post(
                url=f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,  # header, never URL param (PR-05)
                },
                json=payload,
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Network error calling Gemini: {e}") from e
        if response.status_code != 200:
            rejected = credential_rejection(response.status_code, response.text)
            raise LLMError(
                f"Gemini API error {response.status_code}: {response.text[:500]}",
                retryable=not rejected,
                hint=_KEY_HINT if rejected else "",
            )
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
            raise LLMError(f"Unexpected Gemini response structure: {e}", retryable=False) from e
