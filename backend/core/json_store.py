# core/json_store.py
"""The one JSON-collection store: connections, conversations and saved queries are all
"a list of records in one file under the data dir", and that rule used to live three
times. Reads tolerate a corrupt file (treat as empty) and writes are atomic, because a
half-written registry is the failure mode that actually bites on container restarts.

Thread-safe within the single worker this app is designed to run; multi-process
deployments need a real database, which is called out in CLAUDE.md.
"""
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

_lock = threading.RLock()


def collection_path(filename: str) -> Path:
    from core.settings import get_settings

    return Path(get_settings().data_dir) / filename


def load(path: Path) -> List[Dict[str, Any]]:
    with _lock:
        if not path.is_file():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("%s unreadable (%s); treating as empty", path, e)
            return []
        if not isinstance(raw, list):
            logger.warning("%s is not a list; treating as empty", path)
            return []
        return [r for r in raw if isinstance(r, dict)]


def save(path: Path, records: List[Dict[str, Any]]) -> None:
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)
        os.replace(tmp, path)


def upsert(path: Path, record: Dict[str, Any], match: Callable[[Dict[str, Any]], bool]
           ) -> Dict[str, Any]:
    """Replace the record `match` selects, or append it."""
    with _lock:
        records = load(path)
        for i, existing in enumerate(records):
            if match(existing):
                records[i] = record
                break
        else:
            records.append(record)
        save(path, records)
    return record


def delete_by(path: Path, match: Callable[[Dict[str, Any]], bool]) -> bool:
    with _lock:
        records = load(path)
        remaining = [r for r in records if not match(r)]
        if len(remaining) == len(records):
            return False
        save(path, remaining)
    return True


def find(path: Path, match: Callable[[Dict[str, Any]], bool]) -> Dict[str, Any] | None:
    for r in load(path):
        if match(r):
            return r
    return None
