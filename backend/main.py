# main.py
"""
Talk to DB API - Refactored and Modular

A FastAPI application for chatting with databases using natural language.
This version features a clean, modular architecture with separated concerns.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.settings import get_settings
from core.logging_config import configure_logging, RequestContextMiddleware
from core.ratelimit import RateLimitMiddleware
from api.endpoints import create_endpoints

logger = logging.getLogger(__name__)


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
    # Sliding-window rate limit on POST /chat/ + /schema/ (PR-09)
    app.add_middleware(RateLimitMiddleware)

    # Register endpoints
    create_endpoints(app)

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
