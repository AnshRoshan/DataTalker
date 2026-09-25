# agents/schema.py
import logging
import os
import re
import time
import json  # For physical cache
import hashlib  # For creating safe filenames from paths/URIs
from pathlib import Path  # For easier path manipulation
from typing import List, Optional, Dict, Any, Set
import sqlalchemy
from sqlalchemy.sql import text
from sqlalchemy.engine.url import make_url  # To parse database URIs
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.schema import FetchedValue  # Import FetchedValue

from core.cache import get_agent_cached, set_agent_cached
from core.engines import get_engine
from core.settings import get_settings

logger = logging.getLogger(__name__)

# --- Configuration ---
DEFAULT_PHYSICAL_CACHE_DIR = Path(os.path.expanduser("~")) / ".text_to_sql_schema_cache"
# ---------------------


def _is_cache_fresh(cached: Dict[str, Any], current_mod_time: Optional[float], ttl: int) -> bool:
    """Whether a schema-cache entry is still valid.

    SQLite (mod_time known): fresh iff the stored mod_time matches the file's.
    Non-file DBs (Postgres etc., mod_time None): no cheap change signal, so bound
    staleness with a TTL against a stored `saved_at` (CORR-1: these entries were
    previously treated as valid forever, even across restarts).
    """
    if current_mod_time is not None:
        return cached.get("mod_time") == current_mod_time
    saved_at = cached.get("saved_at")
    return saved_at is not None and (time.time() - saved_at) <= ttl


# In-memory cache layer lives in core/cache.py (agent_cache) so /schema/cache
# GET/DELETE and this agent share one owner of cache state (ARCH-08).


class SchemaAgent:
    def __init__(self, physical_cache_dir: Optional[str] = None):
        self.physical_cache_path = Path(
            physical_cache_dir or DEFAULT_PHYSICAL_CACHE_DIR
        )
        # Ensure the physical cache directory exists
        self.physical_cache_path.mkdir(parents=True, exist_ok=True)
        logger.info("Using physical cache directory: %s", self.physical_cache_path)

    def _get_db_modification_time(self, db_path_str: str) -> Optional[float]:
        """Get the last modification time of the database file."""
        db_path = Path(db_path_str)
        if not db_path.exists() or not db_path.is_file():
            return None
        try:
            return db_path.stat().st_mtime
        except OSError:
            return None

    def _generate_cache_key_and_path_info(
        self, db_uri_str: str, db_dialect: str
    ) -> Dict[str, Any]:
        """
        Generates a stable cache key and info for physical file path.
        For SQLite: based on normalized absolute file path.
        For others: based on dialect and database name.
        Returns a dictionary: {'key': cache_key, 'path_for_mod_time_check': path_str_or_None}
        """
        key_base = ""
        path_for_mod_time_check = None

        try:
            uri = make_url(db_uri_str)
            if db_dialect == "sqlite":
                if uri.database:
                    # Normalize the path for SQLite
                    # Resolve relative paths, handle '///C:/path' on Windows
                    if (
                        os.name == "nt"
                        and uri.database.startswith("/")
                        and len(uri.database) > 2
                        and uri.database[2] == ":"
                    ):
                        db_file_path = Path(uri.database[1:])  # Strip leading / for C:/
                    else:
                        db_file_path = Path(uri.database)

                    if not db_file_path.is_absolute():
                        # Try to make it absolute relative to a known base or CWD
                        # This part might need adjustment based on how relative paths are constructed
                        db_file_path = db_file_path.resolve(
                            strict=False
                        )  # strict=False allows non-existent paths initially

                    key_base = str(db_file_path.resolve())  # Use resolved absolute path
                    path_for_mod_time_check = key_base
                else:
                    key_base = "sqlite_in_memory"  # For :memory: or unspecified path
            elif uri.database:  # For PostgreSQL, MySQL, etc.
                key_base = f"{db_dialect}_{uri.database}"
            else:  # Fallback if database name can't be parsed
                key_base = f"{db_dialect}_unknown_db_{hashlib.md5(db_uri_str.encode()).hexdigest()[:8]}"
        except Exception as e:
            logger.debug(
                "Could not parse URI for cache key generation (%s); using full URI hash.", e
            )
            key_base = hashlib.md5(db_uri_str.encode()).hexdigest()

        # Create a filesystem-safe name from the key_base
        safe_filename_base = re.sub(
            r'[<>:"/\\|?*\s]', "_", key_base
        )  # Replace illegal chars
        safe_filename_base = hashlib.md5(
            key_base.encode()
        ).hexdigest()  # Hash for consistency and length

        return {
            "key": f"{db_dialect}_{safe_filename_base}",
            "path_for_mod_time_check": path_for_mod_time_check,
        }

    def _get_physical_cache_filepath(self, cache_key: str) -> Path:
        """Generates the full path to the physical cache file."""
        return self.physical_cache_path / f"{cache_key}.json"

    def _load_from_physical_cache(
        self, filepath: Path, current_mod_time_for_sqlite: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        if not filepath.exists():
            return None
        try:
            with open(filepath, "r") as f:
                cached_content = json.load(f)

            if not _is_cache_fresh(cached_content, current_mod_time_for_sqlite, get_settings().cache_ttl_seconds):
                logger.debug("Physical cache stale for: %s", filepath.name)
                return None

            logger.debug("Loaded from physical cache: %s", filepath.name)
            return cached_content.get("schema_data")  # Return only the schema_data part
        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.debug(
                "Error loading or validating physical cache file %s: %s. Invalidating.", filepath, e
            )
            try:
                os.remove(filepath)  # Remove corrupted/invalid cache file
            except OSError:
                pass
            return None

    def _save_to_physical_cache(
        self,
        filepath: Path,
        schema_data: Dict[str, Any],
        mod_time_for_sqlite: Optional[float],
    ):
        try:
            # Data to store in the JSON file (saved_at bounds staleness for non-file DBs)
            data_to_store: Dict[str, Any] = {"schema_data": schema_data, "saved_at": time.time()}
            if mod_time_for_sqlite is not None:
                data_to_store["mod_time"] = mod_time_for_sqlite

            with open(filepath, "w") as f:
                json.dump(data_to_store, f, indent=2)
            logger.debug("Saved to physical cache: %s", filepath.name)
        except IOError as e:
            logger.debug("Error saving to physical cache file %s: %s", filepath, e)
        except TypeError as e:  # Catch specific JSON serialization errors
            logger.debug("JSON Serialization Error saving to physical cache file %s: %s", filepath, e)
            # Optionally, re-raise or handle more gracefully
            raise

    @staticmethod
    def _format_schema_for_llm(
        detailed_schema: List[Dict[str, Any]],
        db_dialect: str,
        masked_columns: Optional[Set[str]] = None,
    ) -> str:
        """Render the schema for the LLM. masked_columns ('table.column') are
        still listed by name but flagged so the model knows not to select them."""
        if not detailed_schema:
            return f"DATABASE SCHEMA INFORMATION ({db_dialect.upper()}): No tables selected or available.\n"

        formatted = f"DATABASE SCHEMA INFORMATION ({db_dialect.upper()}):\n"
        formatted += "When constructing SQL queries, pay close attention to the available tables and their exact column names as listed below. Use Foreign Key relationships for joins where appropriate.\n\n"

        for table_info in detailed_schema:
            table_name = table_info.get("table_name", "Unknown Table")
            columns = table_info.get("columns", [])
            foreign_keys = table_info.get("foreign_keys", [])
            row_count_str = (
                f" ({table_info['row_count']} rows)"
                if "row_count" in table_info
                else ""
            )

            column_names_summary = ", ".join([col.get("name", "?") for col in columns])

            formatted += f"TABLE: {table_name} (Columns: {column_names_summary}){row_count_str}\n"

            for col in columns:
                col_name = col.get("name", "?")
                # MODIFICATION: "type_obj" is no longer in col, this logic will correctly use col.get("type")
                col_type_obj = col.get("type_obj")  # Will be None
                col_type_str = (
                    str(col_type_obj) if col_type_obj else str(col.get("type", "?"))
                )
                pk_indicator = " [PK]" if col.get("primary_key") else ""
                unique_indicator = " [UNIQUE]" if col.get("unique") else ""
                null_indicator = " [NOT NULL]" if not col.get("nullable") else ""

                default_val = col.get("default")
                default_info = ""
                # This logic remains robust as default_val will now be a primitive or string
                if (
                    default_val is not None
                ):  # Check if default_val is not None before formatting
                    if isinstance(
                        default_val, TextClause
                    ):  # This condition will likely not be met if pre-stringified
                        default_info = f" [DEFAULT: {str(default_val).upper()}]"
                    elif isinstance(default_val, str):
                        # If it was a TextClause and now a string, it might appear quoted.
                        # Example: TextClause("CURRENT_TIMESTAMP") becomes "'CURRENT_TIMESTAMP'" if not handled carefully
                        # However, our serialization converts it to "CURRENT_TIMESTAMP", so this is fine.
                        default_info = (
                            f" [DEFAULT: '{default_val}']"
                            if not default_val.isupper() and not default_val.isnumeric()
                            else f" [DEFAULT: {default_val}]"
                        )

                    else:  # Numbers, booleans
                        default_info = f" [DEFAULT: {str(default_val)}]"

                sample_values_str = ""
                if col.get("sample_values"):
                    samples = ", ".join([f'"{s}"' for s in col["sample_values"]])
                    sample_values_str = f" (e.g., {samples})"
                type_clarification = ""
                if (
                    "TEXT" in col_type_str.upper()
                    and any(
                        hint in col_name.upper()
                        for hint in ["DATE", "TIME", "_AT", "_TS"]
                    )
                    and col.get("sample_values")
                ):
                    first_sample = col["sample_values"][0]
                    if re.match(
                        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)?$",
                        first_sample,
                    ):
                        type_clarification = " (likely timestamp)"
                    elif re.match(r"^\d{4}-\d{2}-\d{2}$", first_sample):
                        type_clarification = " (likely date)"
                masked_flag = (
                    " [MASKED — must not appear in SELECT output]"
                    if masked_columns and f"{table_name}.{col_name}" in masked_columns
                    else ""
                )
                formatted += f"  - {col_name}: {col_type_str}{type_clarification}{pk_indicator}{unique_indicator}{null_indicator}{default_info}{sample_values_str}{masked_flag}\n"
            if foreign_keys:
                formatted += "  FOREIGN KEYS:\n"
                for fk in foreign_keys:
                    constrained_columns = ", ".join(
                        fk.get("constrained_columns", ["?"])
                    )
                    referred_table = fk.get("referred_table", "?")
                    referred_columns = ", ".join(fk.get("referred_columns", ["?"]))
                    fk_name_str = f" (name: {fk.get('name')})" if fk.get("name") else ""
                    formatted += f"    - {constrained_columns} → {referred_table}({referred_columns}){fk_name_str}\n"
            formatted += "\n"
        return formatted

    def _extract_schema_sqlalchemy(
        self, db_uri: str, db_dialect: str
    ) -> Dict[str, Any]:
        logger.debug("Extracting schema via SQLAlchemy (dialect: %s)", db_dialect)
        # Pooled engine (PR-03) — no per-extraction create/dispose. SQLite
        # connections are pinned read-only by core.engines' connect listener.
        engine = get_engine(db_uri)
        inspector = sqlalchemy.inspect(engine)
        metadata = sqlalchemy.MetaData()

        detailed_schema = []
        table_names = inspector.get_table_names()

        for table_name in table_names:
            if db_dialect == "sqlite" and table_name.startswith("sqlite_"):
                continue

            columns_meta = inspector.get_columns(table_name)
            foreign_keys_meta = inspector.get_foreign_keys(table_name)
            primary_keys_names = inspector.get_pk_constraint(table_name).get(
                "constrained_columns", []
            )
            row_count = None
            try:
                with engine.connect() as connection:
                    result = connection.execute(
                        text(f'SELECT COUNT(*) FROM "{table_name}";')
                    )
                    row_count = result.scalar_one_or_none()
            except Exception as count_exc:
                logger.debug("Could not get row count for table %s: %s", table_name, count_exc)
            column_details = []
            reflected_table = None
            try:
                reflected_table = sqlalchemy.Table(
                    table_name, metadata, autoload_with=engine
                )
            except Exception as reflect_exc:
                logger.debug("Could not reflect table %s for sample data: %s", table_name, reflect_exc)

            for col_meta in columns_meta:
                # --- MODIFICATION START ---
                # Handle serialization of default value for JSON compatibility
                col_default_value = col_meta.get("default")
                serializable_default = None  # Explicitly initialize

                if isinstance(col_default_value, (TextClause, FetchedValue)):
                    serializable_default = str(col_default_value)
                elif col_default_value is not None and not isinstance(
                    col_default_value, (str, int, float, bool, list, dict)
                ):
                    # Fallback for other complex types that might not be primitives or common serializable types
                    logger.debug(
                        "Converting complex default value of type %s to string for column %s.%s.",
                        type(col_default_value), table_name, col_meta["name"],
                    )
                    serializable_default = str(col_default_value)
                else:
                    # Handles None, str, int, float, bool, list, dict (which are JSON serializable)
                    serializable_default = col_default_value

                col_info = {
                    "name": col_meta["name"],
                    "type": str(col_meta["type"]),  # String representation of the type
                    # "type_obj": col_meta["type"], # REMOVED: This was the source of non-JSON serializable SQLAlchemy type objects
                    "nullable": col_meta["nullable"],
                    "default": serializable_default,  # Now a JSON-serializable version
                    "primary_key": col_meta["name"] in primary_keys_names,
                    "unique": col_meta.get("unique", False),
                    "sample_values": [],
                }
                # --- MODIFICATION END ---

                is_text_type = any(
                    t
                    in str(
                        col_meta["type"]
                    ).upper()  # Use str(col_meta["type"]) as type_obj is gone
                    for t in ["TEXT", "VARCHAR", "CHAR", "STRING", "CLOB"]
                )
                is_key_column = col_info["primary_key"] or any(
                    col_meta["name"] in fk.get("constrained_columns", [])
                    for fk in foreign_keys_meta
                )
                if (
                    is_text_type
                    and not is_key_column
                    and reflected_table is not None
                    and col_meta["name"] in reflected_table.c
                ):
                    try:
                        with engine.connect() as connection:
                            stmt = (
                                sqlalchemy.select(
                                    sqlalchemy.distinct(
                                        reflected_table.c[col_meta["name"]]
                                    )
                                )
                                .where(reflected_table.c[col_meta["name"]].isnot(None))
                                .limit(3)
                            )
                            sample_result = connection.execute(stmt)
                            raw_samples = [
                                row[0] for row in sample_result if row[0] is not None
                            ]
                            processed_samples = []
                            for s_val in raw_samples:
                                s_str = str(s_val)
                                processed_samples.append(
                                    s_str[:30] + "..." if len(s_str) > 30 else s_str
                                )
                            col_info["sample_values"] = processed_samples
                    except Exception as sample_exc:
                        logger.debug(
                            "Could not get sample values for %s.%s: %s", table_name, col_meta["name"], sample_exc
                        )
                column_details.append(col_info)
            table_data = {
                "table_name": table_name,
                "columns": column_details,
                "foreign_keys": foreign_keys_meta,
            }
            if row_count is not None:
                table_data["row_count"] = row_count
            detailed_schema.append(table_data)
        return {"detailed_schema": detailed_schema}

    def __call__(self, state: dict) -> dict:
        logger.debug(
            "state keys: %s",
            sorted(k for k in state if k not in ("detailed_schema", "schema_description")),
        )
        db_uri = state.get("db_uri")
        db_dialect = state.get("db_dialect")
        include_tables: Optional[List[str]] = state.get("include_tables")

        if not db_uri or not db_dialect:
            return {
                **state,
                "error": "Missing database URI or dialect in state for SchemaAgent.",
            }

        try:
            cache_info = self._generate_cache_key_and_path_info(db_uri, db_dialect)
            cache_key = cache_info["key"]
            sqlite_path_for_mod_time = cache_info["path_for_mod_time_check"]

            current_sqlite_mod_time = None
            if sqlite_path_for_mod_time:
                current_sqlite_mod_time = self._get_db_modification_time(
                    sqlite_path_for_mod_time
                )

            ttl = get_settings().cache_ttl_seconds
            full_schema_data = None  # Initialize
            cached_in_memory = get_agent_cached(cache_key)
            if cached_in_memory:
                if _is_cache_fresh(cached_in_memory, current_sqlite_mod_time, ttl):
                    logger.debug("Using in-memory cached schema for: %s", cache_key)
                    full_schema_data = cached_in_memory["schema_data"]
                else:
                    logger.debug("In-memory cache stale for: %s", cache_key)

            if full_schema_data is None:  # Check if not loaded from in-memory cache
                physical_cache_file = self._get_physical_cache_filepath(cache_key)
                loaded_from_physical = self._load_from_physical_cache(
                    physical_cache_file, current_sqlite_mod_time
                )

                if loaded_from_physical:
                    full_schema_data = loaded_from_physical
                    set_agent_cached(cache_key, full_schema_data, current_sqlite_mod_time)
                else:
                    logger.debug(
                        "Cache miss (in-memory & physical) or invalidation for: %s. Extracting schema.",
                        cache_key,
                    )
                    full_schema_data = self._extract_schema_sqlalchemy(
                        db_uri, db_dialect
                    )
                    self._save_to_physical_cache(
                        physical_cache_file, full_schema_data, current_sqlite_mod_time
                    )
                    set_agent_cached(cache_key, full_schema_data, current_sqlite_mod_time)

            final_detailed_schema_to_format = full_schema_data.get(
                "detailed_schema", []
            )
            if include_tables:
                final_detailed_schema_to_format = [
                    table_info
                    for table_info in final_detailed_schema_to_format
                    if table_info.get("table_name") in include_tables
                ]

            schema_description = self._format_schema_for_llm(
                final_detailed_schema_to_format, db_dialect
            )

            return {
                **state,
                "detailed_schema": final_detailed_schema_to_format,  # This now contains the serializable version
                "schema_description": schema_description,
                "error": None,
            }

        except Exception as e:
            # Full traceback to the server log only; callers surface a generic error.
            logger.warning("Schema extraction failed: %s", e, exc_info=True)
            state.pop("detailed_schema", None)
            state.pop("schema_description", None)
            return {**state, "error": f"SchemaAgent processing failed: {str(e)}"}
