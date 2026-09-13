# services/query_service.py
"""Query processing service."""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.governance import load_governance, mask_rows, prompt_note
from graphs.query_graph import query_app

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 5


def _sanitize_history(history: Any) -> List[Dict[str, Any]]:
    """Keep the last MAX_HISTORY_TURNS well-formed turns (most recent last)."""
    if not isinstance(history, list):
        return []
    turns = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        if not isinstance(turn, dict):
            continue
        turns.append({
            "question": str(turn.get("question", ""))[:2000],
            "answer": str(turn.get("answer", ""))[:2000],
            "sql": str(turn.get("sql", ""))[:2000],
        })
    return turns


class QueryService:
    """Service for handling query processing."""

    @staticmethod
    def process_query(
        question: str,
        db_uri: str,
        db_dialect: str,
        schema_data: Dict[str, Any],
        db_path: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Process a natural language question against the database."""

        if not question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        # Governance-lite (EC-05): masking strategies + prompt note come from the
        # schema service; load the governance config again for result masking.
        gov = load_governance()
        masked_columns = schema_data.get("masked_columns") or []

        # Prepare state for query processing
        query_state = {
            "question": question,
            "db_path": db_path,
            "db_uri": db_uri,
            "db_dialect": db_dialect,
            "detailed_schema": schema_data.get("detailed_schema"),
            "schema_description": schema_data.get("schema_description"),
            "history": _sanitize_history(history),
            "masked_columns": list(masked_columns) if masked_columns else None,
            "governance_note": schema_data.get("governance_note"),
        }

        try:
            started = time.perf_counter()
            # Process with Query Graph
            result_state = query_app.invoke(query_state)
            latency_ms = round((time.perf_counter() - started) * 1000)

            # Post-process results: redact governance-masked columns (EC-05).
            results = result_state.get("results", [])
            if gov and isinstance(results, list) and results and all(isinstance(r, dict) for r in results):
                results = mask_rows(results, gov)

            # Prepare response data (shape only grows — the frontend ignores unknown keys)
            sql_executed = bool(result_state.get("sql_executed"))
            response_data = {
                "answer": result_state.get("answer", "No answer generated."),
                "sql": result_state.get("sql", ""),
                "results": results,
                "follow_up_questions": result_state.get("follow_up_questions", []),
                "results_truncated": bool(result_state.get("results_truncated")),
                "sql_executed": sql_executed,
                "validator_rejected": bool(result_state.get("is_safe") is False),
                "latency_ms": latency_ms,
            }
            if result_state.get("results_truncated"):
                response_data["row_cap"] = result_state.get("row_cap")

            # Handle different result types
            if isinstance(response_data["results"], str):
                # If results is a string (error message), convert to empty list
                response_data["results"] = []
            elif not isinstance(response_data["results"], list):
                # If results is not a list, convert to empty list
                response_data["results"] = []

            return response_data

        except Exception as e:
            logger.warning("error processing query: %r", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to process the query.")
