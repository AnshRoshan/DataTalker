# backend/test_auth_login.py
# Assert-based self-check for signed sessions + the Google sign-in routes.
# No network: Google's token verification is never called with a real credential here.
#   uv run --directory backend python test_auth_login.py
import os
import time

os.environ["DATATALKER_SESSION_SECRET"] = "unit-test-secret"
os.environ["DATATALKER_GOOGLE_CLIENT_ID"] = "1234567890-abc.apps.googleusercontent.com"

from core.settings import get_settings  # noqa: E402

get_settings.cache_clear()

from core import auth  # noqa: E402

USER = {"sub": "g-1", "email": "dev@example.com", "name": "Dev", "picture": "https://x/p.png"}

# --- round trip ---
token = auth.create_session_token(USER)
claims = auth.read_session_token(token)
assert claims and claims["sub"] == "g-1" and claims["email"] == "dev@example.com"

# --- tampering is rejected ---
body, _, sig = token.rpartition(".")
assert auth.read_session_token(f"{body}.{sig[:-2]}xx") is None, "bad signature must not read"
assert auth.read_session_token(f"{body}.{'A' * len(sig)}") is None
assert auth.read_session_token("nodothere") is None
assert auth.read_session_token(None) is None
assert auth.read_session_token("") is None

# a payload re-signed under a different key is refused
import base64, hashlib, hmac  # noqa: E402

forged_body = base64.urlsafe_b64encode(
    b'{"sub":"attacker","email":"attacker@evil","exp":9999999999}'
)
forged_sig = base64.urlsafe_b64encode(hmac.new(b"wrong-key", forged_body, hashlib.sha256).digest()).decode()
assert auth.read_session_token(f"{forged_body.decode()}.{forged_sig}") is None

# --- expiry ---
auth.SESSION_TTL_SECONDS = -60
try:
    stale = auth.create_session_token(USER)
finally:
    auth.SESSION_TTL_SECONDS = 7 * 24 * 3600
assert auth.read_session_token(stale) is None, "expired session must not read"
assert auth.read_session_token(auth.create_session_token(USER)) is not None, "a fresh one must read"

# --- safe_user never carries the subject or anything else internal ---
assert auth.safe_user(USER) == {"email": "dev@example.com", "name": "Dev", "picture": "https://x/p.png"}

# --- the routes, through the real app ---
from fastapi.testclient import TestClient  # noqa: E402

os.environ.pop("DATATALKER_API_KEY", None)
os.environ.pop("DATATALKER_REQUIRE_LOGIN", None)
os.environ.pop("DATATALKER_REQUIRE_API_KEY", None)
import main as app_module  # noqa: E402

app_module.fastapi_app = app_module.create_app()
client = TestClient(app_module.fastapi_app)

cfg = client.get("/auth/config").json()
assert cfg["google_enabled"] is True and cfg["client_id"].endswith("googleusercontent.com")
assert cfg["require_login"] is False

me = client.get("/auth/me").json()
assert me == {"authenticated": False, "user": None}

# a configured server rejects a malformed credential rather than trusting it
bad = client.post("/auth/google", json={"credential": "not-a-jwt"})
assert bad.status_code == 401 and "Google" in bad.json()["detail"], bad.text

# an unconfigured server refuses to exchange a credential at all
del os.environ["DATATALKER_GOOGLE_CLIENT_ID"]
get_settings.cache_clear()
app_module.fastapi_app = app_module.create_app()
off = TestClient(app_module.fastapi_app)
assert off.get("/auth/config").json()["google_enabled"] is False
assert off.post("/auth/google", json={"credential": "whatever"}).status_code == 503

# --- require_login actually gates the data plane ---
os.environ["DATATALKER_GOOGLE_CLIENT_ID"] = "1234567890-abc.apps.googleusercontent.com"
os.environ["DATATALKER_REQUIRE_LOGIN"] = "true"
os.environ["DATATALKER_REQUIRE_API_KEY"] = "false"
get_settings.cache_clear()
app_module.fastapi_app = app_module.create_app()
gated = TestClient(app_module.fastapi_app)

r = gated.post("/chat/", data={"question": "hi", "db_path": "hospital.db"})
assert r.status_code == 401, f"expected 401 without a session, got {r.status_code}"
assert "Sign in" in r.json()["detail"]

# even presenting a shared API key must not bypass the login requirement
gated.cookies.set(auth.SESSION_COOKIE, "junk")
r2 = gated.post("/chat/", data={"question": "hi", "db_path": "hospital.db"})
assert r2.status_code == 401, "a garbage cookie must not authenticate"

gated.cookies.set(auth.SESSION_COOKIE, auth.create_session_token(USER))
r3 = gated.get("/auth/me")
assert r3.json()["authenticated"] is True and r3.json()["user"]["email"] == "dev@example.com"
# data route now gets past auth (it may still fail later for an unrelated reason —
# the point is it is no longer a 401)
r4 = gated.post("/chat/", data={"question": "hi", "db_path": "nope/missing.db"})
assert r4.status_code != 401, r4.status_code

assert gated.post("/auth/logout").status_code == 204

# client-side routes must survive a refresh (the SPA shell is served for any path the
# API does not claim, including a stale asset URL — same convention as static hosts)
for path in ("/", "/login", "/studio", "/assets/definitely-missing.js"):
    assert gated.get(path).status_code == 200, f"{path} should serve the app shell"
assert gated.get("/assets/definitely-missing.js").text.lstrip().startswith("<!doctype")

print("auth_login: all assertions passed")
