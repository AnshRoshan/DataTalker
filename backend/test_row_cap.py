# backend/test_row_cap.py
# Assert-based self-check for the hard server-side row cap (EC-10).
#   uv run --directory backend python test_row_cap.py
import os
import sqlite3
import tempfile

from agents.db_executor import DBExecutorAgent
from core.engines import dispose_all
from core.settings import get_settings

TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TMP.close()
DB = "sqlite:///" + TMP.name.replace("\\", "/")

con = sqlite3.connect(TMP.name)
con.execute("CREATE TABLE nums (n INTEGER)")
con.executemany("INSERT INTO nums VALUES (?)", [(i,) for i in range(20)])
con.commit()
con.close()

# Default cap (500): all 20 rows come back, no truncation.
ex = DBExecutorAgent()
r = ex({"db_uri": DB, "db_dialect": "sqlite", "sql": "SELECT n FROM nums"})
assert r["sql_executed"] is True, r
assert len(r["results"]) == 20, len(r["results"])
assert r.get("results_truncated") is False, r

# Tightened cap: exactly max_rows rows, truncated flag set, cap noted.
os.environ["DATATALKER_MAX_QUERY_ROWS"] = "7"
get_settings.cache_clear()
try:
    r = ex({"db_uri": DB, "db_dialect": "sqlite", "sql": "SELECT n FROM nums"})
    assert r["sql_executed"] is True, r
    assert len(r["results"]) == 7, len(r["results"])
    assert r["results_truncated"] is True, r
    assert r["row_cap"] == 7, r
    assert [row["n"] for row in r["results"]] == list(range(7)), "cap keeps first rows in order"
finally:
    os.environ.pop("DATATALKER_MAX_QUERY_ROWS", None)
    get_settings.cache_clear()
    dispose_all()
    os.unlink(TMP.name)

print("row_cap: all assertions passed")
