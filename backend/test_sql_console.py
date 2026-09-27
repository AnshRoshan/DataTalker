# backend/test_sql_console.py
# Assert-based self-check for the SQL console: the same guard as the chat path.
#   uv run --directory backend python test_sql_console.py
import os
import tempfile

os.environ["DATATALKER_DATA_DIR"] = (tempfile.mkdtemp(prefix="dt-sql-test-") + "/data").replace("\\", "/")
os.environ["DATATALKER_AUDIT_LOG_PATH"] = ""

from fastapi import HTTPException  # noqa: E402
from core.settings import get_settings  # noqa: E402

get_settings.cache_clear()

from services.sql_service import SqlConsoleService  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DB_URI = "sqlite:///" + os.path.join(HERE, "hospital.db").replace("\\", "/")


def run(sql):
    return SqlConsoleService.run(sql, DB_URI, "sqlite")


# --- reads execute ---
ok = run("SELECT patient_id, name FROM patients ORDER BY patient_id LIMIT 3")
assert ok["sql_executed"] is True and ok["validator_rejected"] is False
assert ok["row_count"] == 3 and ok["results"][0]["name"] == "John Doe"
assert isinstance(ok["latency_ms"], int) and ok["reason"] is None

with_join = run(
    "SELECT d.name AS department, COUNT(a.appointment_id) AS n "
    "FROM appointments a JOIN doctors doc ON doc.doctor_id = a.doctor_id "
    "JOIN departments d ON d.department_id = doc.department_id GROUP BY 1 ORDER BY 2 DESC"
)
assert with_join["sql_executed"] and with_join["row_count"] == 5

# --- and the guard still says no ---
for attempt, why in [
    ("DROP TABLE patients", "read-only"),
    ("DELETE FROM patients", "read-only"),
    ("INSERT INTO patients (name) VALUES ('x')", "read-only"),
    ("SELECT 1; DELETE FROM patients", "single statement"),
    ("SELECT pg_read_file('/etc/passwd')", "disallowed function"),
    ("PRAGMA table_info(patients)", "read-only"),
    ("", "400"),
]:
    if attempt == "":
        try:
            run(attempt)
            raise AssertionError("empty statement must 400")
        except HTTPException as e:
            assert e.status_code == 400
        continue
    result = run(attempt)
    assert result["validator_rejected"] is True, f"{attempt!r} should be blocked"
    assert result["sql_executed"] is False and result["results"] == []
    assert why in result["reason"].lower(), f"{attempt!r}: {result['reason']}"

# --- nothing was written: the fixture is untouched, so a read count still holds ---
assert run("SELECT COUNT(*) AS n FROM patients")["results"][0]["n"] == 5

# --- a bad statement fails as a failure, not as a policy block ---
bad = run("SELECT * FROM table_that_does_not_exist")
assert bad["sql_executed"] is False and bad["validator_rejected"] is False
assert bad["reason"] == "The query could not be executed.", bad["reason"]

# --- the route ---
from fastapi.testclient import TestClient  # noqa: E402
import main as app_module  # noqa: E402

os.environ["DATATALKER_API_KEY"] = "k"
get_settings.cache_clear()
app_module.fastapi_app = app_module.create_app()
client = TestClient(app_module.fastapi_app)
H = {"Authorization": "Bearer k"}
db_path = os.path.join(HERE, "hospital.db").replace("\\", "/")

r = client.post("/sql/", data={"sql": "SELECT 1 AS one", "db_path": db_path}, headers=H)
assert r.status_code == 200 and r.json()["results"] == [{"one": 1}], r.text

blocked = client.post("/sql/", data={"sql": "DROP TABLE patients", "db_path": db_path}, headers=H)
assert blocked.status_code == 200 and blocked.json()["validator_rejected"] is True
assert "read-only" in blocked.json()["reason"]

assert client.post("/sql/", data={"sql": "SELECT 1", "db_path": db_path}).status_code == 401
assert client.post("/sql/", data={"sql": "   ", "db_path": db_path}, headers=H).status_code == 400
# path confinement still applies to the console
assert client.post("/sql/", data={"sql": "SELECT 1", "db_path": "C:/Windows/win.ini"}, headers=H).status_code == 403

print("sql_console: all assertions passed")
