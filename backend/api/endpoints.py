# api/endpoints.py
"""FastAPI route definitions."""

import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse

from .dependencies import DatabaseInputHandler, require_api_key
from .models import SchemaResponse, QueryResponse, CacheResponse, ClearCacheResponse, HealthResponse, APIInfo
from services.schema_service import SchemaService
from services.query_service import QueryService
from core.audit import record_audit
from core.cache import get_cache_info, clear_cache
from core.file_handler import cleanup_temp_file
from core.logging_config import request_id_var
from core.settings import get_settings

logger = logging.getLogger(__name__)


def create_endpoints(app: FastAPI) -> None:
    """Create and register all API endpoints."""

    # ponytail: sync `def` (not async) so Starlette runs the blocking schema reflection in
    # its threadpool instead of stalling the event loop for every request (PR-02).
    @app.post("/schema/", response_model=SchemaResponse, dependencies=[Depends(require_api_key)])
    def extract_schema(
        db_file: Optional[UploadFile] = File(None),
        db_path: Optional[str] = Form(None),
        db_url: Optional[str] = Form(None),
        db_connection_string: Optional[str] = Form(None),
    ):
        """
        Extract and cache database schema endpoint that supports multiple input methods:
        - File upload (db_file) - SQLite files only
        - Local file path (db_path) - SQLite files, must be absolute path
        - Remote URL (db_url) - Can be either:
          * Database connection string (postgresql://user:pass@host:port/dbname or sqlite:///path)
          * File download URL (for SQLite files, downloads and caches locally)
        - Connection string (db_connection_string) - SQLite (sqlite:///path), PostgreSQL, or MySQL
        """
        temp_file_to_cleanup = None

        try:
            # Process database input
            db_uri, db_dialect, local_db_path, temp_file_to_cleanup = (
                DatabaseInputHandler.process_database_input(
                    db_file, db_path, db_url, db_connection_string
                )
            )

            # Extract and cache schema
            started = time.perf_counter()
            schema_data = SchemaService.extract_and_cache_schema(
                db_uri, db_dialect, local_db_path
            )
            tables = SchemaService.get_schema_tables(schema_data)

            # Audit: minimal schema-extraction record — dialect + table count only
            # (never the URI/credentials, EC-08).
            record_audit({
                "event": "schema_extract",
                "request_id": request_id_var.get(),
                "dialect": db_dialect,
                "table_count": len(tables),
                "latency_ms": round((time.perf_counter() - started) * 1000),
            })

            # Prepare response
            # ponytail: do NOT echo database_uri/path back — a postgresql:// URI leaks the
            # password to the client (SEC-05).
            response_data = {
                "message": "Schema extracted and cached successfully",
                "database_dialect": db_dialect,
                "tables": tables,
                "schema_description": schema_data.get("schema_description", ""),
                "cached": True,
            }

            return JSONResponse(content=response_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.warning("internal error: %r", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error.")
        finally:
            # Cleanup temporary files (but keep uploaded files for potential reuse)
            if temp_file_to_cleanup and not db_file:
                cleanup_temp_file(temp_file_to_cleanup)

    # ponytail: sync `def` so the blocking SQL + LLM pipeline runs in Starlette's threadpool
    # rather than blocking the event loop (PR-02). Handler never awaits, so this is safe.
    @app.post("/chat/", response_model=QueryResponse, dependencies=[Depends(require_api_key)])
    def chat_with_database(
        question: str = Form(...),
        db_file: Optional[UploadFile] = File(None),
        db_path: Optional[str] = Form(None),
        db_url: Optional[str] = Form(None),
        db_connection_string: Optional[str] = Form(None),
        history: Optional[str] = Form(None),
    ):
        """
        Chat with database endpoint that supports multiple input methods.
        This endpoint will automatically extract and cache the schema if not already cached.

        `history` (optional): JSON string of prior turns, most recent last, e.g.
          [{"question": "...", "answer": "...", "sql": "..."}]
        The server keeps at most the last 5 entries.
        """
        temp_file_to_cleanup = None

        # Optional multi-turn context (cap enforced server-side)
        prior_turns = None
        if history:
            try:
                prior_turns = json.loads(history)
            except (json.JSONDecodeError, TypeError):
                raise HTTPException(status_code=400, detail="history must be a valid JSON array.")

        try:
            # Process database input
            db_uri, db_dialect, local_db_path, temp_file_to_cleanup = (
                DatabaseInputHandler.process_database_input(
                    db_file, db_path, db_url, db_connection_string
                )
            )

            # Extract and cache schema (if not already cached)
            schema_data = SchemaService.extract_and_cache_schema(
                db_uri, db_dialect, local_db_path
            )

            # Process the query
            response_data = QueryService.process_query(
                question, db_uri, db_dialect, schema_data, local_db_path, history=prior_turns
            )

            # Audit the interaction (EC-08). Never record credentials/connection strings.
            results = response_data.get("results")
            record_audit({
                "event": "chat",
                "request_id": request_id_var.get(),
                "dialect": db_dialect,
                "question": question[:500],
                "sql": (response_data.get("sql") or "")[:1000],
                "executed": bool(response_data.get("sql_executed")),
                "row_count": len(results) if isinstance(results, list) else 0,
                "truncated": bool(response_data.get("results_truncated")),
                "validator_rejected": bool(response_data.get("validator_rejected")),
                "latency_ms": response_data.get("latency_ms"),
            })

            return JSONResponse(content=response_data)

        except HTTPException:
            raise
        except Exception as e:
            logger.warning("internal error: %r", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error.")
        finally:
            # Cleanup temporary files
            if temp_file_to_cleanup:
                cleanup_temp_file(temp_file_to_cleanup)

    @app.get("/schema/cache", response_model=CacheResponse, dependencies=[Depends(require_api_key)])
    async def get_schema_cache_info():
        """Get information about cached schemas."""
        return get_cache_info()

    @app.delete("/schema/cache", response_model=ClearCacheResponse, dependencies=[Depends(require_api_key)])
    async def clear_schema_cache():
        """Clear all cached schemas."""
        return clear_cache()

    @app.get("/", response_model=APIInfo)
    async def root():
        """Root endpoint with API information."""
        settings = get_settings()
        return {
            "message": f"{settings.api_title} - Optimized with Schema Caching",
            "version": settings.api_version,
            "features": [
                "Automatic schema extraction and caching",
                "Separated schema extraction from query processing",
                "Support for SQLite (local files, uploads, URLs), PostgreSQL, and MySQL (connection strings)",
                "Real-time schema cache management",
                "Direct PostgreSQL/MySQL database querying without downloads",
                "Modular architecture with clean separation of concerns",
            ],
            "endpoints": {
                "chat": "/chat/ (POST) - Chat with database (auto-extracts schema)",
                "schema": "/schema/ (POST) - Extract and cache database schema",
                "schema_cache": "/schema/cache (GET) - View cached schemas",
                "clear_cache": "/schema/cache (DELETE) - Clear schema cache",
                "health": "/health (GET) - Health check",
                "docs": "/docs - API documentation",
                "openapi": "/openapi.json - OpenAPI specification",
            },
        }

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Readiness check (PR-08): settings must load and an LLM provider must be
        constructible. 503 only when the LLM provider cannot be built."""
        try:
            settings = get_settings()
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "message": f"Configuration could not be loaded: {type(e).__name__}."},
            )
        try:
            from llm.factory import get_provider

            get_provider()  # raises RuntimeError on missing/misconfigured LLM env
            llm_ok, reason = True, ""
        except Exception as e:
            llm_ok, reason = False, str(e)
        if not llm_ok:
            # Keep the message free of credential values — factory errors name env vars only.
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "message": f"LLM provider unavailable: {reason}"},
            )
        return {
            "status": "healthy",
            "message": "API is running",
            "version": settings.api_version,
        }
