# core/stats.py
"""Insights derived from the audit log — no second source of truth.

Every number on the Insights screen comes from reading the same JSONL file the
pipeline already writes, so a stat cannot disagree with an audit entry (the usual way
dashboards rot). The file is read from the tail: an instance may hold months of
history and the aggregation only cares about a bounded recent window.
"""
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core.settings import get_settings

logger = logging.getLogger(__name__)

_MAX_LINES = 20_000  # plenty for the 14-day window; bounds memory on a long-lived box
_WINDOW_DAYS = 14


def _read_events() -> List[Dict[str, Any]]:
    settings = get_settings()
    path = settings.audit_log_file
    if not settings.audit_log_path or not path.is_file():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = list(deque(f, maxlen=_MAX_LINES))
    except OSError as e:
        logger.warning("audit log %s unreadable: %r", path, e)
        return []

    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue  # a torn final line is normal after a crash; skip it
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _percentile(values: List[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def summarize(window_days: int = _WINDOW_DAYS) -> Dict[str, Any]:
    """Totals, safety verdicts, latency and a per-day activity series."""
    events = _read_events()
    since = datetime.now(timezone.utc) - timedelta(days=window_days - 1)

    chats = [e for e in events if e.get("event") == "chat"]
    in_window = [e for e in chats if (_ts(e.get("timestamp")) or since) >= since]

    latencies = [e["latency_ms"] for e in chats if isinstance(e.get("latency_ms"), int)]
    rows = [e.get("row_count", 0) for e in chats if isinstance(e.get("row_count"), int)]
    blocked = [e for e in chats if e.get("validator_rejected")]
    executed = [e for e in chats if e.get("executed")]

    by_day: Dict[str, Dict[str, int]] = defaultdict(lambda: {"questions": 0, "blocked": 0})
    for e in in_window:
        stamp = _ts(e.get("timestamp"))
        if not stamp:
            continue
        key = stamp.astimezone(timezone.utc).date().isoformat()
        by_day[key]["questions"] += 1
        if e.get("validator_rejected"):
            by_day[key]["blocked"] += 1
    # Fill the window so the chart's x-axis does not stretch/shrink with usage.
    activity = []
    for offset in range(window_days):
        day = (since + timedelta(days=offset)).date().isoformat()
        activity.append({"date": day, **by_day.get(day, {"questions": 0, "blocked": 0})})

    dialects: Dict[str, int] = defaultdict(int)
    for e in chats:
        if isinstance(e.get("dialect"), str):
            dialects[e["dialect"]] += 1

    return {
        "window_days": window_days,
        "questions": len(chats),
        "questions_in_window": len(in_window),
        "executed": len(executed),
        "blocked": len(blocked),
        "truncated": len([e for e in chats if e.get("truncated")]),
        "rows_returned": sum(rows),
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 95),
        "slowest_ms": max(latencies) if latencies else None,
        "dialects": dict(dialects),
        "activity": activity,
        "sign_ins": len([e for e in events if e.get("event") == "sign_in"]),
        "schema_reads": len([e for e in events if e.get("event") == "schema_extract"]),
        "audit_enabled": bool(get_settings().audit_log_path),
    }


def recent_history(limit: int = 100) -> List[Dict[str, Any]]:
    """The Library's audit trail: recent questions with their verdict and cost."""
    chats = [e for e in _read_events() if e.get("event") == "chat"]
    chats.reverse()
    return [
        {
            "timestamp": e.get("timestamp"),
            "request_id": e.get("request_id"),
            "question": e.get("question", ""),
            "sql": e.get("sql", ""),
            "dialect": e.get("dialect"),
            "executed": bool(e.get("executed")),
            "validator_rejected": bool(e.get("validator_rejected")),
            "row_count": e.get("row_count", 0),
            "truncated": bool(e.get("truncated")),
            "latency_ms": e.get("latency_ms"),
        }
        for e in chats[:limit]
    ]
