# api/endpoints.py
"""FastAPI route definitions."""

import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse

from .dependencies import DatabaseInputHandler, require_api_key
from .models import (
    SchemaResponse,
    QueryResponse,
    CacheResponse,
    ClearCacheResponse,
    HealthResponse,
    APIInfo,
    ConnectionCreate,
    ConnectionOut,
    ConnectionListResponse,
    ConnectionCheckResponse,
    LLMModelsResponse,
    LLMModelSelect,
    LLMModelSelection,
    AuthUser,
    GoogleCallback,
    ConversationIn,
    SavedQueryIn,
)
from services.schema_service import SchemaService
from services.query_service import QueryService
from core.audit import record_audit
from core.cache import get_cache_info, clear_cache
from core.connections import add_connection, delete_connection, list_connections, update_status
from core.preflight import check_connection
from core.schema_graph import build_schema_graph, subgraph
from core.file_handler import cleanup_temp_file
from core.logging_config import request_id_var
from core.settings import get_settings

logger = logging.getLogger(__name__)


def _claims(request: Request):
    """The verified session identity, or None on an unauthenticated install."""
    from core.auth import current_user

    return current_user(request)


def _owner(request: Request) -> str:
    from core.conversations import owner_of

    return owner_of(_claims(request))


def create_endpoints(app: FastAPI, serve_spa: bool = False) -> None:
    """Create and register all API endpoints.

    serve_spa: when the built frontend is being served from "/", the API info
    route is skipped so the SPA root wins (the mount is added after routes).
    """

    # ponytail: sync `def` (not async) so Starlette runs the blocking schema reflection in
    # its threadpool instead of stalling the event loop for every request (PR-02).
    @app.post("/schema/", response_model=SchemaResponse, dependencies=[Depends(require_api_key)])
    def extract_schema(
        db_file: Optional[UploadFile] = File(None),
        db_path: Optional[str] = Form(None),
        db_url: Optional[str] = Form(None),
        db_connection_string: Optional[str] = Form(None),
        connection_id: Optional[str] = Form(None),
    ):
        """
        Extract and cache database schema endpoint that supports multiple input methods:
        - File upload (db_file) - SQLite files only
        - Local file path (db_path) - SQLite files, must be absolute path
        - Remote URL (db_url) - Can be either:
          * Database connection string (postgresql://user:pass@host:port/dbname or sqlite:///path)
          * File download URL (for SQLite files, downloads and caches locally)
        - Connection string (db_connection_string) - any SQLAlchemy URL with its driver installed
        - Registered connection (connection_id) - lowest precedence; explicit db refs win
        """
        temp_file_to_cleanup = None

        try:
            # Process database input
            db_uri, db_dialect, local_db_path, temp_file_to_cleanup = (
                DatabaseInputHandler.process_database_input(
                    db_file, db_path, db_url, db_connection_string, connection_id
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
                "connection_id": connection_id,
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
        connection_id: Optional[str] = Form(None),
        history: Optional[str] = Form(None),
    ):
        """
        Chat with database endpoint that supports multiple input methods.
        This endpoint will automatically extract and cache the schema if not already cached.

        `history` (optional): JSON string of prior turns, most recent last, e.g.
          [{"question": "...", "answer": "...", "sql": "..."}]
        The server keeps at most the last 5 entries.
        `connection_id` (optional): a registered connection from /connections/ —
        lowest precedence; explicit db refs win.
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
                    db_file, db_path, db_url, db_connection_string, connection_id
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
                "connection_id": connection_id,
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

    @app.post("/schema/graph/", dependencies=[Depends(require_api_key)])
    def schema_graph_endpoint(
        db_file: Optional[UploadFile] = File(None),
        db_path: Optional[str] = Form(None),
        db_url: Optional[str] = Form(None),
        db_connection_string: Optional[str] = Form(None),
        connection_id: Optional[str] = Form(None),
    ):
        """
        Schema relationship graph for the frontend visual explorer. Accepts the
        same DB-reference form fields as /schema/ (plus connection_id). Derived
        on demand from the cached schema via core/schema_graph.py (explicit FK
        edges + inferred joins). Nodes are capped at 200 for gigantic schemas
        (truncated: true).
        """
        temp_file_to_cleanup = None
        try:
            db_uri, db_dialect, local_db_path, temp_file_to_cleanup = (
                DatabaseInputHandler.process_database_input(
                    db_file, db_path, db_url, db_connection_string, connection_id
                )
            )
            schema_data = SchemaService.extract_and_cache_schema(
                db_uri, db_dialect, local_db_path
            )
            detailed = schema_data.get("detailed_schema", [])
            graph = build_schema_graph(detailed)

            max_nodes = 200
            truncated = len(graph["nodes"]) > max_nodes
            if truncated:
                keep = {n["id"] for n in graph["nodes"][:max_nodes]}
                graph = subgraph(graph, keep)

            # Never echo the URI/path back (SEC-05).
            return JSONResponse(content={
                "dialect": db_dialect,
                "nodes": graph["nodes"],
                "edges": graph["edges"],
                "table_count": len(detailed),
                "truncated": truncated,
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("internal error: %r", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error.")
        finally:
            if temp_file_to_cleanup and not db_file:
                cleanup_temp_file(temp_file_to_cleanup)

    @app.get("/connections/", response_model=ConnectionListResponse,
             dependencies=[Depends(require_api_key)])
    def list_connections_endpoint():
        """List registered connections. Full connection strings are NEVER
        returned — only a password-masked URI (SEC-05)."""
        connections = list_connections()
        for conn in connections:
            status = conn.get("last_status") or {}
            ok = isinstance(status, dict) and status.get("ok")
            conn["dialect"] = status.get("dialect") if ok else None
            conn["table_count"] = status.get("table_count") if ok else None
        return JSONResponse(content={"connections": connections, "total": len(connections)})

    @app.post("/connections/", response_model=ConnectionOut, status_code=201,
              dependencies=[Depends(require_api_key)])
    def create_connection_endpoint(body: ConnectionCreate):
        """Register a connection. The preflight (core/preflight.py) must pass —
        failed checks are rejected with the structured error, nothing is stored."""
        name = body.name.strip()
        connection_string = body.connection_string.strip()
        if not name or not connection_string:
            raise HTTPException(status_code=400, detail="name and connection_string are required.")
        status = check_connection(connection_string)
        if not status.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=status.get("error", "Connection check failed."),
            )
        record = add_connection(name, connection_string, notes=body.notes or "", status=status)
        return JSONResponse(content=record)

    @app.delete("/connections/{connection_id}", dependencies=[Depends(require_api_key)])
    def delete_connection_endpoint(connection_id: str):
        if not delete_connection(connection_id):
            raise HTTPException(
                status_code=404,
                detail="Unknown connection_id: no registered connection with that id.",
            )
        return JSONResponse(content={"message": "Connection deleted.", "id": connection_id})

    @app.post("/connections/{connection_id}/check", response_model=ConnectionCheckResponse,
              dependencies=[Depends(require_api_key)])
    def check_connection_endpoint(connection_id: str):
        """Re-run the preflight for a registered connection and update its status."""
        from core.connections import get_connection

        record = get_connection(connection_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail="Unknown connection_id: no registered connection with that id.",
            )
        status = check_connection(str(record["connection_string"]))
        updated = update_status(connection_id, status)
        return JSONResponse(content={
            "id": connection_id,
            "last_checked_at": (updated or {}).get("last_checked_at"),
            "last_status": status,
        })

    # ------------------------------------------------------------------ auth
    # Public (no Bearer gate) by design: these are how a visitor becomes someone.

    @app.get("/auth/config")
    async def auth_config():
        """What the browser needs to render a sign-in button. Never a secret."""
        s = get_settings()
        return {
            "google_enabled": bool(s.google_client_id),
            "client_id": s.google_client_id or None,
            "require_login": s.require_login,
            "api_key_required": s.require_api_key,
        }

    @app.post("/auth/google", response_model=AuthUser)
    async def auth_google(body: GoogleCallback, request: Request, response: Response):
        """Verify a Google ID token and start a signed session."""
        from core.auth import (
            SESSION_COOKIE,
            SESSION_TTL_SECONDS,
            create_session_token,
            safe_user,
            verify_google_id_token,
        )

        user = verify_google_id_token(body.credential)
        payload = safe_user(user)
        record_audit({"event": "sign_in", "request_id": request_id_var.get(), "email": payload["email"]})

        response.set_cookie(
            SESSION_COOKIE,
            create_session_token(user),
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            samesite="lax",
            # Proxies terminate TLS, so trust the forwarded scheme; a Secure cookie that
            # the browser drops because the visible origin is http is the worse failure.
            secure=(request.headers.get("x-forwarded-proto") or request.url.scheme).startswith("https"),
            path="/",
        )
        return payload

    @app.get("/auth/me")
    async def auth_me(request: Request):
        from core.auth import current_user, safe_user

        claims = current_user(request)
        return {"authenticated": claims is not None, "user": safe_user(claims) if claims else None}

    @app.post("/auth/logout", status_code=204)
    async def auth_logout(response: Response):
        from core.auth import SESSION_COOKIE

        response.delete_cookie(SESSION_COOKIE, path="/")
        return Response(status_code=204)

    @app.get("/llm/models", response_model=LLMModelsResponse, dependencies=[Depends(require_api_key)])
    def list_llm_models_endpoint():
        """Which models the configured provider serves — OpenRouter or any
        OpenAI-compatible gateway exposes its whole catalog through one key.
        Listing failures come back as an empty list, never a 500."""
        from llm.selection import list_models

        return list_models()

    @app.post("/llm/model", response_model=LLMModelSelection, dependencies=[Depends(require_api_key)])
    def select_llm_model_endpoint(body: LLMModelSelect):
        """Pick the model used by subsequent questions. The provider (and therefore
        the base URL and key) stays operator config; only the model id changes."""
        from llm.selection import SelectionError, provider_name, set_selected_model

        try:
            model = set_selected_model(body.model)
        except SelectionError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return JSONResponse(content={"provider": provider_name(), "model": model})

    @app.delete("/llm/model", response_model=LLMModelSelection, dependencies=[Depends(require_api_key)])
    def clear_llm_model_endpoint():
        """Drop the runtime pick and fall back to LLM_MODEL from the environment."""
        from llm.selection import clear_selected_model, provider_name

        clear_selected_model()
        return JSONResponse(content={"provider": provider_name(), "model": None})

    # ------------------------------------------------------------- SQL console
    @app.post("/sql/", dependencies=[Depends(require_api_key)])
    def run_sql_console(
        request: Request,
        sql: str = Form(...),
        db_file: Optional[UploadFile] = File(None),
        db_path: Optional[str] = Form(None),
        db_url: Optional[str] = Form(None),
        db_connection_string: Optional[str] = Form(None),
        connection_id: Optional[str] = Form(None),
    ):
        """Run a hand-written statement through the same read-only guard as the chat
        path. Rejected statements come back as a 200 with the reason, because a refusal
        is a normal, useful result here rather than a client error."""
        from core.file_handler import cleanup_temp_file
        from services.sql_service import SqlConsoleService

        temp_file_to_cleanup = None
        started = time.perf_counter()
        try:
            db_uri, db_dialect, local_db_path, temp_file_to_cleanup = (
                DatabaseInputHandler.process_database_input(
                    db_file, db_path, db_url, db_connection_string, connection_id
                )
            )
            schema_data = SchemaService.extract_and_cache_schema(db_uri, db_dialect, local_db_path)
            result = SqlConsoleService.run(
                sql, db_uri, db_dialect, masked_columns=schema_data.get("masked_columns")
            )
            record_audit({
                "event": "sql_console",
                "request_id": request_id_var.get(),
                "dialect": db_dialect,
                "sql": (result.get("sql") or "")[:1000],
                "executed": bool(result.get("sql_executed")),
                "validator_rejected": bool(result.get("validator_rejected")),
                "row_count": result.get("row_count", 0),
                "truncated": bool(result.get("results_truncated")),
                "connection_id": connection_id,
                "latency_ms": result.get("latency_ms")
                or round((time.perf_counter() - started) * 1000),
                "owner": _owner(request),
            })
            return JSONResponse(content=result)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("internal error: %r", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error.")
        finally:
            if temp_file_to_cleanup:
                cleanup_temp_file(temp_file_to_cleanup)

    # --------------------------------------------------------- conversations
    @app.get("/conversations/", dependencies=[Depends(require_api_key)])
    def list_conversations_endpoint(request: Request):
        """Header rows for the caller's threads — titles and counts, no message bodies."""
        from core.conversations import list_conversations, owner_of

        conversations = list_conversations(owner_of(_claims(request)))
        return JSONResponse(content={"conversations": conversations, "total": len(conversations)})

    @app.get("/conversations/{conversation_id}", dependencies=[Depends(require_api_key)])
    def get_conversation_endpoint(request: Request, conversation_id: str):
        from core.conversations import get_conversation, owner_of

        thread = get_conversation(conversation_id, owner_of(_claims(request)))
        if thread is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return JSONResponse(content=thread)

    @app.post("/conversations/", dependencies=[Depends(require_api_key)])
    def save_conversation_endpoint(request: Request, body: ConversationIn):
        from core.conversations import owner_of, save_conversation

        header = save_conversation(
            conversation_id=body.id, messages=body.messages,
            owner=owner_of(_claims(request)), source=body.source,
        )
        return JSONResponse(content=header)

    @app.delete("/conversations/{conversation_id}", dependencies=[Depends(require_api_key)])
    def delete_conversation_endpoint(request: Request, conversation_id: str):
        from core.conversations import delete_conversation, owner_of

        if not delete_conversation(conversation_id, owner_of(_claims(request))):
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return JSONResponse(content={"message": "Conversation deleted.", "id": conversation_id})

    # ---------------------------------------------------------- saved queries
    @app.get("/queries/", dependencies=[Depends(require_api_key)])
    def list_saved_endpoint(request: Request):
        from core.saved_queries import ANONYMOUS, list_saved

        queries = list_saved(_owner(request) or ANONYMOUS)
        return JSONResponse(content={"queries": queries, "total": len(queries)})

    @app.post("/queries/", dependencies=[Depends(require_api_key)])
    def save_query_endpoint(request: Request, body: SavedQueryIn):
        from core.saved_queries import ANONYMOUS, save_query

        try:
            record = save_query(
                query_id=body.id, name=body.name, sql=body.sql, dialect=body.dialect,
                owner=_owner(request) or ANONYMOUS, source=body.source,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except KeyError:
            raise HTTPException(status_code=404, detail="Query not found.")
        return JSONResponse(content=record, status_code=201)

    @app.delete("/queries/{query_id}", dependencies=[Depends(require_api_key)])
    def delete_saved_endpoint(request: Request, query_id: str):
        from core.saved_queries import ANONYMOUS, delete_saved

        if not delete_saved(query_id, _owner(request) or ANONYMOUS):
            raise HTTPException(status_code=404, detail="Query not found.")
        return JSONResponse(content={"message": "Query deleted.", "id": query_id})

    @app.post("/queries/{query_id}/run", dependencies=[Depends(require_api_key)])
    def mark_query_run_endpoint(request: Request, query_id: str):
        """Records that a library entry was re-run; the statement itself executes
        through /sql/, so this endpoint cannot run anything."""
        from core.saved_queries import ANONYMOUS, mark_run

        record = mark_run(query_id, _owner(request) or ANONYMOUS)
        if record is None:
            raise HTTPException(status_code=404, detail="Query not found.")
        return JSONResponse(content=record)

    # ----------------------------------------------------------------- insights
    @app.get("/stats", dependencies=[Depends(require_api_key)])
    async def stats_endpoint(window_days: int = 14):
        """Usage, safety and latency aggregates read straight from the audit log."""
        from core.stats import summarize

        return summarize(window_days=max(1, min(window_days, 90)))

    @app.get("/history", dependencies=[Depends(require_api_key)])
    async def history_endpoint(limit: int = 100):
        from core.stats import recent_history

        return {"history": recent_history(max(1, min(limit, 500)))}

    @app.get("/schema/cache", response_model=CacheResponse, dependencies=[Depends(require_api_key)])
    async def get_schema_cache_info():
        """Get information about cached schemas."""
        return get_cache_info()

    @app.delete("/schema/cache", response_model=ClearCacheResponse, dependencies=[Depends(require_api_key)])
    async def clear_schema_cache():
        """Clear all cached schemas."""
        return clear_cache()

    if not serve_spa:
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
                    "schema_graph": "/schema/graph/ (POST) - Schema relationship graph for the visual explorer",
                    "connections_list": "/connections/ (GET) - List registered database connections",
                    "connections_create": "/connections/ (POST) - Register a database connection (preflight-validated)",
                    "connections_delete": "/connections/{id} (DELETE) - Remove a registered connection",
                    "connections_check": "/connections/{id}/check (POST) - Re-run the connection preflight",
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
        from llm.selection import provider_name

        try:
            from llm.factory import get_provider

            provider = get_provider()  # raises RuntimeError on missing/misconfigured LLM env
        except Exception as e:
            # No operator key is a supported shape, not a broken deployment: every caller
            # may bring their own (X-LLM-Provider / X-LLM-Key), so this instance answers
            # for them. Report that mode instead of failing readiness — but say so plainly.
            return {
                "status": "healthy",
                "message": "API is running (no operator LLM key; callers must bring their own)",
                "version": settings.api_version,
                "llm_mode": "byok-only",
                "llm_provider": None,
                "llm_model": None,
                "auth": "required" if settings.require_api_key else "disabled",
            }

        return {
            "status": "healthy",
            "message": "API is running",
            "version": settings.api_version,
            "llm_mode": "operator-or-byok",
            "llm_provider": provider_name(),
            "llm_model": getattr(provider, "model", None),
            "auth": "required" if settings.require_api_key else "disabled",
        }
