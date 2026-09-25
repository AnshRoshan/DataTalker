# backend/test_governance.py
# Assert-based self-check for governance-lite: masking + validator rejection (EC-06/EC-05).
#   uv run --directory backend python test_governance.py
import json
import os
import tempfile

from agents.validator import ValidatorAgent
from core.governance import (
    filter_schema,
    load_governance,
    mask_rows,
    mask_value,
    prompt_note,
    sql_selects_masked_column,
)
from core.settings import get_settings

# --- masking strategies ---
assert mask_value("555-123-4567", "full") == "***"
assert mask_value("555-123-4567", "partial") == "********4567"  # keeps length, last 4 visible
assert mask_value("1234", "partial") == "***"      # short values fully masked
assert mask_value(None, "full") is None
h = mask_value("secret", "hash")
assert h == mask_value("secret", "hash") and len(h) == 12 and h != "secret"

# --- result masking (bare column names in rows) ---
gov = {"allowed_tables": None, "masked_columns": {"patients.ssn": "full", "patients.phone": "partial"}}
rows = [{"id": 1, "ssn": "111-22-3333", "phone": "555-123-4567", "name": "Ann"}]
masked = mask_rows(rows, gov)
assert masked[0]["ssn"] == "***"
assert masked[0]["phone"].endswith("4567") and set(masked[0]["phone"]) <= {"*", "4", "5", "6", "7"}
assert masked[0]["name"] == "Ann" and masked[0]["id"] == 1
assert rows[0]["ssn"] == "111-22-3333", "original rows are not mutated"

# --- schema filtering: allowed tables kept, masked columns still visible ---
schema = [
    {"table_name": "patients", "columns": [{"name": "ssn"}, {"name": "name"}]},
    {"table_name": "secrets", "columns": [{"name": "payload"}]},
]
gov2 = {"allowed_tables": {"patients"}, "masked_columns": {"patients.ssn": "full"}}
filtered, masked_set = filter_schema(schema, gov2)
assert [t["table_name"] for t in filtered] == ["patients"]
assert "patients.ssn" in masked_set
assert any(c["name"] == "ssn" for c in filtered[0]["columns"]), "masked columns stay visible by name"
assert filter_schema(schema, None) == (schema, set())

# --- SQL rejection of masked columns ---
masked = {"patients.ssn"}
assert sql_selects_masked_column("SELECT ssn FROM patients", masked)
assert sql_selects_masked_column("SELECT p.ssn FROM patients p", masked)
assert sql_selects_masked_column('SELECT "ssn" FROM patients', masked)
assert sql_selects_masked_column("SELECT name FROM patients WHERE ssn = '1'", masked)
assert sql_selects_masked_column("SELECT COUNT(ssn) FROM patients", masked)
# literals must not trigger it
assert sql_selects_masked_column("SELECT name FROM patients WHERE note = 'ssn'", masked) is None
assert sql_selects_masked_column("SELECT name FROM patients", masked) is None
assert sql_selects_masked_column("SELECT 1", set()) is None

# --- validator wiring: masked column blocks execution ---
ex = ValidatorAgent()
r = ex({"sql": "SELECT ssn FROM patients", "masked_columns": ["patients.ssn"]})
assert r["is_safe"] is False, r
assert "ssn" in r["validation_reason"]
assert r["sql"].startswith("--"), "blocked SQL is neutralized"
r = ex({"sql": "SELECT name FROM patients", "masked_columns": ["patients.ssn"]})
assert r["is_safe"] is True, r
r = ex({"sql": "SELECT name FROM patients", "masked_columns": None})
assert r["is_safe"] is True, "no governance -> unchanged behavior"

# --- prompt note ---
note = prompt_note({"patients.ssn", "patients.phone"})
assert "patients.ssn" in note and "patients.phone" in note
assert "MUST NOT" in note
assert prompt_note(set()) == ""

# --- file loading via settings ---
TMP = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
json.dump({"allowed_tables": ["patients"], "masked_columns": {"patients.phone": "hash"}}, TMP)
TMP.close()
os.environ["DATATALKER_GOVERNANCE_FILE"] = TMP.name.replace("\\", "/")
get_settings.cache_clear()
try:
    g = load_governance()
    assert g["allowed_tables"] == {"patients"}
    assert g["masked_columns"] == {"patients.phone": "hash"}
finally:
    os.environ.pop("DATATALKER_GOVERNANCE_FILE", None)
    get_settings.cache_clear()
    os.unlink(TMP.name)

# no config -> None (current behavior)
assert load_governance() is None

# unreadable file fails CLOSED (restrictions cannot be silently disabled)
os.environ["DATATALKER_GOVERNANCE_FILE"] = "no_such_governance_file.json"
get_settings.cache_clear()
try:
    g = load_governance()
    assert g == {"allowed_tables": [], "masked_columns": {}}, "unreadable file must fail closed"
finally:
    os.environ.pop("DATATALKER_GOVERNANCE_FILE", None)
    get_settings.cache_clear()

# --- bundled example file is valid ---
with open("governance.example.json", "r", encoding="utf-8") as f:
    example = json.load(f)
assert "allowed_tables" in example and "masked_columns" in example

print("governance: all assertions passed")
