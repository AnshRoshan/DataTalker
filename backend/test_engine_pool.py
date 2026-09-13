# backend/test_engine_pool.py
# Assert-based self-check for the process-global engine pool (PR-03).
#   uv run --directory backend python test_engine_pool.py
import os
import sqlite3
import tempfile

import sqlalchemy
from sqlalchemy import exc as sqlalchemy_exc

from core.engines import dispose_all, get_engine

TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TMP.close()
URI = "sqlite:///" + TMP.name.replace("\\", "/")
URI2 = "sqlite:///" + (TMP.name + ".2").replace("\\", "/")

con = sqlite3.connect(TMP.name)
con.execute("CREATE TABLE t (a INTEGER)")
con.commit()
con.close()

try:
    # --- same URI -> same engine object (reuse, not per-call creation) ---
    e1 = get_engine(URI)
    e2 = get_engine(URI)
    assert e1 is e2, "two calls for the same db_uri must return the same engine"

    # different URI -> different engine
    e3 = get_engine(URI2)
    assert e3 is not e1
    assert get_engine(URI) is e1, "still cached"

    # engines are real, working SQLAlchemy engines
    assert isinstance(e1, sqlalchemy.engine.Engine)
    with e1.connect() as c:
        assert c.execute(sqlalchemy.text("SELECT COUNT(*) FROM t")).scalar() == 0

    # --- sqlite connections are pinned read-only via the connect listener ---
    with e1.connect() as c:
        assert c.exec_driver_sql("PRAGMA query_only").scalar() == 1
        try:
            c.exec_driver_sql("CREATE TABLE _pwn (a INTEGER)")
            assert False, "write must be blocked by PRAGMA query_only"
        except sqlalchemy_exc.OperationalError:
            pass

    # --- dispose_all clears the cache (next call creates a fresh engine) ---
    dispose_all()
    e4 = get_engine(URI)
    assert e4 is not e1, "after dispose_all a new engine is built"
finally:
    dispose_all()
    os.unlink(TMP.name)
    if os.path.exists(TMP.name + ".2"):
        os.unlink(TMP.name + ".2")

print("engine_pool: all assertions passed")
