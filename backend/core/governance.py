# core/governance.py
"""Governance-lite (EC-06/EC-05): optional table allowlist + column masking.

Configured via DATATALKER_GOVERNANCE_FILE pointing at a JSON file:
    {"allowed_tables": ["patients", "doctors"],
     "masked_columns": {"patients.ssn": "full", "patients.phone": "partial"}}

Strategies: "full" -> "***", "partial" -> keep last 4 chars, "hash" -> short
sha256 hex. No file (or empty setting) = no restrictions, current behavior.

Column matching for SQL rejection is a deliberately simple identifier check
(sqlglot is not installed): a bare or table-qualified reference to a masked
column name is rejected. The bare-name match is fail-closed — if two tables
share a column name and only one is masked, queries against either are
rejected. Over-blocking is the safe direction for governance.
"""
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .settings import get_settings

logger = logging.getLogger(__name__)

_MASK_STRATEGIES = ("full", "partial", "hash")

_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.S)
_DQUOTE_IDENT = re.compile(r'"([^"]+)"')
_BACKTICK_IDENT = re.compile(r"`([^`]+)`")
_SQ_LITERAL = re.compile(r"'(?:[^']|'')*'", re.S)
_IDENT = r"(?:(?:\"[^\"]+\")|(?:`[^`]+`)|[A-Za-z_][A-Za-z0-9_]*)"


def load_governance() -> Optional[Dict[str, Any]]:
    """Load and validate the governance file. None = no restrictions."""
    path = get_settings().governance_file_path
    if not get_settings().governance_file:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Governance file %s could not be loaded (%s); failing closed.", path, e)
        # Fail closed: an unreadable governance file must not silently disable
        # the restrictions it was configured to enforce.
        return {"allowed_tables": [], "masked_columns": {}}

    allowed = raw.get("allowed_tables")
    masked = raw.get("masked_columns", {})
    masked = {
        str(k).strip(): v
        for k, v in masked.items()
        if isinstance(k, str) and k.strip() and v in _MASK_STRATEGIES
    }
    return {
        "allowed_tables": set(allowed) if isinstance(allowed, list) else None,
        "masked_columns": masked,
    }


def masked_columns_of(gov: Dict[str, Any]) -> Set[str]:
    """The set of masked columns as 'table.column' strings."""
    return set(gov.get("masked_columns", {}))


def filter_schema(
    detailed_schema: List[Dict[str, Any]], gov: Optional[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Keep only allowed tables; return (filtered_schema, masked 'table.column' set).

    Masked columns stay visible by name so the LLM understands the schema —
    they are flagged as forbidden in the prompt instead (see prompt_note).
    """
    if not gov:
        return detailed_schema, set()
    allowed = gov.get("allowed_tables")
    masked = masked_columns_of(gov)
    if allowed is None:
        filtered = detailed_schema
    else:
        filtered = [t for t in detailed_schema if t.get("table_name") in allowed]
    return filtered, masked


def mask_value(value: Any, strategy: str) -> Any:
    """Apply a masking strategy to a single value."""
    if value is None:
        return None
    if strategy == "full":
        return "***"
    if strategy == "partial":
        s = str(value)
        return "*" * max(0, len(s) - 4) + s[-4:] if len(s) > 4 else "***"
    if strategy == "hash":
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return "***"


def mask_rows(rows: List[Dict[str, Any]], gov: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Redact masked-column values in result rows.

    Rows carry bare column names (no table prefix), so matching is by column
    name: a result column is masked if any 'table.column' entry ends with it.
    """
    masked_columns = gov.get("masked_columns", {})
    if not masked_columns or not rows:
        return rows
    strategies: Dict[str, str] = {}
    for qualified, strategy in masked_columns.items():
        strategies.setdefault(str(qualified).split(".")[-1].lower(), strategy)
    out: List[Dict[str, Any]] = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            bare = str(key).split(".")[-1].lower()
            if bare in strategies:
                new_row[key] = mask_value(value, strategies[bare])
            else:
                new_row[key] = value
        out.append(new_row)
    return out


def sql_selects_masked_column(sql: str, masked: Set[str]) -> Optional[str]:
    """Reason string if the SQL references a masked column, else None."""
    if not masked or not sql or not isinstance(sql, str):
        return None
    # Strip comments, unquote double-quoted/backtick identifiers (so "ssn"
    # matches ssn), then blank single-quoted string literals so a value like
    # 'ssn' is not mistaken for a column reference.
    scan = _COMMENT.sub(" ", sql)
    scan = _DQUOTE_IDENT.sub(r"\1", scan)
    scan = _BACKTICK_IDENT.sub(r"\1", scan)
    scan = _SQ_LITERAL.sub(" ", scan)
    for qualified in masked:
        table, _, column = qualified.partition(".")
        pattern = rf"{_quote(table)}\s*\.\s*{_quote(column)}"
        if re.search(pattern, scan, re.I):
            return f"Query selects the restricted column '{column}'."
        # Bare reference (fail-closed on shared column names — see module docstring).
        if re.search(rf"\b{_quote(column)}\b", scan, re.I):
            return f"Query references the restricted column '{column}'."
    return None


def _quote(name: str) -> str:
    """Regex for an identifier that may be quoted."""
    body = re.escape(name)
    return rf"(?:\"{body}\"|`{body}`|{body})"


def prompt_note(masked: Set[str]) -> str:
    """Prompt fragment telling the LLM which columns must never be selected."""
    if not masked:
        return ""
    cols = ", ".join(sorted(masked))
    return (
        "## GOVERNANCE RESTRICTIONS:\n"
        f"The following columns are restricted and MUST NOT appear in SELECT output: {cols}.\n"
        "Never select, aggregate, or filter output on these columns directly. "
        "Use other columns to answer the question; if the question cannot be "
        "answered without them, return a direct response saying so.\n"
    )
