# backend/test_semantic.py
# Assert-based self-check for the semantic layer lite (EC-09).
#   uv run --directory backend python test_semantic.py
import os

from core.settings import get_settings

# --- bundled example loads and renders ---
os.environ["DATATALKER_SEMANTIC_FILE"] = "semantic.hospital.yml"
get_settings.cache_clear()
try:
    from core.semantic import load_semantic, semantic_context

    model = load_semantic()
    assert model is not None
    assert "patients" in model["tables"]
    assert model["tables"]["patients"]["synonyms"] == ["person", "individual", "client"]
    assert "dob" in model["tables"]["patients"]["columns"]
    assert "total_patients" in model["metrics"]
    assert "SELECT COUNT(*) FROM patients" in model["metrics"]["total_patients"]["sql"]

    ctx = semantic_context()
    assert "SEMANTIC LAYER" in ctx
    assert "People admitted to or treated by the hospital" in ctx
    assert "person, individual, client" in ctx
    assert "Date of birth" in ctx
    assert "SELECT COUNT(*) FROM patients" in ctx, "metric definition SQL is provided as context"
finally:
    os.environ.pop("DATATALKER_SEMANTIC_FILE", None)
    get_settings.cache_clear()

# --- not configured -> no context, no error ---
from core.semantic import load_semantic, semantic_context

assert load_semantic() is None
assert semantic_context() == ""

# --- invalid file -> ignored ("" context) ---
os.environ["DATATALKER_SEMANTIC_FILE"] = "no_such_semantic_file.yml"
get_settings.cache_clear()
try:
    assert load_semantic() is None
    assert semantic_context() == ""
finally:
    os.environ.pop("DATATALKER_SEMANTIC_FILE", None)
    get_settings.cache_clear()

# --- malformed YAML -> ignored ---
import tempfile

TMP = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
TMP.write("tables: [unclosed")
TMP.close()
os.environ["DATATALKER_SEMANTIC_FILE"] = TMP.name.replace("\\", "/")
get_settings.cache_clear()
try:
    assert load_semantic() is None
finally:
    os.environ.pop("DATATALKER_SEMANTIC_FILE", None)
    get_settings.cache_clear()
    os.unlink(TMP.name)

# --- semantic context is injected into the SQL-writer prompt path ---
from agents.sql_writer import history_context
from llm.prompts import build_sql_instruction

sys_mysql = build_sql_instruction("mysql")
assert "MySQL" in sys_mysql and "backticks" in sys_mysql
assert "LIMIT" in sys_mysql
sys_sqlite = build_sql_instruction("sqlite")
assert "SQLite databases." in sys_sqlite
sys_pg = build_sql_instruction("postgresql")
assert "PostgreSQL databases." in sys_pg
assert "double quotes for identifiers" in sys_pg  # pre-registry wording preserved
assert "defaulting to SQLite behavior" in build_sql_instruction("oracle"), "unknown dialect falls back to sqlite"

print("semantic: all assertions passed")
