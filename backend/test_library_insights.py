# backend/test_library_insights.py
# Assert-based self-check for saved queries, the insights aggregation and the
# first-run demo registration.
#   uv run --directory backend python test_library_insights.py
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

_TMP = tempfile.mkdtemp(prefix="dt-lib-test-")
os.environ["DATATALKER_DATA_DIR"] = (_TMP + "/data").replace("\\", "/")
# Absolute on purpose: a relative audit path resolves against the backend directory,
# and a test must not append its synthetic events into a real deployment's log.
os.environ["DATATALKER_AUDIT_LOG_PATH"] = (_TMP + "/logs/audit.log").replace("\\", "/")
os.environ["DATATALKER_API_KEY"] = "k"

from core.settings import get_settings  # noqa: E402

get_settings.cache_clear()

from core import saved_queries as sq  # noqa: E402
from core import stats  # noqa: E402

# --------------------------------------------------------------- saved queries
made = sq.save_query(None, "", "SELECT d.name\nFROM departments d", "sqlite", "alice", source="hospital")
assert made["name"] == "SELECT d.name", "an unnamed query is titled by its first line"
assert made["sql"].startswith("SELECT d.name") and made["run_count"] == 0
qid = made["id"]

assert sq.list_saved("alice") and sq.list_saved("bob") == [], "one user's library is not another's"
assert sq.get_saved(qid, "bob") is None

try:
    sq.save_query(None, "", "   ", "sqlite", "alice")
    raise AssertionError("blank statement must be refused")
except ValueError as e:
    assert "statement" in str(e).lower()

try:
    sq.save_query(qid, "renamed", "SELECT 2", "sqlite", "bob")
    raise AssertionError("another owner must not update this row")
except KeyError:
    pass

renamed = sq.save_query(qid, "Departments list", "SELECT 2", "sqlite", "alice")
assert renamed["name"] == "Departments list" and renamed["created_at"] == made["created_at"]

ran = sq.mark_run(qid, "alice")
assert ran["run_count"] == 1 and ran["last_run_at"]
assert sq.mark_run(qid, "bob") is None

assert sq.delete_saved(qid, "bob") is False and sq.delete_saved(qid, "alice") is True

for i in range(sq._MAX_PER_OWNER + 10):
    sq.save_query(None, f"q{i}", f"SELECT {i}", "sqlite", "carol")
assert len(sq.list_saved("carol")) == sq._MAX_PER_OWNER
assert sq.list_saved("carol")[0]["name"] == f"q{sq._MAX_PER_OWNER + 9}"

# ------------------------------------------------------------------- insights
today = datetime.now(timezone.utc)
lines = []
for i in range(4):
    lines.append({
        "timestamp": (today - timedelta(days=i)).isoformat(),
        "event": "chat", "request_id": f"r{i}", "dialect": "sqlite",
        "question": f"question {i}", "sql": "SELECT 1", "executed": True,
        "row_count": 10, "truncated": i == 0, "validator_rejected": False, "latency_ms": 100 + i * 100,
    })
lines.append({  # a blocked statement
    "timestamp": today.isoformat(), "event": "chat", "dialect": "sqlite", "question": "drop it",
    "sql": "", "executed": False, "row_count": 0, "truncated": False,
    "validator_rejected": True, "latency_ms": 5,
})
lines.append({"timestamp": today.isoformat(), "event": "schema_extract", "dialect": "sqlite", "table_count": 7})
lines.append({"timestamp": today.isoformat(), "event": "sign_in", "email": "a@b.c"})

audit = get_settings().audit_log_file
audit.parent.mkdir(parents=True, exist_ok=True)
with open(audit, "w", encoding="utf-8") as f:
    f.write("\n".join(json.dumps(x) for x in lines) + "\n")
    f.write("{ torn line without closing brace\n")  # a crash-truncated tail

summary = stats.summarize(window_days=14)
assert summary["questions"] == 5 and summary["blocked"] == 1
assert summary["executed"] == 4 and summary["truncated"] == 1
assert summary["rows_returned"] == 40
assert summary["avg_latency_ms"] == round((100 + 200 + 300 + 400 + 5) / 5)
assert summary["p95_latency_ms"] == 400 and summary["slowest_ms"] == 400
assert summary["schema_reads"] == 1 and summary["sign_ins"] == 1
assert len(summary["activity"]) == 14, "the x-axis must not stretch with usage"
assert summary["activity"][-1]["questions"] >= 1
assert summary["dialects"] == {"sqlite": 5} and summary["audit_enabled"] is True
assert stats.summarize(window_days=2)["questions_in_window"] <= summary["questions_in_window"]

history = stats.recent_history(limit=3)
assert len(history) == 3 and history[0]["question"] == "drop it", "newest first"
assert history[0]["validator_rejected"] is True and history[1]["executed"] is True

# a missing audit file is an empty dashboard, not an error
os.remove(audit)
assert stats.summarize()["questions"] == 0 and stats.recent_history() == []

# ---------------------------------------------------------------- demo bootstrap
from core import bootstrap  # noqa: E402
from core.connections import list_connections  # noqa: E402

assert list_connections() == []
added = bootstrap.register_demo_sources()
assert any("hospital" in name.lower() for name in added), added
assert len(list_connections()) == len(added)

# idempotent: a second boot must not duplicate, and a real connection disables it
assert bootstrap.register_demo_sources() == []
sq_path = get_settings().data_dir
os.environ["DATATALKER_BOOTSTRAP_DEMO"] = "false"
get_settings.cache_clear()
assert bootstrap.register_demo_sources() == []
del os.environ["DATATALKER_BOOTSTRAP_DEMO"]
get_settings.cache_clear()

# ---------------------------------------------------------------------- routes
from fastapi.testclient import TestClient  # noqa: E402
import main as app_module  # noqa: E402

get_settings.cache_clear()
app_module.fastapi_app = app_module.create_app()
client = TestClient(app_module.fastapi_app)
H = {"Authorization": "Bearer k"}

assert client.get("/queries/").status_code == 401
assert client.get("/stats", headers=H).json()["questions"] == 0  # audit file was removed

saved = client.post("/queries/", json={"name": "Count", "sql": "SELECT COUNT(*) AS n FROM patients"}, headers=H)
assert saved.status_code == 201, saved.text
new_id = saved.json()["id"]
assert client.get("/queries/", headers=H).json()["total"] == 1
assert client.post(f"/queries/{new_id}/run", headers=H).json()["run_count"] == 1
assert client.post("/queries/nope/run", headers=H).status_code == 404
assert client.post("/queries/", json={"name": "x", "sql": "  "}, headers=H).status_code == 400
assert client.delete(f"/queries/{new_id}", headers=H).status_code == 200
assert client.delete(f"/queries/{new_id}", headers=H).status_code == 404

with open(audit, "w", encoding="utf-8") as f:
    f.write(json.dumps({"timestamp": today.isoformat(), "event": "chat", "question": "hi",
                        "executed": True, "row_count": 2, "validator_rejected": False, "latency_ms": 42}) + "\n")
get_settings.cache_clear()
stats_view = client.get("/stats", params={"window_days": 30}, headers=H).json()
assert stats_view["window_days"] == 30 and stats_view["questions"] == 1
assert client.get("/history", headers=H).json()["history"][0]["question"] == "hi"

print("library_insights: all assertions passed")
