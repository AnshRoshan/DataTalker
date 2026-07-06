# backend/test_schema_cache.py
# Assert-based self-check for schema-cache freshness (CORR-1: Postgres entries must expire).
#   uv run --directory backend python test_schema_cache.py
import time
from agents.schema import _is_cache_fresh

TTL = 3600

# SQLite (modification time known): fresh only when the stored mod_time matches.
assert _is_cache_fresh({"mod_time": 100.0}, 100.0, TTL) is True
assert _is_cache_fresh({"mod_time": 100.0}, 200.0, TTL) is False
assert _is_cache_fresh({}, 100.0, TTL) is False           # no stored mod_time -> stale

# Postgres / non-file (mod_time is None): fresh only within the TTL window.
now = time.time()
assert _is_cache_fresh({"saved_at": now}, None, TTL) is True
assert _is_cache_fresh({"saved_at": now - (TTL + 100)}, None, TTL) is False
assert _is_cache_fresh({}, None, TTL) is False            # CORR-1: no timestamp -> stale, not "valid forever"

print("schema_cache: all assertions passed")
