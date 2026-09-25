# core/engines.py
"""Process-global SQLAlchemy engine pool (PR-03).

One engine per db_uri, reused across requests instead of the old
create/dispose-per-request churn. Bounded (LRU-style eviction) with TTL-based
disposal of engines unused for ENGINE_TTL_SECONDS.

SQLite connections are pinned read-only here via a "connect" event listener
(`PRAGMA query_only = ON`), so every consumer of get_engine() gets the same
guarantee the executor used to set up by hand.
"""
import logging
import threading
import time

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

ENGINE_TTL_SECONDS = 10 * 60   # dispose engines unused for 10 minutes
MAX_ENGINES = 16               # bound on distinct engines kept alive
POOL_SIZE = 5
MAX_OVERFLOW = 10

_lock = threading.Lock()
_engines: dict[str, dict] = {}  # db_uri -> {"engine": Engine, "last_used": float}


def _sqlite_read_only_connect(dbapi_connection, _connection_record):
    """Pin every SQLite connection read-only (defense-in-depth, SEC-01).

    Postgres/MySQL rely on the SQL guard plus a least-privilege read-only role;
    SQLite has no roles, so the PRAGMA is the only native pin available.
    """
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA query_only = ON")
        cursor.close()
    except Exception:  # pragma: no cover - never block a connection on the pragma
        logger.warning("Could not set PRAGMA query_only on sqlite connection", exc_info=True)


def _build_engine(db_uri: str) -> Engine:
    if db_uri.strip().lower().startswith("sqlite"):
        # NullPool for SQLite: pooled connections would keep the .db file locked
        # (Windows), breaking temp-upload cleanup. The engine object itself is
        # still cached; the read-only PRAGMA applies via the connect listener.
        engine = create_engine(db_uri, pool_pre_ping=True, poolclass=NullPool)
        event.listen(engine, "connect", _sqlite_read_only_connect)
        return engine
    return create_engine(
        db_uri,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
    )


def get_engine(db_uri: str) -> Engine:
    """Return a cached Engine for db_uri, creating it on first use."""
    now = time.time()
    with _lock:
        # TTL eviction: drop engines idle past the window.
        stale = [k for k, v in _engines.items() if now - v["last_used"] > ENGINE_TTL_SECONDS]
        for k in stale:
            logger.debug("disposing idle engine (TTL): %s", _redact(k))
            _engines.pop(k)["engine"].dispose()
        # Hard bound: evict the least-recently-used engine when full.
        while len(_engines) >= MAX_ENGINES:
            lru_key = min(_engines, key=lambda k: _engines[k]["last_used"])
            logger.debug("disposing LRU engine (pool full): %s", _redact(lru_key))
            _engines.pop(lru_key)["engine"].dispose()

        entry = _engines.get(db_uri)
        if entry is None:
            logger.debug("creating pooled engine: %s", _redact(db_uri))
            entry = {"engine": _build_engine(db_uri), "last_used": now}
            _engines[db_uri] = entry
        entry["last_used"] = now
        return entry["engine"]


def _redact(uri: str) -> str:
    """Log-friendly URI: strip credentials if present."""
    if "@" in uri:
        scheme, _, rest = uri.partition("://")
        return f"{scheme}://***@{rest.split('@', 1)[-1]}" if "://" in uri else uri
    return uri


def dispose_all() -> None:
    """Dispose every pooled engine (used by tests and graceful shutdown)."""
    with _lock:
        for entry in _engines.values():
            entry["engine"].dispose()
        _engines.clear()
