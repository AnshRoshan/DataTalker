# backend/test_audit.py
# Assert-based self-check for the append-only audit log (EC-08).
#   uv run --directory backend python test_audit.py
import json
import os
import tempfile

from core.settings import get_settings

TMP = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
TMP.close()
os.unlink(TMP.name)  # audit module must create the file (and dirs) itself

os.environ["DATATALKER_AUDIT_LOG_PATH"] = TMP.name.replace("\\", "/")
get_settings.cache_clear()
try:
    from core.audit import record_audit

    record_audit({"event": "chat", "request_id": "abc123", "dialect": "sqlite", "row_count": 2})
    record_audit({"event": "chat", "request_id": "def456", "dialect": "sqlite", "row_count": 0})

    with open(TMP.name, "r", encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    assert len(lines) == 2, "one JSON object per line"
    first = json.loads(lines[0])
    assert first["event"] == "chat"
    assert first["request_id"] == "abc123"
    assert "timestamp" in first and "T" in first["timestamp"], "ISO timestamp included"
    assert json.loads(lines[1])["request_id"] == "def456"

    # nested values are serialized safely
    record_audit({"event": "x", "payload": {"a": [1, 2]}})
    with open(TMP.name, "r", encoding="utf-8") as f:
        assert json.loads(f.read().splitlines()[-1])["payload"] == {"a": [1, 2]}
finally:
    os.environ.pop("DATATALKER_AUDIT_LOG_PATH", None)
    get_settings.cache_clear()
    os.unlink(TMP.name)

# --- disabled audit log records nothing ---
os.environ["DATATALKER_AUDIT_LOG_PATH"] = ""
get_settings.cache_clear()
try:
    from core.audit import record_audit

    record_audit({"event": "chat"})  # must be a no-op, not an error
finally:
    os.environ.pop("DATATALKER_AUDIT_LOG_PATH", None)
    get_settings.cache_clear()

print("audit: all assertions passed")
