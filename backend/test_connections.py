# backend/test_connections.py
# Assert-based self-check for the connections registry (core/connections.py):
# CRUD on a temp data dir, password masking, unknown-id errors.
#   uv run --directory backend python test_connections.py
import os
import pathlib
import tempfile

# Data dir must be set BEFORE core.settings is first instantiated (lru_cached).
_TMP = tempfile.mkdtemp(prefix="dataltalker_conns_")
os.environ["DATATALKER_DATA_DIR"] = _TMP

from core.connections import (  # noqa: E402
    _registry_path,
    add_connection,
    delete_connection,
    get_connection,
    list_connections,
    mask_uri,
    public_view,
    update_status,
)
from core.settings import get_settings  # noqa: E402

assert get_settings().data_dir == _TMP
assert str(_registry_path()).endswith("connections.json")

# --- password masking ---
assert mask_uri("postgresql://user:secret@host:5432/mydb") == "postgresql://user:***@host:5432/mydb"
assert mask_uri("mysql://root:pw123@localhost/db") == "mysql://root:***@localhost/db"
assert mask_uri("postgresql://user@host/db") == "postgresql://user@host/db"  # no password
assert mask_uri("sqlite:///C:/data/hospital.db") == "sqlite:///C:/data/hospital.db"  # unchanged
assert "***" not in mask_uri("postgresql://user@host/db")

# --- create + read-back ---
status = {"ok": True, "dialect": "sqlite", "driver": "pysqlite", "table_count": 7}
rec = add_connection("hospital", "sqlite:///C:/tmp/hospital.db", notes="fixture", status=status)
assert rec["id"] and rec["name"] == "hospital"
assert rec["connection_string_masked"] == "sqlite:///C:/tmp/hospital.db"
assert "connection_string" not in rec, "full URI must never appear in the public view"
assert rec["last_status"] == status and rec["last_checked_at"]

full = get_connection(rec["id"])
assert full is not None and full["connection_string"] == "sqlite:///C:/tmp/hospital.db"

rec2 = add_connection(
    "pg-prod", "postgresql://admin:s3cret@db.example.com:5432/analytics", notes=""
)
masked = public_view(rec2)
assert masked["connection_string_masked"] == "postgresql://admin:***@db.example.com:5432/analytics"

# --- list: no full connection strings anywhere ---
listing = list_connections()
assert len(listing) == 2
assert all("connection_string" not in c for c in listing)
assert all("connection_string_masked" in c for c in listing)
serialized = str(listing)
assert "s3cret" not in serialized, "credential leaked in listing"

# --- update status ---
updated = update_status(rec["id"], {"ok": False, "error": "boom"})
assert updated["last_status"] == {"ok": False, "error": "boom"}
assert updated["last_checked_at"] >= rec["last_checked_at"]

# --- delete + unknown-id errors ---
assert delete_connection(rec["id"]) is True
assert len(list_connections()) == 1
assert delete_connection(rec["id"]) is False          # already gone
assert delete_connection("no-such-id") is False
assert get_connection("no-such-id") is None
assert update_status("no-such-id", {"ok": True}) is None

# --- persistence across reloads (file-backed) ---
import json  # noqa: E402

with open(_registry_path(), "r", encoding="utf-8") as f:
    on_disk = json.load(f)
assert len(on_disk) == 1 and on_disk[0]["name"] == "pg-prod"

print("connections: all assertions passed")
