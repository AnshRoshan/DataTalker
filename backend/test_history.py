# backend/test_history.py
# Assert-based self-check for chat-history context (multi-turn follow-ups).
#   uv run --directory backend python test_history.py
import os

os.environ.setdefault("DATATALKER_API_KEY", "k")
os.environ.setdefault("GEMINI_API_KEY", "dummy")

from agents.sql_writer import history_context

# --- rendering ---
ctx = history_context([
    {"question": "How many patients are there?", "answer": "There are 5 patients.", "sql": "SELECT COUNT(*) FROM patients"},
    {"question": "Show me their names", "answer": "Here are the names.", "sql": "SELECT name FROM patients"},
])
assert "PREVIOUS TURNS" in ctx
assert "How many patients are there?" in ctx
assert "SELECT COUNT(*) FROM patients" in ctx
assert "Show me their names" in ctx
assert "most recent last" in ctx

# turn without SQL is fine
ctx = history_context([{"question": "hi", "answer": "hello"}])
assert "hi" in ctx and "SQL used" not in ctx

# empty / malformed inputs -> no context
assert history_context(None) == ""
assert history_context([]) == ""
assert history_context("not-a-list") == ""
assert history_context([42, {"question": "q", "answer": "a"}]) != "", "non-dict turns are skipped, dict turns kept"

# --- endpoint accepts and caps the history form field ---
import main
from fastapi.testclient import TestClient

c = TestClient(main.fastapi_app, headers={"Authorization": "Bearer k"})

bad = c.post("/chat/", data={"question": "q", "db_path": os.path.abspath("hospital.db"), "history": "{not json"})
assert bad.status_code == 400, bad.status_code
assert "history" in bad.json()["detail"]

# valid history with a missing db still 400s (input handling), not a crash
ok_shape = c.post("/chat/", data={"question": "q", "history": "[]"})
assert ok_shape.status_code in (400, 404, 403), ok_shape.status_code

# QueryService caps the number of threaded turns
from services.query_service import _sanitize_history

turns = [{"question": f"q{i}", "answer": "a", "sql": "s"} for i in range(8)]
sanitized = _sanitize_history(turns)
assert len(sanitized) == 5, "at most the last 5 entries are kept"
assert sanitized[-1]["question"] == "q7", "most recent last"
assert sanitized[0]["question"] == "q3"

print("history: all assertions passed")
