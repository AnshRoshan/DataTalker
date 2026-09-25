# core/preflight.py
"""Connection preflight: validate a database URI and report what's there.

check_connection(uri) connects via the pooled engine (core/engines.py) with a
hard timeout and returns a structured dict:

    {"ok": True,
     "dialect": ..., "driver": ..., "server_version": ...,
     "table_count": N, "sample_tables": [...],
     "warnings": ["could not verify read-only privileges — use a least-privilege role", ...]}

Every failure path returns a structured error dict — never a raw traceback —
and the URI itself is NEVER included in the result (credentials, SEC-05).
Used by the /connections/ API and as the gate for non-whitelisted SQLAlchemy
dialects (core/database.py).
"""
import logging
import threading
from typing import Any, Dict, Optional

from sqlalchemy import inspect, text

from core.engines import get_engine

logger = logging.getLogger(__name__)

# Hard wall-clock budget for the whole preflight (connect + introspection).
PREFLIGHT_TIMEOUT_SECONDS = 15
_SAMPLE_TABLE_LIMIT = 10

# Version probes per dialect family. None = no cheap probe (skip reporting).
_VERSION_PROBES = {
    "postgresql": "SELECT version()",
    "mysql": "SELECT version()",
    "sqlite": "SELECT sqlite_version()",
    "mssql": "SELECT @@VERSION",
}


def _redact_uri(uri: str) -> str:
    """Log-safe form of the URI (no credentials)."""
    if "@" in uri and "://" in uri:
        scheme, _, rest = uri.partition("://")
        return f"{scheme}://***@{rest.rpartition('@')[-1]}"
    return uri


def _probe(engine, dialect: str) -> Dict[str, Any]:
    """Introspect the live database (runs inside the timeout thread)."""
    out: Dict[str, Any] = {}
    # Fail fast: a connection that cannot be established is a failed preflight —
    # let the error propagate to check_connection's structured handler.
    with engine.connect() as first_conn:
        first_conn.close()

    probe = _VERSION_PROBES.get(dialect)
    if probe:
        try:
            with engine.connect() as conn:
                out["server_version"] = str(conn.execute(text(probe)).scalar())[:120]
        except Exception as e:
            logger.debug("version probe failed for %s: %s", dialect, e)
            out["warnings"] = ["could not determine the server version."]

    warnings = out.get("warnings", [])
    warnings.append(
        "could not verify read-only privileges — use a least-privilege role."
    )
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        out["table_count"] = len(tables)
        out["sample_tables"] = tables[:_SAMPLE_TABLE_LIMIT]
    except Exception as e:
        logger.debug("introspection failed: %s", e)
        warnings.append("schema introspection failed; table counts unavailable.")
    out["warnings"] = warnings
    return out


def check_connection(uri: str, timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
    """Validate a database URI. Never raises; never returns the URI."""
    if not uri or not str(uri).strip():
        return {"ok": False, "error": "Connection string cannot be empty."}

    deadline = PREFLIGHT_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    result: Dict[str, Any] = {}

    def _run() -> None:
        try:
            engine = get_engine(str(uri).strip())
            dialect = engine.dialect.name
            driver = engine.dialect.driver
            details = _probe(engine, dialect)
            result.update({"ok": True, "dialect": dialect, "driver": driver, **details})
        except ModuleNotFoundError as e:
            # Missing optional driver extra — name the package, not the traceback.
            logger.info("preflight: missing driver module %s", e.name)
            result.update({
                "ok": False,
                "error": (
                    f"Database driver not installed ({e.name}). "
                    "Install the matching optional extra, e.g. "
                    "'pip install talktodata[mssql]' or talktodata[oracle]."
                ),
            })
        except Exception as e:
            # Full detail to the log only; the structured result stays generic.
            logger.warning("preflight failed (%s): %s", type(e).__name__, e, exc_info=True)
            result.update({
                "ok": False,
                "error": "Could not connect to the database. "
                         "Check the connection string, network reachability, and credentials.",
            })

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(deadline)
    if worker.is_alive():
        logger.warning("preflight timed out after %ss (%s)", deadline, _redact_uri(str(uri)))
        return {
            "ok": False,
            "error": f"Connection attempt timed out after {deadline} seconds.",
        }
    return result
