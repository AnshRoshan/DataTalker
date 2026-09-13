# core/connections.py
"""Connections registry (JSON-file-backed) for managing many databases.

SECRETS CAVEAT: connection strings (which contain credentials) are stored
PLAINTEXT in <data_dir>/connections.json. This is acceptable for the current
self-hosted, single-user deployment model (the server already holds
DATATALKER_API_KEY and LLM keys in backend/.env); it is NOT multi-tenant
storage. The API never returns full connection strings — list endpoints carry a
password-masked URI only (see mask_uri).

Each record: {id (uuid), name, connection_string, notes, created_at,
last_checked_at, last_status}. last_status is the preflight dict from
core/preflight.py (dialect/driver/server_version/table_count/sample_tables/
warnings) or {"ok": False, "error": ...}. Thread-safe: every read/write takes
the module lock and re-reads the file (multi-process safe enough for the
single-user tool; writes are atomic via temp-file rename).
"""
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_REGISTRY_FILENAME = "connections.json"


def _registry_path() -> Path:
    from core.settings import get_settings

    return Path(get_settings().data_dir) / _REGISTRY_FILENAME


def mask_uri(uri: str) -> str:
    """Mask the password in a URI: postgresql://user:***@host/db.
    A URI without a password component is returned unchanged."""
    if "@" in uri and "://" in uri:
        scheme, _, rest = uri.partition("://")
        creds, _, host = rest.rpartition("@")
        user, sep, _pw = creds.partition(":")
        if sep:  # only mask when there is actually a password segment
            return f"{scheme}://{user}{sep}***@{host}"
    return uri


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> List[Dict[str, Any]]:
    path = _registry_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, list) else []
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("connections registry %s unreadable (%s); treating as empty", path, e)
        return []


def _save(records: List[Dict[str, Any]]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    os.replace(tmp, path)


def list_connections() -> List[Dict[str, Any]]:
    """All connections WITHOUT full connection strings (password masked)."""
    with _lock:
        records = _load()
    out = []
    for r in records:
        out.append({k: v for k, v in r.items() if k != "connection_string"} | {
            "connection_string_masked": mask_uri(str(r.get("connection_string", ""))),
        })
    return out


def add_connection(name: str, connection_string: str,
                   notes: str = "", status: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Store a validated connection; returns the record (masked URI)."""
    record = {
        "id": str(uuid.uuid4()),
        "name": name,
        "connection_string": connection_string,
        "notes": notes or "",
        "created_at": _now_iso(),
        "last_checked_at": _now_iso() if status is not None else None,
        "last_status": status,
    }
    with _lock:
        records = _load()
        records.append(record)
        _save(records)
    logger.info("connection registered (id=%s, name=%s)", record["id"], name)
    return public_view(record)


def get_connection(connection_id: str) -> Optional[Dict[str, Any]]:
    """Full record (including the real connection string) or None."""
    with _lock:
        for r in _load():
            if r.get("id") == connection_id:
                return r
    return None


def delete_connection(connection_id: str) -> bool:
    with _lock:
        records = _load()
        remaining = [r for r in records if r.get("id") != connection_id]
        if len(remaining) == len(records):
            return False
        _save(remaining)
    logger.info("connection deleted (id=%s)", connection_id)
    return True


def update_status(connection_id: str, status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Persist a preflight result against the connection."""
    with _lock:
        records = _load()
        for r in records:
            if r.get("id") == connection_id:
                r["last_checked_at"] = _now_iso()
                r["last_status"] = status
                _save(records)
                return public_view(r)
    return None


def public_view(record: Dict[str, Any]) -> Dict[str, Any]:
    """Record safe to return over the API: no real connection string.
    Idempotent — passing an already-public record returns it unchanged."""
    if "connection_string" not in record:
        return dict(record)
    return {k: v for k, v in record.items() if k != "connection_string"} | {
        "connection_string_masked": mask_uri(str(record.get("connection_string", ""))),
    }
