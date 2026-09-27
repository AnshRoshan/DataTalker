# core/saved_queries.py
"""Saved queries — the library a console needs, and nothing more.

A record stores the statement, the dialect it was written for and who saved it. It does
NOT store a connection's credentials: `source` is the display name only, so a library
entry can never become a place secrets leak from. Re-running goes through the SQL
console guard like any other statement.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.json_store import collection_path, delete_by, find, load, save, upsert

logger = logging.getLogger(__name__)

_FILENAME = "saved_queries.json"
_MAX_PER_OWNER = 300
_MAX_NAME = 120
_MAX_SQL = 20_000
ANONYMOUS = "anonymous"


def _path():
    return collection_path(_FILENAME)


def list_saved(owner: str) -> List[Dict[str, Any]]:
    rows = [r for r in load(_path()) if r.get("owner") == owner]
    rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return rows


def get_saved(query_id: str, owner: str) -> Optional[Dict[str, Any]]:
    return find(_path(), lambda r: r.get("id") == query_id and r.get("owner") == owner)


def save_query(query_id: Optional[str], name: str, sql: str, dialect: Optional[str],
               owner: str, source: Optional[str] = None) -> Dict[str, Any]:
    clean_name = (name or "").strip()[:_MAX_NAME]
    clean_sql = (sql or "").strip()[:_MAX_SQL]
    if not clean_sql:
        raise ValueError("A saved query needs a statement.")

    existing = get_saved(query_id, owner) if query_id else None
    if existing is None and query_id:
        # An id that is not yours reads as not found, same as conversations.
        raise KeyError(query_id)

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": (existing or {}).get("id") or str(uuid.uuid4()),
        "owner": owner,
        "name": clean_name or clean_sql.splitlines()[0][: _MAX_NAME],
        "sql": clean_sql,
        "dialect": dialect or (existing or {}).get("dialect"),
        "source": source if source is not None else (existing or {}).get("source"),
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
        "run_count": int((existing or {}).get("run_count", 0)),
        "last_run_at": (existing or {}).get("last_run_at"),
    }
    saved_id = record["id"]
    upsert(_path(), record, lambda r: r.get("id") == saved_id)
    _enforce_cap(owner)
    return record


def mark_run(query_id: str, owner: str) -> Optional[Dict[str, Any]]:
    """Bookkeeping for re-runs, so the library can show what is actually used."""
    updated = None

    def _bump(r: Dict[str, Any]) -> bool:
        nonlocal updated
        if r.get("id") != query_id or r.get("owner") != owner:
            return False
        r["last_run_at"] = datetime.now(timezone.utc).isoformat()
        r["run_count"] = int(r.get("run_count", 0)) + 1
        updated = r
        return True

    records = load(_path())
    if not any(_bump(r) for r in records):
        return None
    save(_path(), records)
    return updated


def delete_saved(query_id: str, owner: str) -> bool:
    return delete_by(_path(), lambda r: r.get("id") == query_id and r.get("owner") == owner)


def _enforce_cap(owner: str) -> None:
    records = load(_path())
    mine = [r for r in records if r.get("owner") == owner]
    if len(mine) <= _MAX_PER_OWNER:
        return
    keep = {r["id"] for r in sorted(mine, key=lambda r: r.get("updated_at") or "")[-_MAX_PER_OWNER:]}
    save(_path(), [r for r in records if r.get("owner") != owner or r.get("id") in keep])
