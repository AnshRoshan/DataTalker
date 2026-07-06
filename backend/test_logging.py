# backend/test_logging.py
# Assert-based self-check for the request-context middleware (PR-06).
#   uv run --directory backend python test_logging.py
import os

os.environ.setdefault("DATATALKER_API_KEY", "k")
os.environ.setdefault("GEMINI_API_KEY", "dummy")

from fastapi.testclient import TestClient
import main

c = TestClient(main.fastapi_app)

r = c.get("/health")
assert r.status_code == 200
assert r.headers.get("X-Request-ID"), "middleware must add an X-Request-ID header"

# a client-supplied id is echoed back so an error can be traced end to end
r2 = c.get("/health", headers={"X-Request-ID": "trace-abc"})
assert r2.headers.get("X-Request-ID") == "trace-abc", r2.headers

print("logging: all assertions passed")
