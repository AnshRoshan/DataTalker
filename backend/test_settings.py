# backend/test_settings.py
# Assert-based self-check for core/settings.py (EC-07/PR-07).
#   uv run --directory backend python test_settings.py
import os

from core.settings import Settings, get_settings

# --- defaults (behavior unchanged vs the old core/config.py constants) ---
s = get_settings()
assert s.api_title == "Talk to DB API"
assert s.api_version == "1.0.0"
assert s.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
assert s.cache_ttl_seconds == 3600
assert s.allowed_extensions_list == [".db", ".sqlite", ".sqlite3"]
assert s.max_upload_mb == 100 and s.max_file_size_bytes == 100 * 1024 * 1024
assert s.max_query_rows == 500
assert s.statement_timeout_seconds == 30
assert s.rate_limit_requests == 30 and s.rate_limit_window_seconds == 60
assert s.supported_dialects == ["sqlite", "postgresql", "mysql"]
assert s.audit_log_path == "logs/audit.log"
assert s.audit_log_file.is_absolute(), "relative audit path resolves under backend/"
assert s.governance_file == "" and s.semantic_file == ""
# get_settings is cached -> same object
assert get_settings() is s

# --- env override via DATATALKER_ prefix ---
os.environ["DATATALKER_MAX_QUERY_ROWS"] = "42"
os.environ["DATATALKER_RATE_LIMIT_REQUESTS"] = "0"
try:
    s2 = Settings()
    assert s2.max_query_rows == 42
    assert s2.rate_limit_requests == 0  # 0 disables the limiter
finally:
    os.environ.pop("DATALKER_MAX_QUERY_ROWS", None)
    os.environ.pop("DATATALKER_MAX_QUERY_ROWS", None)
    os.environ.pop("DATATALKER_RATE_LIMIT_REQUESTS", None)

# --- CORS_ALLOWED_ORIGINS backwards-compat alias ---
os.environ["CORS_ALLOWED_ORIGINS"] = "http://a.dev, http://b.dev"
try:
    s3 = Settings()
    assert s3.cors_origin_list == ["http://a.dev", "http://b.dev"]
finally:
    os.environ.pop("CORS_ALLOWED_ORIGINS", None)

# --- DATATALKER_DB_DIR confinement dir ---
os.environ["DATATALKER_DB_DIR"] = os.getcwd()
try:
    s4 = Settings()
    assert s4.db_dir == os.getcwd()
finally:
    os.environ.pop("DATATALKER_DB_DIR", None)

# --- disabled audit log ("") ---
os.environ["DATATALKER_AUDIT_LOG_PATH"] = ""
try:
    s5 = Settings()
    assert not s5.audit_log_file.exists() or s5.audit_log_path == ""
finally:
    os.environ.pop("DATATALKER_AUDIT_LOG_PATH", None)

print("settings: all assertions passed")
