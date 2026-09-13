# services/schema_service.py
"""Schema extraction service."""

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException

from core.database import generate_database_hash
from core.cache import get_cached_schema, cache_schema
from core.governance import filter_schema, load_governance, prompt_note
from graphs.schema_graph import schema_app
from agents.schema import SchemaAgent

logger = logging.getLogger(__name__)


class SchemaService:
    """Service for handling schema extraction and caching."""

    @staticmethod
    def extract_and_cache_schema(
        db_uri: str,
        db_dialect: str,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract schema using the schema graph and cache it.

        The full schema is cached; when a governance file is configured the
        returned view is filtered (allowed tables only) and masked columns are
        flagged, so every consumer (LLM prompt, /schema/ listing) sees the
        governed view.
        """
        db_hash = generate_database_hash(db_uri, db_path)

        # Check if schema is already cached
        cached_schema = get_cached_schema(db_hash)
        if cached_schema:
            logger.debug("Using cached schema for database (dialect %s).", db_dialect)
            return SchemaService._apply_governance(cached_schema)

        logger.info("Extracting schema for database (dialect: %s).", db_dialect)

        # Prepare state for schema extraction
        schema_state = {
            "db_uri": db_uri,
            "db_dialect": db_dialect,
            "db_path": db_path,
        }

        try:
            # Extract schema using schema graph
            result_state = schema_app.invoke(schema_state)

            if result_state.get("error"):
                logger.warning("schema extraction error: %s", result_state['error'])
                raise HTTPException(status_code=500, detail="Failed to extract the database schema.")

            # Cache the full schema (governance is applied on read, so config
            # changes take effect without cache invalidation)
            cache_schema(db_hash, result_state, db_path or db_uri, db_uri)

            logger.info("Schema extracted and cached (dialect: %s).", db_dialect)
            return SchemaService._apply_governance(result_state)

        except HTTPException:
            raise
        except Exception as e:
            logger.warning("error extracting schema: %r", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to extract the database schema.")

    @staticmethod
    def _apply_governance(schema_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a governed view of schema_data (no-op without a config file)."""
        gov = load_governance()
        if not gov:
            return schema_data
        filtered, masked = filter_schema(schema_data.get("detailed_schema", []), gov)
        governed = dict(schema_data)
        governed["detailed_schema"] = filtered
        governed["masked_columns"] = sorted(masked)
        governed["governance_note"] = prompt_note(masked)
        # Re-render the prompt description so masked columns are flagged inline.
        governed["schema_description"] = SchemaAgent._format_schema_for_llm(
            filtered, governed.get("db_dialect") or "sqlite",
            masked_columns=masked,
        )
        return governed

    @staticmethod
    def get_schema_tables(schema_data: Dict[str, Any]) -> list:
        """Extract table names from schema data."""
        return [
            table["table_name"]
            for table in schema_data.get("detailed_schema", [])
        ]
