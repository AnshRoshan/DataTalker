# llm/base.py
"""The provider seam: one protocol + one exception.

Providers return raw model text; ALL prompt building, JSON parsing, and the
retry loop live in llm/service.py. Adapters stay tiny and share zero logic.
"""
from typing import Protocol


class LLMError(Exception):
    """Transport-level failure talking to a provider (network, HTTP status, bad envelope).

    retryable=False means the failure is structural (e.g. malformed response
    envelope, rejected credentials) and the service layer should not re-attempt.
    hint is a secret-free, actionable message shown to the end user; empty means
    the service falls back to its generic wording.
    """

    def __init__(self, message: str, retryable: bool = True, hint: str = ""):
        super().__init__(message)
        self.retryable = retryable
        self.hint = hint


_KEY_REJECTION_MARKERS = ("api key", "api_key", "apikey", "invalid x-api-key")


def credential_rejection(status_code: int, body: str) -> bool:
    """Did the provider reject our credentials/config (as opposed to choking on the request)?

    401/403 are always auth/config. A 400 is only a credential problem when the body
    says so — Gemini answers a bad key with 400 "API key not valid", which otherwise
    reads like a transient failure and burns the whole retry budget.
    """
    if status_code in (401, 403):
        return True
    text = body.lower()
    return any(marker in text for marker in _KEY_REJECTION_MARKERS)


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Send one system+user turn, return the model's raw text. Raises LLMError."""
        ...
