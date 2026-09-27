# core/conversations.py
"""Persistent conversations, stored in the same JSON-collection format as connections.

Answers are expensive and a browser's localStorage loses them on another machine, so
threads live server-side and are listed in the sidebar. Every record carries an `owner`
— the signed-in identity's subject, or "anonymous" — and reads filter by it: without
that, one person's questions would be listed to everyone on a shared instance.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.json_store import collection_path, delete_by, load, save, upsert

logger = logging.getLogger(__name__)

_FILENAME = "conversations.json"
_MAX_CONVERSATIONS = 200
_MAX_MESSAGES = 100
_MAX_TITLE = 160
_MAX_TEXT = 20_000
_MAX_ROWS_KEPT = 200

ANONYMOUS = "anonymous"


def _path():
    return collection_path(_FILENAME)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def owner_of(claims: Optional[Dict[str, Any]]) -> str:
    """Which bucket a request's threads live in. Unauthenticated installs share one."""
    return str(claims["sub"]) if claims and claims.get("sub") else ANONYMOUS


def _clip(value: Any, limit: int) -> str:
    return str(value if value is not None else "")[:limit]


def sanitize_messages(raw: Any) -> List[Dict[str, Any]]:
    """A defensive copy of what the client sent. Results are trimmed because storing
    500 rows per turn makes the file grow without bound."""
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw[-_MAX_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        results = item.get("results")
        if isinstance(results, list):
            kept = results[:_MAX_ROWS_KEPT]
        elif isinstance(results, dict):
            kept = [results]
        else:
            kept = []
        follows = item.get("follow_up_questions") or []
        out.append({
            "id": _clip(item.get("id"), 64),
            "question": _clip(item.get("question"), _MAX_TEXT),
            "answer": _clip(item.get("answer"), _MAX_TEXT),
            "sql": _clip(item.get("sql"), _MAX_TEXT),
            "results": kept,
            "follow_up_questions": [_clip(q, 500) for q in follows[:5] if isinstance(q, str)],
            "latency_ms": item.get("latency_ms") if isinstance(item.get("latency_ms"), int) else None,
            "sql_executed": bool(item.get("sql_executed")),
        })
    return out


def list_conversations(owner: str) -> List[Dict[str, Any]]:
    """Header rows only — no message bodies — newest first."""
    rows = [r for r in load(_path()) if r.get("owner") == owner]
    rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return [_header(r) for r in rows]


def get_conversation(conversation_id: str, owner: str) -> Optional[Dict[str, Any]]:
    """The full thread, or None. Another owner's thread reads as missing rather than
    forbidden, so ids cannot be enumerated on a shared instance."""
    for r in load(_path()):
        if r.get("id") == conversation_id and r.get("owner") == owner:
            return r
    return None


def save_conversation(conversation_id: Optional[str], messages: Any, owner: str,
                      source: Optional[str] = None) -> Dict[str, Any]:
    """Create or replace a thread; returns its header row."""
    clean = sanitize_messages(messages)
    existing = get_conversation(conversation_id, owner) if conversation_id else None
    now = _now()
    title = (existing or {}).get("title") or ""
    if clean:
        title = _clip(clean[0]["question"], _MAX_TITLE)

    record = {
        "id": (existing or {}).get("id") or str(uuid.uuid4()),
        "owner": owner,
        "title": title or "New conversation",
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
        "source": source if source is not None else (existing or {}).get("source"),
        "messages": clean,
    }
    new_id = record["id"]
    upsert(_path(), record, lambda r: r.get("id") == new_id)
    _enforce_cap(owner)
    return _header(record)


def delete_conversation(conversation_id: str, owner: str) -> bool:
    return delete_by(_path(), lambda r: r.get("id") == conversation_id and r.get("owner") == owner)


def _header(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record.get("id"),
        "owner": record.get("owner"),
        "title": record.get("title", ""),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "source": record.get("source"),
        "message_count": len(record.get("messages") or []),
    }


def _enforce_cap(owner: str) -> None:
    """Trim the owner's oldest threads after a write, so one long-lived instance cannot
    grow the file forever. Called post-upsert: the thread just written must never be
    the one dropped."""
    records = load(_path())
    mine = [r for r in records if r.get("owner") == owner]
    if len(mine) <= _MAX_CONVERSATIONS:
        return
    keep = {
        r.get("id")
        for r in sorted(mine, key=lambda r: r.get("updated_at") or "")[-_MAX_CONVERSATIONS:]
    }
    save(_path(), [r for r in records if r.get("owner") != owner or r.get("id") in keep])
