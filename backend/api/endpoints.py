# api/endpoints.py
"""FastAPI route definitions."""

from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse

from .dependencies import DatabaseInputHandler, require_api_key
from .models import SchemaResponse, QueryResponse, CacheResponse, ClearCacheResponse, HealthResponse, APIInfo
from services.schema_service import SchemaService
from services.query_service import QueryService
from core.cache import get_cache_info, clear_cache
from core.file_handler import cleanup_temp_file
from core.config import API_TITLE, API_VERSION


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
        - Connection string (db_connection_string) - SQLite (sqlite:///path) or PostgreSQL (postgresql://user:pass@host:port/dbname)
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
            schema_data = SchemaService.extract_and_cache_schema(
                db_uri, db_dialect, local_db_path
            )

            # Prepare response
            # ponytail: do NOT echo database_uri/path back — a postgresql:// URI leaks the
            # password to the client (SEC-05).
            response_data = {
                "message": "Schema extracted and cached successfully",
                "database_dialect": db_dialect,
                "tables": SchemaService.get_schema_tables(schema_data),
                "schema_description": schema_data.get("schema_description", ""),
                "cached": True,
            }

            return JSONResponse(content=response_data)

        except HTTPException:
            raise
        except Exception as e:
            print(f"[endpoints] internal error: {e!r}")
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
    ):
        """
        Chat with database endpoint that supports multiple input methods.
        This endpoint will automatically extract and cache the schema if not already cached.
        """
        temp_file_to_cleanup = None
        
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
                question, db_uri, db_dialect, schema_data, local_db_path
            )

            return JSONResponse(content=response_data)

        except HTTPException:
            raise
        except Exception as e:
            print(f"[endpoints] internal error: {e!r}")
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
        return {
            "message": f"{API_TITLE} - Optimized with Schema Caching",
            "version": API_VERSION,
            "features": [
                "Automatic schema extraction and caching",
                "Separated schema extraction from query processing",
                "Support for SQLite (local files, uploads, URLs) and PostgreSQL (connection strings)",
                "Real-time schema cache management",
                "Direct PostgreSQL database querying without downloads",
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
        """Health check endpoint."""
        return {"status": "healthy", "message": "API is running"}