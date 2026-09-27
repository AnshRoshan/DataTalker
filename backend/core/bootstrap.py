# core/bootstrap.py
"""First-run registration of the bundled sample databases.

A stranger arriving at a deployment has no database to ask about, and asking them to
find a server path before they have seen the product is a bad first minute. The image
ships two SQLite fixtures, so on an empty registry they are registered as demo sources.

Only ever runs when the registry is empty, and never overwrites a name an operator
chose — re-deploying cannot resurrect these once real connections exist.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent

DEMO_SOURCES: List[Dict[str, Any]] = [
    {
        "file": "hospital.db",
        "name": "Demo — hospital",
        "notes": "Bundled SQLite fixture: departments, doctors, patients, appointments, records, medications.",
    },
    {
        "file": "multi_table.db",
        "name": "Demo — multi-table",
        "notes": "Bundled SQLite fixture for schema-graph and join-path testing.",
    },
]


def register_demo_sources() -> List[str]:
    """Register any bundled fixture that exists. Returns the names added."""
    from core.connections import add_connection, list_connections
    from core.preflight import check_connection
    from core.settings import get_settings

    settings = get_settings()
    if not settings.bootstrap_demo:
        return []
    if list_connections():
        return []  # not a first run

    added: List[str] = []
    for source in DEMO_SOURCES:
        path = _BACKEND_DIR / source["file"]
        if not path.is_file():
            continue
        uri = f"sqlite:///{path.as_posix()}"
        status = check_connection(uri)
        if not status.get("ok"):
            # A broken fixture should not block startup or pretend to be a source.
            logger.warning("demo source %s skipped: %s", source["file"], status.get("error"))
            continue
        add_connection(source["name"], uri, notes=source["notes"], status=status)
        added.append(source["name"])

    if added:
        logger.info("registered demo sources on first run: %s", ", ".join(added))
    return added
