# backend/test_dialects.py
# Assert-based self-check for the dialect registry + MySQL acceptance (EC-03).
#   uv run --directory backend python test_dialects.py
from core.dialects import DIALECT_PROMPTS, get_dialect_prompt, supported_dialects

# registry covers sqlite, postgresql, mysql
assert set(supported_dialects()) == {"sqlite", "postgresql", "mysql"}
for d, (ctx, practices) in DIALECT_PROMPTS.items():
    assert ctx and practices, f"dialect {d} must provide prompt snippets"

# mysql snippet teaches MySQL-specific syntax
mctx, mpractices = get_dialect_prompt("mysql")
assert "MySQL databases." in mctx
assert "backticks" in mpractices
assert "LIMIT" in mpractices
assert "DATE_FORMAT" in mpractices

# unknown dialect falls back to the generic standard-SQL snippet (universal support)
ctx, practices = get_dialect_prompt("oracle")
assert "oracle SQL database" in ctx
assert "standard SQL (ANSI)" in practices
assert "LIMIT" in practices

# --- connection-string parsing accepts mysql:// and mysql+pymysql:// ---
from core.database import is_database_connection_url, parse_connection_string

for uri in (
    "mysql://user:pass@host:3306/dbname",
    "mysql+pymysql://user:pass@host:3306/dbname",
):
    parsed_uri, dialect, path = parse_connection_string(uri)
    assert dialect == "mysql" and path is None and parsed_uri == uri

assert is_database_connection_url("mysql://user@host/db")
assert is_database_connection_url("mysql+pymysql://user@host/db")
# existing dialects unchanged
assert parse_connection_string("postgresql://u:p@h:5432/db")[1] == "postgresql"
assert parse_connection_string("postgres://u:p@h:5432/db")[1] == "postgresql"
assert is_database_connection_url("postgresql://u:p@h/db")
assert not is_database_connection_url("https://example.com/db.sqlite")

# dialect validation (settings-driven) includes mysql
from core.database import validate_database_dialect

assert validate_database_dialect("mysql") == "mysql"
assert validate_database_dialect("sqlite") == "sqlite"

# unsupported dialect still rejected
from fastapi import HTTPException

try:
    validate_database_dialect("oracle")
    assert False, "oracle must be rejected"
except HTTPException as e:
    assert e.status_code == 400

# --- executor issues a MySQL session timeout (unit via SQL construction) ---
from core.settings import get_settings

expected = f"SET SESSION MAX_EXECUTION_TIME={get_settings().statement_timeout_seconds * 1000}"
assert "MAX_EXECUTION_TIME" in expected

print("dialects: all assertions passed")
