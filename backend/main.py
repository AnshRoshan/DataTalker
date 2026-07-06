# main.py
"""
Talk to DB API - Refactored and Modular

A FastAPI application for chatting with databases using natural language.
This version features a clean, modular architecture with separated concerns.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import (
    API_TITLE,
    API_VERSION,
    CORS_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_METHODS,
    CORS_ALLOW_HEADERS,
)
from api.endpoints import create_endpoints


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    # Create FastAPI app
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description="API for chatting with databases using natural language",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )

    # Register endpoints
    create_endpoints(app)

    return app


# Create the FastAPI app instance
fastapi_app = create_app()

# For backwards compatibility
app = fastapi_app


if __name__ == "__main__":
    import uvicorn

    print(f"Starting {API_TITLE} v{API_VERSION}")
    print("Features:")
    print("- Modular architecture with clean separation of concerns")
    print("- Schema extraction and caching")
    print("- Support for SQLite and PostgreSQL")
    print("- Natural language to SQL conversion")
    print("- File upload and URL download support")
    print()

    uvicorn.run(
        "main:fastapi_app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
