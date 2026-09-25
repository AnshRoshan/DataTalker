# agents/sql_writer.py
import logging
from typing import Any, Dict

from llm.service import generate_sql_or_response

logger = logging.getLogger(__name__)


def history_context(history: Any) -> str:
    """Render prior chat turns (most recent last) as compact prompt context so
    follow-up questions like "and of those, how many are female?" resolve."""
    if not isinstance(history, list) or not history:
        return ""
    lines = ["## PREVIOUS TURNS IN THIS CONVERSATION (most recent last):"]
    for turn in history:
        if not isinstance(turn, dict):
            continue
        q = str(turn.get("question", "")).strip()
        a = str(turn.get("answer", "")).strip()
        sql = str(turn.get("sql", "")).strip()
        entry = f"- Q: {q}\n  A: {a}"
        if sql:
            entry += f"\n  SQL used: {sql}"
        lines.append(entry)
    lines.append(
        "If the current question refers to those results (e.g. \"of those\", \"and how many\"), "
        "build on the previous SQL rather than starting over."
    )
    return "\n".join(lines) + "\n"


class SQLWriterAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates SQL query or a direct response based on the question and schema.
        Handles database dialect, governance restrictions, the semantic layer,
        and conversation history.
        """
        logger.debug(
            "state keys: %s",
            sorted(k for k in state if k != "detailed_schema"),
        )
        question = state.get("question", "")
        schema_description = state.get(
            "schema_description"
        )  # Use the formatted description
        db_dialect = state.get(
            "db_dialect", "sqlite"
        )  # Get dialect from state, default to sqlite

        if not schema_description:
            logger.warning("No schema description available; asking for a direct response.")
            # Return state indicating no SQL needed and provide a result message
            # Avoid overwriting existing errors if present
            if "error" not in state or not state["error"]:
                state["error"] = (
                    "No database schema information available to generate SQL."
                )
            state["sql_needed"] = False
            return state

        # Extra prompt context: governance restrictions, semantic layer, chat history.
        extra: list[str] = []
        governance_note = state.get("governance_note")
        if governance_note:
            extra.append(governance_note)
        try:
            from core.semantic import semantic_context

            semantic = semantic_context()
            if semantic:
                extra.append(semantic)
        except Exception:
            logger.debug("Semantic layer unavailable", exc_info=True)
        history = history_context(state.get("history"))
        if history:
            extra.append(history)

        # Call the LLM function, passing the dialect and extra context
        logger.info("Calling LLM for %s...", db_dialect)
        llm_result = generate_sql_or_response(
            schema=schema_description,
            question=question,
            db_dialect=db_dialect,
            extra_context="\n".join(extra),
        )

        logger.debug("LLM result keys: %s", sorted(llm_result))

        # Process the LLM result (which could be {'sql': ...}, {'response': ...}, or {'error': ...})
        if "sql" in llm_result:
            logger.info("SQL generated.")
            state["sql"] = llm_result["sql"]
            state["sql_needed"] = True
            state.pop(
                "error", None
            )  # Clear previous non-critical errors if SQL is generated
        elif "response" in llm_result:
            logger.info("Direct response generated.")
            # Pass the direct response to the formatter via the 'results' key
            state["results"] = llm_result["response"]
            state["sql_needed"] = False
            state.pop("error", None)
        elif "error" in llm_result:
            logger.warning("Error from LLM: %s", llm_result["error"])
            # Propagate the error from the LLM
            state["error"] = llm_result["error"]
            state["sql_needed"] = False
        else:
            # Unexpected result format from LLM
            logger.warning("Unexpected result format from LLM.")
            state["error"] = (
                "Unexpected result format from LLM after SQL generation attempt."
            )
            state["sql_needed"] = False

        return state
