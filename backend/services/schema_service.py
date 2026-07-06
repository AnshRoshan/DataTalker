# services/schema_service.py
"""Schema extraction service."""

from typing import Dict, Any, Optional
from fastapi import HTTPException

from core.database import generate_database_hash
from core.cache import get_cached_schema, cache_schema
from graphs.schema_graph import schema_app


class SchemaService:
    """Service for handling schema extraction and caching."""
    
    @staticmethod
    def extract_and_cache_schema(
        db_uri: str, 
        db_dialect: str, 
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract schema using the schema graph and cache it."""
        db_hash = generate_database_hash(db_uri, db_path)

        # Check if schema is already cached
        cached_schema = get_cached_schema(db_hash)
        if cached_schema:
            print(f"[SchemaService] Using cached schema for database: {db_uri}")
            return cached_schema

        print(f"[SchemaService] Extracting schema for database: {db_uri}")

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
                print(f"[SchemaService] schema extraction error: {result_state['error']}")
                raise HTTPException(status_code=500, detail="Failed to extract the database schema.")

            # Cache the schema
            cache_schema(db_hash, result_state, db_path or db_uri, db_uri)

            print(f"[SchemaService] Schema extracted and cached for database: {db_uri}")
            return result_state

        except HTTPException:
            raise
        except Exception as e:
            print(f"[SchemaService] error extracting schema: {e!r}")
            raise HTTPException(status_code=500, detail="Failed to extract the database schema.")
    
    @staticmethod
    def get_schema_tables(schema_data: Dict[str, Any]) -> list:
        """Extract table names from schema data."""
        return [
            table["table_name"] 
            for table in schema_data.get("detailed_schema", [])
        ]