# backend/test_conversations.py
# Assert-based self-check for the conversations store + its routes.
#   uv run --directory backend python test_conversations.py
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="dt-conv-test-")
os.environ["DATATALKER_DATA_DIR"] = os.path.join(_TMP, "data").replace("\\", "/")
os.environ["DATATALKER_AUDIT_LOG_PATH"] = ""

from core.settings import get_settings  # noqa: E402

get_settings.cache_clear()

from core import conversations as conv  # noqa: E402

ALICE, BOB = "alice-sub", "bob-sub"

MSG = {
    "id": "m1",
    "question": "How many patients?",
    "answer": "There are 5.",
    "sql": "SELECT COUNT(*) FROM patients",
    "results": [{"n": 5}],
    "follow_up_questions": ["By department?"],
    "latency_ms": 120,
    "sql_executed": "SELECT COUNT(*) FROM patients",
}

# --- create then list ---
header = conv.save_conversation(None, [MSG], owner=ALICE, source="hospital.db")
assert header["title"] == "How many patients?" and header["message_count"] == 1
assert header["source"] == "hospital.db"
cid = header["id"]

listed = conv.list_conversations(ALICE)
assert [c["id"] for c in listed] == [cid]
assert "messages" not in listed[0], "the list must not carry message bodies"

# --- ownership: another user cannot see, open, or delete it ---
assert conv.list_conversations(BOB) == []
assert conv.get_conversation(cid, BOB) is None, "cross-owner read must look like a missing id"
assert conv.delete_conversation(cid, BOB) is False
assert conv.get_conversation(cid, ALICE)["messages"][0]["answer"] == "There are 5."

# --- update keeps the original created_at ---
first_created = conv.get_conversation(cid, ALICE)["created_at"]
updated = conv.save_conversation(cid, [MSG, {**MSG, "id": "m2", "question": "And doctors?"}], owner=ALICE)
assert updated["message_count"] == 2
again = conv.get_conversation(cid, ALICE)
assert again["created_at"] == first_created and again["updated_at"] >= first_created
# the title stays the first question, so the sidebar does not rename itself mid-thread
assert again["title"] == "How many patients?"

# --- sanitising: junk in, bounded record out ---
junk = conv.sanitize_messages([
    MSG,
    "not-a-dict",
    {"question": "x" * 50_000, "results": {"not": "a list"}},
    {"question": "bad results", "results": "a string"},
    None,
])
assert all(isinstance(m, dict) for m in junk)
assert len(junk[1]["question"]) == 20_000
assert junk[1]["results"] == [{"not": "a list"}], "a single-object result is still one row"
assert junk[2]["results"] == []

wide = conv.sanitize_messages([{"question": "q", "results": [{"i": i} for i in range(5000)]}])
assert len(wide[0]["results"]) == conv._MAX_ROWS_KEPT, "rows must be capped before storing"

many = conv.sanitize_messages([{"question": f"q{i}"} for i in range(500)])
assert len(many) == conv._MAX_MESSAGES and many[-1]["question"] == "q499"

assert conv.delete_conversation(cid, ALICE) is True
assert conv.delete_conversation(cid, ALICE) is False
assert conv.get_conversation(cid, ALICE) is None

# --- the cap trims this owner's oldest, and only theirs ---
other = conv.save_conversation(None, [{"question": "bob's thread"}], owner=BOB)["id"]
keep = None
for i in range(conv._MAX_CONVERSATIONS + 25):
    keep = conv.save_conversation(None, [{"question": f"thread {i}"}], owner=ALICE)["id"]
final = conv.list_conversations(ALICE)
assert len(final) == conv._MAX_CONVERSATIONS, len(final)
assert any(c["id"] == keep for c in final), "the live thread must survive the trim"
assert final[0]["title"] == f"thread {conv._MAX_CONVERSATIONS + 24}"
assert conv.list_conversations(BOB)[0]["id"] == other, "trimming one owner cannot evict another"

# --- routes: auth-gated, owner-scoped, SPA-safe ---
from fastapi.testclient import TestClient  # noqa: E402
import main as app_module  # noqa: E402

os.environ["DATATALKER_API_KEY"] = "k"
os.environ["DATATALKER_REQUIRE_LOGIN"] = "false"
get_settings.cache_clear()
app_module.fastapi_app = app_module.create_app()
client = TestClient(app_module.fastapi_app)

assert client.post("/conversations/", json={"messages": [MSG]}).status_code == 401
headers = {"Authorization": "Bearer k"}

body = client.post("/conversations/", json={"messages": [MSG]}, headers=headers).json()
thread = client.get(f"/conversations/{body['id']}", headers=headers).json()
assert thread["messages"][0]["question"] == MSG["question"]
assert client.get("/conversations/nope", headers=headers).status_code == 404
# the list is the caller's own — the 200 stored under ALICE above must not appear
assert client.get("/conversations/", headers=headers).json()["total"] == 1
assert client.delete(f"/conversations/{body['id']}", headers=headers).status_code == 200
assert client.delete(f"/conversations/{body['id']}", headers=headers).status_code == 404
assert client.get("/conversations/", headers=headers).json()["total"] == 0

# a client that sends nonsense gets a bounded record, not a crash
weird = client.post("/conversations/", json={"messages": [{"question": 1}, {"nope": 2}, 5]}, headers=headers)
assert weird.status_code == 200 and weird.json()["message_count"] == 2

print("conversations: all assertions passed")
