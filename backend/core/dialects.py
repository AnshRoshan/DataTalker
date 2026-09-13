# core/dialects.py
"""Dialect registry (EC-03): per-dialect prompt snippets for the SQL writer.

One place mapping dialect -> (context sentence, best-practices bullet list).
Adding a dialect = adding an entry here (plus driver support in
core/database.py and a timeout branch in agents/db_executor.py).
"""


def _sqlite() -> tuple[str, str]:
    return (
        "You are working with SQLite databases.",
        "- Ensure all SQL is valid SQLite syntax.\n",
    )


def _postgresql() -> tuple[str, str]:
    return (
        "You are working with PostgreSQL databases.",
        (
            "- Use standard SQL syntax compatible with PostgreSQL.\n"
            "- Pay attention to PostgreSQL-specific functions and data types where applicable.\n"
            "- Use double quotes for identifiers (table/column names) only when necessary (e.g., spaces or special characters), otherwise use standard unquoted names.\n"
            "- Use single quotes for string literals.\n"
            "- Ensure all SQL is valid PostgreSQL syntax.\n"
        ),
    )


def _mysql() -> tuple[str, str]:
    return (
        "You are working with MySQL databases.",
        (
            "- Use standard SQL syntax compatible with MySQL 8+.\n"
            "- Use backticks (`identifier`) for identifiers only when necessary (reserved words or special characters), otherwise use standard unquoted names.\n"
            "- Use single quotes for string literals.\n"
            "- Use LIMIT for row limits (e.g., LIMIT 10).\n"
            "- Date functions: NOW(), CURDATE(), DATEDIFF(), DATE_FORMAT().\n"
            "- Ensure all SQL is valid MySQL syntax.\n"
        ),
    )


# dialect -> (context, practices). Unknown dialects fall back to SQLite behavior,
# matching the pre-registry default.
DIALECT_PROMPTS: dict[str, tuple[str, str]] = {
    "sqlite": _sqlite(),
    "postgresql": _postgresql(),
    "mysql": _mysql(),
}


def get_dialect_prompt(dialect: str) -> tuple[str, str]:
    """(context, practices) for a dialect; unknown dialects default to SQLite behavior."""
    return DIALECT_PROMPTS.get(dialect, (
        "You are working with a SQL database (defaulting to SQLite behavior).",
        "- Ensure all SQL is valid SQLite syntax.\n",
    ))


def supported_dialects() -> list[str]:
    return list(DIALECT_PROMPTS)
