# llm/request_provider.py
"""Bring-your-own-key: per-request LLM credentials, held in memory only.

A deployment does not have to own an LLM key. A caller may send
`X-LLM-Provider` + `X-LLM-Key` (+ optional `X-LLM-Model`) on any data route and the
pipeline uses those for that request alone — the key is never written to disk, never
placed in the audit log, never echoed back, and dies with the request context.

The provider name selects a FIXED base URL. Callers may not supply a URL: that would
turn this server into an attacker-directed HTTP client (the SEC-03 lesson, applied to
the LLM hop). Operators keep the env path, including arbitrary LLM_BASE_URL.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Only presets we will send a stranger's key to. Keep this list public-facing: the
# Settings UI mirrors it.
PRESET_BASE_URLS = {
    "gemini": None,  # GeminiProvider hardcodes the Google endpoint
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}

DEFAULT_MODELS = {
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
    "openai": "gpt-4o-mini",
}


@dataclass(frozen=True)
class RequestLLMCredentials:
    provider: str
    api_key: str
    model: Optional[str] = None


_credentials: ContextVar[Optional[RequestLLMCredentials]] = ContextVar(
    "llm_request_credentials", default=None
)


def parse_headers(provider: Optional[str], key: Optional[str], model: Optional[str]) -> Optional[RequestLLMCredentials]:
    """Turn raw headers into credentials, or None when the caller isn't bringing a key.

    Raises ValueError for an unknown provider so the route can answer 400 rather than
    silently falling back to the operator's key — a caller who thinks they are using
    their own quota must never be billed someone else's.
    """
    if not (provider or key):
        return None
    name = (provider or "").strip().lower()
    if name not in PRESET_BASE_URLS:
        raise ValueError(
            f"Unknown X-LLM-Provider '{name}' (expected one of: {', '.join(sorted(PRESET_BASE_URLS))})."
        )
    if not key or not key.strip():
        raise ValueError("X-LLM-Key is required when X-LLM-Provider is set.")
    return RequestLLMCredentials(
        provider=name,
        api_key=key.strip(),
        model=(model or "").strip() or None,
    )


def set_credentials(creds: Optional[RequestLLMCredentials]):
    """Bind credentials to this request. Always call — including with None — so a
    pooled worker thread can't carry a previous caller's key into the next request."""
    return _credentials.set(creds)


def reset_credentials(token) -> None:
    _credentials.reset(token)


def current_credentials() -> Optional[RequestLLMCredentials]:
    return _credentials.get()


def has_request_credentials() -> bool:
    return _credentials.get() is not None


class LlmCredentialsMiddleware(BaseHTTPMiddleware):
    """Bind X-LLM-* request headers to the request context and clear them after.

    Middleware rather than a route dependency so the reset is guaranteed on every
    exit path, and so no route has to remember to pass the headers down.
    """

    async def dispatch(self, request, call_next):
        headers = request.headers
        try:
            creds = parse_headers(
                headers.get("x-llm-provider"),
                headers.get("x-llm-key"),
                headers.get("x-llm-model"),
            )
        except ValueError as e:
            return JSONResponse(status_code=400, content={"detail": str(e)})
        token = set_credentials(creds)
        try:
            return await call_next(request)
        finally:
            reset_credentials(token)
