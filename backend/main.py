# main.py
"""
Talk to DB API - Refactored and Modular

A FastAPI application for chatting with databases using natural language.
This version features a clean, modular architecture with separated concerns.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.settings import get_settings
from core.logging_config import configure_logging, RequestContextMiddleware
from core.ratelimit import RateLimitMiddleware
from api.endpoints import create_endpoints

logger = logging.getLogger(__name__)

# Built frontend (frontend/dist). When present, the API serves the SPA itself so the
# Docker image is a complete one-container app. A catch-all StaticFiles mount is added
# AFTER the API routes, so every /chat /schema /connections route still wins, and any
# other path (/, /favicon.svg, /assets/*) serves from dist with index.html fallback.
def _mount_spa(app: FastAPI) -> bool:
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        return False
    app.mount("/", StaticFiles(directory=dist, html=True), name="spa")
    logger.info("serving frontend SPA from %s", dist)
    return True


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    configure_logging()
    settings = get_settings()

    # Create FastAPI app
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware (behavior identical to the pre-settings constants)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=[settings.cors_allow_methods],
        allow_headers=[settings.cors_allow_headers],
    )
    # Per-request correlation id + structured request logging
    app.add_middleware(RequestContextMiddleware)
    # Bring-your-own LLM key: bind X-LLM-* headers to this request, cleared on exit
    from llm.request_provider import LlmCredentialsMiddleware

    app.add_middleware(LlmCredentialsMiddleware)
    # Sliding-window rate limit on POST /chat/ + /schema/ (PR-09)
    app.add_middleware(RateLimitMiddleware)

    # Register API endpoints first (skipping the API root when the SPA owns "/"),
    # then the SPA catch-all mount (order matters: a "/" mount registered first
    # would shadow every API route).
    dist_index = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
    create_endpoints(app, serve_spa=dist_index.is_file())
    _mount_spa(app)

    return app


# Create the FastAPI app instance
fastapi_app = create_app()

# For backwards compatibility
app = fastapi_app


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    logger.info("Starting %s v%s", settings.api_title, settings.api_version)

    uvicorn.run(
        "main:fastapi_app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
