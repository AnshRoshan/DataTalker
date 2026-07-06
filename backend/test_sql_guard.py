# backend/test_sql_guard.py
# Assert-based self-check for the SQL read-only guard (ponytail: no framework, run directly).
#   uv run --directory backend python test_sql_guard.py
from agents.validator import is_read_only_select


def ok(sql: str) -> bool:
    allowed, _ = is_read_only_select(sql)
    return allowed


# --- allowed: genuine read-only queries ---
assert ok("SELECT * FROM patients")
assert ok("select count(*) from patients where age > 30")
assert ok("WITH t AS (SELECT id FROM patients) SELECT * FROM t")
assert ok("SELECT * FROM audit WHERE operation = 'delete'")   # 'delete' is a literal value, not a verb
assert ok("SELECT name FROM patients;   ")                    # trailing semicolon + space is fine

# --- blocked: writes / DDL ---
assert not ok("DROP TABLE patients")
assert not ok("DELETE FROM patients")
assert not ok("INSERT INTO patients VALUES (1)")
assert not ok("UPDATE patients SET age = 0")
assert not ok("CREATE TABLE x (a int)")

# --- blocked: statement chaining (the multi-statement attack vector) ---
assert not ok("SELECT 1; DROP TABLE patients")

# --- blocked: SQLite ATTACH / PRAGMA ---
assert not ok("ATTACH DATABASE '/etc/passwd' AS pwn")
assert not ok("PRAGMA table_info(patients)")

# --- blocked: Postgres file read / COPY-to-program / data-modifying CTE ---
assert not ok("SELECT pg_read_file('/etc/passwd')")
assert not ok("COPY (SELECT 1) TO PROGRAM 'sh -c id'")
assert not ok("WITH t AS (DELETE FROM patients RETURNING id) SELECT * FROM t")

# --- blocked: junk / empty ---
assert not ok("")
assert not ok("   ")
assert not ok("-- just a comment")
assert not ok(None)  # type: ignore

print("sql_guard: all assertions passed")
