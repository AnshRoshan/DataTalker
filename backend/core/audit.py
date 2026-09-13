# core/audit.py
"""Append-only audit log (EC-08): one JSON object per line.

Records governance-relevant events (chat queries, schema extractions) to the
file configured by DATATALKER_AUDIT_LOG_PATH (default logs/audit.log under
backend/; empty string disables). Never record credentials or connection
strings — callers pass only non-secret fields.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .settings import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def record_audit(event: Dict[str, Any]) -> None:
    """Append a single-line JSON event to the audit file. Best-effort: an audit
    write failure must never take down the request that produced the event."""
    settings = get_settings()
    if not settings.audit_log_path:
        return  # auditing disabled
    path: Path = settings.audit_log_file
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    line = json.dumps(record, default=str, ensure_ascii=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        logger.warning("Failed to write audit event to %s", path, exc_info=True)
