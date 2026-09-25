# backend/test_ratelimit.py
# Assert-based self-check for the sliding-window rate limiter (PR-09).
#   uv run --directory backend python test_ratelimit.py
import os
import time

os.environ.setdefault("DATATALKER_API_KEY", "k")     # for the TestClient block
os.environ.setdefault("GEMINI_API_KEY", "dummy")

from core.ratelimit import SlidingWindowLimiter

# --- unit: window fills, then blocks with Retry-After ---
lim = SlidingWindowLimiter(3, 1.0)
for i in range(3):
    allowed, _ = lim.check("1.2.3.4")
    assert allowed, f"hit {i + 1} must be allowed"
allowed, retry_after = lim.check("1.2.3.4")
assert not allowed, "4th hit inside the window must be blocked"
assert retry_after >= 1, retry_after

# other keys are unaffected
allowed, _ = lim.check("5.6.7.8")
assert allowed

# sliding window: after the window passes, hits are allowed again
time.sleep(1.05)
allowed, _ = lim.check("1.2.3.4")
assert allowed

# --- unit: max_requests=0 disables the limiter ---
off = SlidingWindowLimiter(0, 60)
for _ in range(100):
    allowed, _ = off.check("1.1.1.1")
    assert allowed

# --- unit: bounded memory (stale keys evicted when over the cap) ---
lim2 = SlidingWindowLimiter(1, 60)
old = time.monotonic() - 3600
for i in range(10_005):
    lim2._hits[f"stale-{i}"] = __import__("collections").deque([old])
allowed, _ = lim2.check("new-client")
assert allowed
from core.ratelimit import _MAX_KEYS
assert len(lim2._hits) <= _MAX_KEYS, "stale keys must be evicted to bound memory"
assert "new-client" in lim2._hits

# --- integration: middleware returns 429 + Retry-After on POST /schema/ ---
os.environ["DATATALKER_RATE_LIMIT_REQUESTS"] = "1"
from core.settings import get_settings
get_settings.cache_clear()
from core import ratelimit as rl
rl._limiter = None  # force rebuild from settings

import main
from fastapi.testclient import TestClient
c = TestClient(main.fastapi_app, headers={"Authorization": "Bearer k"})

r1 = c.post("/schema/")           # 400 (no db given) — but the budget is consumed
assert r1.status_code == 400, r1.status_code
r2 = c.post("/schema/")
assert r2.status_code == 429, r2.status_code
assert r2.json()["detail"] == "Rate limit exceeded. Try again later."
assert "Retry-After" in r2.headers
assert int(r2.headers["Retry-After"]) >= 1

# GET routes are not limited
assert c.get("/health").status_code == 200

# cleanup
os.environ.pop("DATATALKER_RATE_LIMIT_REQUESTS", None)
get_settings.cache_clear()

print("ratelimit: all assertions passed")
