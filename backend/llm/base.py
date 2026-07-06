# llm/base.py
"""The provider seam: one protocol + one exception.

Providers return raw model text; ALL prompt building, JSON parsing, and the
retry loop live in llm/service.py. Adapters stay tiny and share zero logic.
"""
from typing import Protocol


class LLMError(Exception):
    """Transport-level failure talking to a provider (network, HTTP status, bad envelope).

    retryable=False means the failure is structural (e.g. malformed response
    envelope) and the service layer should not re-attempt.
    """

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Send one system+user turn, return the model's raw text. Raises LLMError."""
        ...
