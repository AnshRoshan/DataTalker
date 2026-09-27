# core/auth.py
"""Google sign-in and stateless sessions.

A visitor authenticates with Google Identity Services in the browser and posts the
resulting ID token here. We verify it against Google's published keys, then issue our
own signed cookie. No user table and no database: the identity lives entirely inside
the signed payload, which is the right shape for a tool that has no app-database and
must keep working on an ephemeral container disk.

Trade-offs worth knowing before you turn this on:
  * There is no server-side revocation. Signing out deletes the cookie; a stolen
    cookie stays valid until it expires, so the lifetime is deliberately short-ish and
    the cookie is HttpOnly + SameSite=Lax + Secure.
  * Per-user data (saved connections, history) is NOT scoped by this identity yet —
    see USER SCOPING in require_api_key. Turning on login restricts who may use the
    instance; it does not yet partition what they can see.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

SESSION_COOKIE = "dt_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # a week; long enough to survive a restart
_MAX_TTL = 10 * 24 * 3600

_GOOGLE_ISSUERS = (
    "https://accounts.google.com",
    "accounts.google.com",  # the historical value, still issued
)


def _secret() -> str:
    """Sessions key. Falls back to the API key so a small deployment configures one
    secret, not two; a fresh random key otherwise (sessions then end with the process)."""
    import os

    from core.settings import get_settings

    settings = get_settings()
    secret = settings.session_secret or os.getenv("DATATALKER_API_KEY", "")
    if secret:
        return secret
    global _EPHEMERAL_SECRET
    if not _EPHEMERAL_SECRET:
        _EPHEMERAL_SECRET = secrets.token_urlsafe(32)
        logger.warning(
            "DATATALKER_SESSION_SECRET is not set — using a random in-process key, so "
            "sign-ins expire when this container restarts. Set a stable secret for production."
        )
    return _EPHEMERAL_SECRET


_EPHEMERAL_SECRET = ""


def _sign(body: bytes, secret: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def create_session_token(user: Dict[str, Any]) -> str:
    """Serialize a user into a signed, self-describing cookie value."""
    payload = {
        "sub": user["sub"],
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "picture": user.get("picture", ""),
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body.decode()}.{_sign(body, _secret())}"


def read_session_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Verify a cookie. Returns None on any problem — never raises to a caller."""
    if not token or "." not in token:
        return None
    body, _, signature = token.rpartition(".")
    try:
        expected = _sign(body.encode(), _secret())
        # compare_digest, not ==: a valid-looking prefix must not be trusted faster
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        logger.debug("session cookie rejected: %r", e)
        return None
    if not isinstance(payload, dict) or not payload.get("sub"):
        return None
    if int(payload.get("exp", 0)) < time.time():
        return None
    return payload


def current_user(request: Request) -> Optional[Dict[str, Any]]:
    return read_session_token(request.cookies.get(SESSION_COOKIE))


def verify_google_id_token(credential: str) -> Dict[str, Any]:
    """Exchange a Google ID token for verified claims. 401 on anything suspicious."""
    from core.settings import get_settings

    client_id = get_settings().google_client_id
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server.")

    from google.auth.transport import requests as google_requests  # imported lazily: only needed when enabled
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_oauth2_token(
            credential, google_requests.Request(), audience=client_id
        )
    except ValueError as e:
        # signature, audience, issuer or expiry failure — Google's own wording is
        # variable, so log the detail and hand the client a generic reason.
        logger.warning("Google ID token rejected: %r", e)
        raise HTTPException(status_code=401, detail="Google rejected that sign-in token.")

    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Unexpected token issuer.")
    if int(claims.get("exp", 0)) > time.time() + _MAX_TTL:
        raise HTTPException(status_code=401, detail="Token lifetime is implausibly long.")

    email = claims.get("email")
    if not email or claims.get("email_verified") is False:
        raise HTTPException(status_code=401, detail="The Google account has no verified email.")

    return {
        "sub": str(claims["sub"]),
        "email": email,
        "name": claims.get("name") or email.split("@")[0],
        "picture": claims.get("picture", ""),
    }


def safe_user(claims: Dict[str, Any]) -> Dict[str, Any]:
    """What the browser is allowed to learn about the signed-in identity."""
    return {
        "email": claims.get("email", ""),
        "name": claims.get("name", ""),
        "picture": claims.get("picture", ""),
    }


# ---------------------------------------------------------------------------
# USER SCOPING
# ---------------------------------------------------------------------------
# Saved connections and chat state are still instance-global. Once this ships to
# more than one person, key the connections registry by claims["sub"] so one user
# cannot reach another's databases — until then, require_login is an access gate,
# not a tenancy boundary, and that distinction is load-bearing for anyone treating
# this as multi-tenant.
