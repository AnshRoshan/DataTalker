# backend/test_executor.py
# Assert-based self-check for DBExecutorAgent read-only + single-statement enforcement.
#   uv run --directory backend python test_executor.py
import os
import tempfile
from agents.db_executor import DBExecutorAgent

HOSPITAL = "sqlite:///" + os.path.abspath("hospital.db").replace("\\", "/")
ex = DBExecutorAgent()


def run(db_uri: str, sql: str):
    return ex({"db_uri": db_uri, "db_dialect": "sqlite", "sql": sql})


# valid read -> flat list of dicts (no multi-statement wrapper shape)
r = run(HOSPITAL, "SELECT name FROM sqlite_master WHERE type='table'")
assert r["sql_executed"] is True, r
assert isinstance(r["results"], list) and all(isinstance(x, dict) for x in r["results"]), r

# multiple statements -> rejected outright
r = run(HOSPITAL, "SELECT 1; SELECT 2")
assert r["sql_executed"] is False and "single" in (r.get("error") or "").lower(), r

# a write must be blocked by PRAGMA query_only (validator bypassed here on purpose).
# Use a throwaway db so a PRAGMA regression can never mutate the hospital.db fixture.
tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp.close()
try:
    r = run("sqlite:///" + tmp.name.replace("\\", "/"), "CREATE TABLE _pwn (a INTEGER)")
    assert r["sql_executed"] is False, r
finally:
    os.unlink(tmp.name)

# a failing query returns a GENERIC error — the SQL / table names must not leak to the user
r = run(HOSPITAL, "SELECT * FROM no_such_table_xyz")
assert r["sql_executed"] is False, r
assert "no_such_table_xyz" not in (r.get("error") or ""), r

print("db_executor: all assertions passed")
