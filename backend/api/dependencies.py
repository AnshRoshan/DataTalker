# api/dependencies.py
"""FastAPI dependencies for handling database inputs."""

import os
import secrets
from typing import Tuple, Optional
from fastapi import Form, File, UploadFile, HTTPException, Header

from core.database import parse_connection_string, is_database_connection_url, validate_database_path
from core.file_handler import save_uploaded_file, download_database_from_url


def require_api_key(authorization: Optional[str] = Header(None)) -> None:
    """Gate data routes on a shared API key. Deny by default if none is configured.

    ponytail: a single env-configured key (matches the Bearer token the frontend already
    sends). Per-user auth / RBAC is a later phase; this just closes the open data plane.
    """
    expected = os.getenv("DATATALKER_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Server authentication is not configured (set DATATALKER_API_KEY).")
    if not authorization or not secrets.compare_digest(authorization, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


class DatabaseInputHandler:
    """Handler for processing different database input methods."""
    
    @staticmethod
    def process_database_input(
        db_file: Optional[UploadFile] = File(None),
        db_path: Optional[str] = Form(None),
        db_url: Optional[str] = Form(None),
        db_connection_string: Optional[str] = Form(None),
    ) -> Tuple[str, str, Optional[str], Optional[str]]:
        """
        Process database input and return (db_uri, db_dialect, local_db_path, temp_file_to_cleanup).
        
        Priority order: db_connection_string > db_path > db_file > db_url
        """
        db_uri = None
        db_dialect = None
        local_db_path = None
        temp_file_to_cleanup = None

        if db_connection_string:
            # Handle connection string
            db_uri, db_dialect, local_db_path = parse_connection_string(db_connection_string)

        elif db_path:
            # Handle local file path (SQLite)
            local_db_path = validate_database_path(db_path)
            db_uri = f"sqlite:///{local_db_path}"
            db_dialect = "sqlite"

        elif db_file:
            # Handle file upload (SQLite)
            temp_file_to_cleanup = save_uploaded_file(db_file)
            local_db_path = temp_file_to_cleanup
            db_uri = f"sqlite:///{local_db_path}"
            db_dialect = "sqlite"

        elif db_url:
            # Check if URL is a database connection string or a file download URL
            if is_database_connection_url(db_url):
                # Handle as database connection string
                db_uri, db_dialect, local_db_path = parse_connection_string(db_url)
            else:
                # Handle URL download (SQLite only)
                temp_file_to_cleanup = download_database_from_url(db_url)
                local_db_path = temp_file_to_cleanup
                db_uri = f"sqlite:///{local_db_path}"
                db_dialect = "sqlite"

        else:
            raise HTTPException(
                status_code=400,
                detail="No database provided. Use 'db_connection_string', 'db_path', 'db_file', or 'db_url'.",
            )

        return db_uri, db_dialect, local_db_path, temp_file_to_cleanup