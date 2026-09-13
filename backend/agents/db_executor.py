# agents/db_executor.py
import logging
from typing import Any, Dict

import sqlalchemy
from sqlalchemy import exc as sqlalchemy_exc

from core.engines import get_engine
from core.settings import get_settings

logger = logging.getLogger(__name__)


class DBExecutorAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single validated read-only SQL statement and return its rows."""
        logger.debug(
            "state keys: %s",
            sorted(k for k in state if k not in ("detailed_schema", "schema_description", "results")),
        )

        sql = state.get("sql")
        db_uri = state.get("db_uri")
        db_dialect: str = state.get("db_dialect", "sqlite")

        if not db_uri:
            return {**state, "error": "Database URI not provided for execution.", "sql_executed": False}
        if not sql:
            return {**state, "error": "SQL query not found for execution.", "sql_executed": False}

        # Defense-in-depth: the validator already enforces a single read-only statement,
        # but never execute more than one here regardless (blocks statement chaining).
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        if len(statements) != 1:
            return {**state, "error": "Only a single read-only statement may be executed.", "sql_executed": False}
        statement = statements[0]

        settings = get_settings()
        max_rows = settings.max_query_rows

        try:
            # ponytail: pooled engine (PR-03) — created once per db_uri, disposed via
            # TTL/LRU in core.engines, never per request.
            engine = get_engine(db_uri)
            with engine.connect() as connection:
                if db_dialect == "postgresql":
                    # Transaction-scoped timeout: expires when the pooled connection's
                    # transaction ends, so it never leaks across requests (SEC-08).
                    connection.exec_driver_sql(
                        f"SET LOCAL statement_timeout = '{settings.statement_timeout_seconds}s'"
                    )
                elif db_dialect == "mysql":
                    # MySQL's max_execution_time is session-level and SELECT-only; set it
                    # for the whole session (matches the intent — every query bounded).
                    connection.exec_driver_sql(
                        f"SET SESSION MAX_EXECUTION_TIME={settings.statement_timeout_seconds * 1000}"
                    )
                # SQLite is exempt: it has no server-side statement timeout, but it is
                # file-local, pinned read-only (PRAGMA query_only via core.engines), and
                # queries there are bounded by the row cap below.
                result_proxy = connection.execute(sqlalchemy.text(statement))
                if result_proxy.returns_rows:
                    # Hard server-side row cap (EC-10): fetch one extra row to detect
                    # truncation without pulling the whole result set into memory.
                    rows = result_proxy.mappings().fetchmany(max_rows + 1)
                    truncated = len(rows) > max_rows
                    results = [dict(row) for row in rows[:max_rows]]
                else:
                    truncated = False
                    results = []
            if truncated:
                logger.info("statement hit the row cap (%d rows); results truncated", max_rows)
            else:
                logger.info("statement returned %d row(s).", len(results))
            state.pop("error", None)
            return {
                **state,
                "results": results,
                "sql_executed": True,
                "results_truncated": truncated,
                "row_cap": max_rows,
            }

        except sqlalchemy_exc.SQLAlchemyError as e:
            # Full detail to the server log only; the client gets a generic message
            # (the raw error embeds the SQL and can leak schema/paths — SEC-05/CORR-4).
            logger.warning("SQLAlchemyError (%s) on statement: %s", type(e).__name__, e)
            return {**state, "results": None, "sql_executed": False, "error": "The query could not be executed."}

        except Exception as e:
            logger.warning("Execution error (%s) on statement: %s", type(e).__name__, e, exc_info=True)
            return {**state, "results": None, "sql_executed": False, "error": "The query could not be executed."}
