# agents/validator.py
from typing import Any, Dict, Tuple
import re

# ponytail: allowlist guard (a single read-only SELECT/WITH statement) replaces the old
# keyword blocklist, which missed ATTACH / COPY ... TO PROGRAM / pg_read_file and allowed
# statement chaining. Upgrade path: sqlglot for literal-aware parsing if query obfuscation
# becomes a concern. Production Postgres should ALSO connect with a least-privilege
# read-only role (the guard cannot enforce roles). SQLite reads are additionally pinned
# read-only via `PRAGMA query_only = ON` in the executor.

_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.S)
_LITERAL = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"", re.S)  # string + quoted-identifier literals
_STARTS_READ = re.compile(r"^\s*(select|with)\b", re.I)
_WRITE = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|replace|"
    r"attach|detach|vacuum|pragma|reindex|copy|call)\b",
    re.I,
)
_DANGEROUS_FN = re.compile(
    r"\b(pg_read_file|pg_read_binary_file|pg_ls_dir|pg_stat_file|lo_import|lo_export|dblink)\b",
    re.I,
)


def is_read_only_select(sql: str) -> Tuple[bool, str]:
    """Allow only a single read-only SELECT/WITH statement. Returns (allowed, reason)."""
    if not sql or not isinstance(sql, str):
        return False, "No SQL query provided."
    cleaned = _COMMENT.sub(" ", sql).strip().rstrip(";").strip()
    if not cleaned:
        return False, "Empty SQL query."
    # Blank out string/identifier literals so a value like 'delete' or a ';' inside a
    # string is not mistaken for a keyword or a second statement.
    scan = _LITERAL.sub(" ", cleaned)
    if ";" in scan:
        return False, "Only a single statement is allowed."
    if not _STARTS_READ.match(cleaned):
        return False, "Only read-only SELECT/WITH queries are allowed."
    if _WRITE.search(scan):
        return False, "Only read-only queries are allowed (write/DDL keyword found)."
    if _DANGEROUS_FN.search(scan):
        return False, "Query uses a disallowed function."
    return True, "SQL is a single read-only query."


class ValidatorAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Gate SQL execution: only a single read-only SELECT/WITH statement may pass."""
        sql = state.get("sql", "")
        is_safe, reason = is_read_only_select(sql)
        state["is_safe"] = is_safe
        state["validation_reason"] = reason
        if not is_safe:
            state["unsafe_sql_attempt"] = sql
            state["sql"] = "-- Query blocked by read-only guard"
            state["response"] = f"Error: {reason} Query blocked for security."
            print(f"[ValidatorAgent] blocked: {reason}")
        return state
