# llm/service.py
"""Provider-agnostic LLM service: the two functions the agents call.

Contracts (unchanged from the old llm/gemini.py — the agents and graph depend on them):
- generate_sql_or_response -> {"sql": str} | {"response": str} | {"error": str, "retryable": bool}
- format_answer            -> {"answer": str, "follow_up_questions": list}   (never an error dict)

The retry loop lives HERE, not in providers, because it must also cover parse
failures (the model returning non-JSON) — which only this layer can detect.
SQLRetryAgent in the graph only retries empty results after execution.
"""
import json
import logging
import re
import time
from typing import Any, Callable, Dict, Literal

from llm.base import LLMError
from llm.factory import get_provider
from llm.prompts import build_answer_instruction, build_sql_instruction

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

_GENERIC_UNAVAILABLE = "The language model is unavailable."


def _strip_fences(text: str) -> str:
    """Remove a surrounding ```/```json markdown fence, if present."""
    content = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", content)


def _parse_sql_response(response_text: str) -> Dict[str, Any]:
    """Moved from llm/gemini.py:_parse_and_validate_gemini_response — contract unchanged.

    (The old fence-stripping regex used r"\\s*" — a literal backslash — and never
    matched; the re.search fallback made it work anyway. _strip_fences fixes the
    regex; the fallback is kept for JSON embedded in prose.)
    """
    if not response_text:
        return {"error": "LLM returned an empty response.", "retryable": True}
    content = _strip_fences(response_text)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return {"error": "LLM did not return valid JSON.", "retryable": True, "raw_content": response_text}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"error": "LLM returned malformed JSON.", "retryable": True, "raw_content": response_text}
    if not isinstance(parsed, dict):
        return {
            "error": f"LLM JSON was not an object (got {type(parsed).__name__}).",
            "retryable": True,
            "raw_content": content,
        }
    sql = parsed.get("sql")
    if isinstance(sql, str) and sql.strip():
        if "SELECT _FROM" in sql:  # known bad-generation pattern, kept from the old parser
            return {"error": "LLM generated potentially invalid SQL.", "retryable": True, "raw_content": content}
        return {"sql": sql, "retryable": False}
    response = parsed.get("response")
    if isinstance(response, str) and response.strip():
        return {"response": response, "retryable": False}
    return {
        "error": f"LLM JSON missing a non-empty 'sql' or 'response' key. Found keys: {list(parsed.keys())}",
        "retryable": True,
        "raw_content": content,
    }


def _parse_answer(response_text: str) -> Dict[str, Any]:
    """Answer formatting is best-effort: non-JSON output falls back to the raw text
    as the answer (pre-refactor behavior) instead of triggering a retry."""
    content = _strip_fences(response_text)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Answer formatter returned non-JSON; falling back to raw text.")
        return {"answer": content, "follow_up_questions": []}
    if not isinstance(parsed, dict):
        return {"answer": content, "follow_up_questions": []}
    return {
        "answer": parsed.get("answer", "Could not format the results."),
        "follow_up_questions": parsed.get("follow_up_questions", []),
    }


def _complete_with_retries(
    system: str, user: str, parse: Callable[[str], Dict[str, Any]]
) -> Dict[str, Any]:
    """Call the provider, parse its text; retry (with backoff) on retryable failures."""
    last_error: Dict[str, Any] = {"error": _GENERIC_UNAVAILABLE, "retryable": True}
    for attempt in range(MAX_RETRIES):
        try:
            text = get_provider().complete(system, user)
        except LLMError as e:
            # Full detail to logs only; clients get the actionable hint (rejected
            # credentials/config) or a generic message (PR-05).
            logger.warning("LLM transport failure (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            last_error = {"error": e.hint or _GENERIC_UNAVAILABLE, "retryable": e.retryable}
            if not e.retryable:
                return last_error
            time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
            continue
        except RuntimeError as e:
            # Provider misconfig from the factory (names an env var, no secrets).
            # Spec: a clear error at first use, never a vague 500. Never retryable.
            logger.warning("LLM provider misconfigured: %s", e)
            return {"error": str(e), "retryable": False}
        parsed = parse(text)
        if "error" not in parsed:
            return parsed
        last_error = parsed
        if not parsed.get("retryable"):
            return parsed
        logger.warning("LLM output rejected (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, parsed.get("error"))
        time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    logger.warning("All %d LLM attempts failed: %s", MAX_RETRIES, last_error.get("error"))
    return last_error


def generate_sql_or_response(
    schema: str,
    question: str,
    db_dialect: Literal["sqlite", "postgresql", "mysql"] | str = "sqlite",
    extra_context: str = "",
) -> Dict[str, Any]:
    """NL question + schema -> {"sql"} | {"response"} | {"error", "retryable"}.

    extra_context (governance notes, semantic layer, chat history) is appended
    to the user message after the schema.
    """
    system = build_sql_instruction(db_dialect)
    user = f"Schema:\n```\n{schema}\n```\n\nQuestion: {question}"
    if extra_context:
        user += f"\n\n{extra_context}"
    return _complete_with_retries(system, user, _parse_sql_response)


def format_answer(question: Any, result: Any) -> Dict[str, Any]:
    """Query results -> {"answer", "follow_up_questions"}. Never returns an error dict."""
    system = build_answer_instruction()
    user = (
        f"Original Question: {question}\n\n"
        f"Query Results: {result}\n\n"
        "Task: Format the results into a structured JSON response with the main answer and relevant follow-up questions."
    )
    parsed = _complete_with_retries(system, user, _parse_answer)
    if "error" in parsed:
        return {"answer": "Sorry, I couldn't format the answer right now.", "follow_up_questions": []}
    return parsed
