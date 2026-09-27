# services/sql_service.py
"""SQL console: run a hand-written statement through the same guard the LLM answers go
through, not a second, weaker one.

The chat path can afford to retry and to explain; a console cannot, because the human
already knows what they asked for. So this skips the graph and uses the two agents that
carry the actual guarantees — ValidatorAgent (single read-only statement, governance
columns) and DBExecutorAgent (pooled read-only engine, statement timeout, hard row cap)
— plus the same result masking. A statement that the chat pipeline would refuse is
refused here with the same reason.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from agents.db_executor import DBExecutorAgent
from agents.validator import ValidatorAgent
from core.governance import load_governance, mask_rows

logger = logging.getLogger(__name__)

_MAX_SQL_LENGTH = 20_000


class SqlConsoleService:
    _validator = ValidatorAgent()
    _executor = DBExecutorAgent()

    @classmethod
    def run(cls, sql: str, db_uri: str, db_dialect: str,
            masked_columns: Optional[List[str]] = None) -> Dict[str, Any]:
        statement = (sql or "").strip()
        if not statement:
            raise HTTPException(status_code=400, detail="Enter a SQL statement to run.")
        if len(statement) > _MAX_SQL_LENGTH:
            raise HTTPException(status_code=400, detail="That statement is too long to run.")

        state: Dict[str, Any] = {
            "sql": statement,
            "db_uri": db_uri,
            "db_dialect": db_dialect,
            "masked_columns": list(masked_columns) if masked_columns else None,
        }

        state = cls._validator(state)
        if not state.get("is_safe"):
            # The refusal is the product here, so the reason goes back to the client —
            # it describes the guard, not the data.
            logger.info("console statement rejected: %s", state.get("validation_reason"))
            return {
                "sql": statement,
                "results": [],
                "row_count": 0,
                "sql_executed": False,
                "validator_rejected": True,
                "reason": state.get("validation_reason", "Statement rejected by the read-only guard."),
                "latency_ms": 0,
            }

        started = time.perf_counter()
        state = cls._executor(state)
        latency_ms = round((time.perf_counter() - started) * 1000)

        error = state.get("error")
        if error:
            # Executor messages are already generic (raw DB errors are logged, not
            # returned), but keep the shape identical to a rejection so the client has
            # one thing to render.
            return {
                "sql": statement,
                "results": [],
                "row_count": 0,
                "sql_executed": False,
                "validator_rejected": False,
                "reason": error,
                "latency_ms": latency_ms,
            }

        rows = state.get("results") or []
        gov = load_governance()
        if gov and rows and all(isinstance(r, dict) for r in rows):
            rows = mask_rows(rows, gov)

        return {
            "sql": statement,
            "results": rows,
            "row_count": len(rows),
            "sql_executed": bool(state.get("sql_executed")),
            "validator_rejected": False,
            "results_truncated": bool(state.get("results_truncated")),
            "row_cap": state.get("row_cap"),
            "reason": None,
            "latency_ms": latency_ms,
        }
