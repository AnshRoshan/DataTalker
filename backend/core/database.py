# core/database.py
"""Database connection and validation utilities."""

import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException

from .config import SUPPORTED_DIALECTS

# db_path is confined to this directory (defaults to backend/, which ships the sample DBs).
# Override with the DATATALKER_DB_DIR env var to point at your own data directory.
_DEFAULT_DB_DIR = str(Path(__file__).resolve().parent.parent)


def is_absolute_path(path: str) -> bool:
    """Check if a path is absolute."""
    if not path:
        return False
    
    # Check for Windows absolute paths (C:\, D:\, etc.)
    if len(path) >= 3 and path[1:3] == ":\\" and path[0].isalpha():
        return True
    
    # Check for Unix/Linux absolute paths (starting with /)
    if path.startswith("/"):
        return True
    
    # Check for UNC paths (\\server\share)
    if path.startswith("\\\\"):
        return True
    
    return False


def validate_database_path(db_path: str) -> str:
    """Validate db_path and confine it to the allowed directory (SEC-04)."""
    if not db_path:
        raise HTTPException(status_code=400, detail="Database path cannot be empty")

    if not is_absolute_path(db_path):
        raise HTTPException(
            status_code=400,
            detail="Database path must be absolute (e.g. C:\\path\\to\\file.db or /path/to/file.db)",
        )

    real = os.path.realpath(db_path)
    base = os.path.realpath(os.getenv("DATATALKER_DB_DIR", _DEFAULT_DB_DIR))
    try:
        inside = os.path.commonpath([base, real]) == base
    except ValueError:
        inside = False  # different drive on Windows
    if not inside:
        # generic message — do not echo the path back (SEC-04 enumeration aid)
        raise HTTPException(status_code=403, detail="Database path is outside the allowed directory.")
    if not os.path.isfile(real):
        raise HTTPException(status_code=404, detail="Database file not found or not accessible.")

    return real


def parse_connection_string(connection_string: str) -> Tuple[str, str, Optional[str]]:
    """Parse connection string and return (db_uri, db_dialect, db_path)."""
    if connection_string.startswith("sqlite:///"):
        # SQLite connection string
        path_part = connection_string[10:]  # Remove "sqlite:///"
        local_db_path = validate_database_path(path_part)
        return connection_string, "sqlite", local_db_path
    elif connection_string.startswith(("postgresql://", "postgres://")):
        # PostgreSQL connection string
        return connection_string, "postgresql", None
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported connection string format. Supported: sqlite:///path/to/file.db, postgresql://user:pass@host:port/dbname",
        )


def is_database_connection_url(url: str) -> bool:
    """Check if URL is a database connection string rather than a file download URL."""
    return url.startswith(("postgresql://", "postgres://", "sqlite:///"))


def generate_database_hash(db_uri: str, db_path: Optional[str] = None) -> str:
    """Generate a hash for the database based on URI and modification time (for files)."""
    try:
        if db_path and os.path.exists(db_path):
            # For file-based databases (SQLite), use path and modification time
            stat = os.stat(db_path)
            hash_input = f"{db_uri}:{stat.st_mtime}:{stat.st_size}"
        else:
            # For remote databases (PostgreSQL), use just the URI
            hash_input = db_uri
        return hashlib.md5(hash_input.encode()).hexdigest()
    except Exception:
        # Fallback to just URI hash if stat fails
        return hashlib.md5(db_uri.encode()).hexdigest()


def validate_database_dialect(dialect: str) -> str:
    """Validate database dialect."""
    if dialect not in SUPPORTED_DIALECTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported database dialect: {dialect}. Supported: {', '.join(SUPPORTED_DIALECTS)}"
        )
    return dialect