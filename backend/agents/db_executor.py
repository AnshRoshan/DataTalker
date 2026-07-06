# agents/db_executor.py
import sqlalchemy
from typing import Dict, Any
from sqlalchemy import exc as sqlalchemy_exc


class DBExecutorAgent:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single validated read-only SQL statement and return its rows."""
        print(
            "[DBExecutorAgent] received state:",
            {
                k: v
                for k, v in state.items()
                if k not in ["detailed_schema", "schema_description", "results"]
            },
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

        engine = None
        try:
            engine = sqlalchemy.create_engine(db_uri)
            with engine.connect() as connection:
                if db_dialect == "sqlite":
                    # ponytail: SQLite native read-only pin — blocks any write even if the
                    # guard is bypassed. Postgres relies on the guard + a least-privilege role.
                    connection.exec_driver_sql("PRAGMA query_only = ON")
                result_proxy = connection.execute(sqlalchemy.text(statement))
                results = (
                    [dict(row) for row in result_proxy.mappings().all()]
                    if result_proxy.returns_rows
                    else []
                )
            print(f"[DBExecutorAgent] statement returned {len(results)} row(s).")
            state.pop("error", None)
            return {**state, "results": results, "sql_executed": True}

        except sqlalchemy_exc.SQLAlchemyError as e:
            error_message = f"SQLAlchemy Execution Error ({type(e).__name__}) on sql {sql}: {str(e)}"
            print(f"[DBExecutorAgent] {error_message}")
            return {**state, "results": None, "sql_executed": False, "error": error_message}

        except Exception as e:
            import traceback

            error_message = f"Generic Execution Error ({type(e).__name__}) on sql {sql}: {str(e)}\n{traceback.format_exc()}"
            print(f"[DBExecutorAgent] {error_message}")
            return {**state, "results": None, "sql_executed": False, "error": error_message}
        finally:
            if engine:
                engine.dispose()
