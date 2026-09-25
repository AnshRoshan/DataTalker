# core/ratelimit.py
"""Sliding-window rate limiter (PR-09), keyed by client IP.

Thread-safe (the /chat/ + /schema/ handlers run in Starlette's threadpool) and
memory-bounded: keys with no recent hits are evicted once the map grows past a
hard cap. Configured via settings; rate_limit_requests=0 disables the limiter.
"""
import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple

from .settings import get_settings

# Hard bound on tracked keys; stale keys are evicted when exceeded.
_MAX_KEYS = 10_000


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _evict_stale(self, now: float) -> None:
        """Drop keys with no hits inside the window (caller holds the lock)."""
        if len(self._hits) <= _MAX_KEYS:
            return
        stale = [k for k, q in self._hits.items() if not q or now - q[-1] > self.window_seconds]
        for k in stale:
            del self._hits[k]
        # Still over the cap (pathological traffic): drop oldest by last hit.
        if len(self._hits) > _MAX_KEYS:
            ordered = sorted(self._hits, key=lambda k: self._hits[k][-1])
            for k in ordered[: len(self._hits) - _MAX_KEYS]:
                del self._hits[k]

    def check(self, key: str) -> Tuple[bool, int]:
        """Record a hit for key. Returns (allowed, retry_after_seconds)."""
        if self.max_requests <= 0:
            return True, 0
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            self._evict_stale(now)
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - q[0])) + 1)
                return False, retry_after
            q.append(now)
            return True, 0


_limiter: SlidingWindowLimiter | None = None


def get_limiter() -> SlidingWindowLimiter:
    """Process-wide limiter built from settings."""
    global _limiter
    s = get_settings()
    if _limiter is None or _limiter.max_requests != s.rate_limit_requests or _limiter.window_seconds != s.rate_limit_window_seconds:
        _limiter = SlidingWindowLimiter(s.rate_limit_requests, s.rate_limit_window_seconds)
    return _limiter


def client_ip(request) -> str:
    """First hop of X-Forwarded-For, else the socket peer address."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


# POST routes guarded by the limiter.
_RATE_LIMITED_PATHS = {"/chat/", "/schema/"}


class RateLimitMiddleware:
    """Apply the sliding-window limiter to POST /chat/ and POST /schema/.

    Runs outside the auth dependency so repeated bad-key hammering is also
    throttled. Disabled entirely when rate_limit_requests is 0.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] in _RATE_LIMITED_PATHS:
            allowed, retry_after = get_limiter().check(_key_from_scope(scope))
            if not allowed:
                from starlette.responses import JSONResponse

                response = JSONResponse(
                    {"detail": "Rate limit exceeded. Try again later."},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _key_from_scope(scope) -> str:
    """Client IP from the ASGI scope: first X-Forwarded-For hop, else peer host."""
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            first = value.decode("latin-1").split(",")[0].strip()
            if first:
                return first
    client = scope.get("client")
    return client[0] if client else "unknown"
