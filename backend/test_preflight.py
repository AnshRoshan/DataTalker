# backend/test_preflight.py
# Assert-based self-check for core/preflight.py: sqlite fixture fields and
# structured error shapes (never raw tracebacks, never the URI).
#   uv run --directory backend python test_preflight.py
import pathlib

from core.preflight import check_connection

BACKEND = pathlib.Path(__file__).resolve().parent
HOSPITAL = BACKEND / "hospital.db"

# --- sqlite fixture: full field set ---
result = check_connection(f"sqlite:///{HOSPITAL}")
assert result["ok"] is True, result
assert result["dialect"] == "sqlite"
assert result["driver"]
assert result["server_version"], result  # sqlite_version() probe
assert isinstance(result["server_version"], str) and result["server_version"][0].isdigit()
assert result["table_count"] == 7, result["table_count"]
assert len(result["sample_tables"]) == 7 and "patients" in result["sample_tables"]
assert result["warnings"], "read-only caveat warning must always be present"
assert all(isinstance(w, str) for w in result["warnings"])

# the URI itself must never leak into the result (SEC-05)
serialized = str(result)
assert "hospital.db" not in serialized and "sqlite:///" not in serialized

# --- bad URI: structured error shape, no traceback text ---
bad = check_connection("totally_bogus_connection_string")
assert bad["ok"] is False
assert isinstance(bad["error"], str) and bad["error"]
assert "Traceback" not in str(bad)

unreachable = check_connection("sqlite:///<does-not-exist>/nope.db")
assert unreachable["ok"] is False and unreachable["error"]

empty = check_connection("")
assert empty["ok"] is False and empty["error"]

# --- hard timeout path ---
timed_out = check_connection("sqlite:///<does-not-exist>/nope.db", timeout_seconds=0)
assert timed_out["ok"] is False and "timed out" in timed_out["error"], timed_out

print("preflight: all assertions passed")
