# core/file_handler.py
"""File upload and download handling utilities."""

import os
import logging
import socket
import ipaddress
import tempfile
import requests
from pathlib import Path
from urllib.parse import urlparse
from fastapi import HTTPException, UploadFile

from .settings import get_settings

logger = logging.getLogger(__name__)

_CHUNK = 65536


def validate_file_extension(filename: str) -> bool:
    """Validate file extension."""
    if not filename:
        return False
    return Path(filename).suffix.lower() in get_settings().allowed_extensions_list


def save_uploaded_file(db_file: UploadFile) -> str:
    """Save an uploaded DB to a unique temp file, enforcing the size cap (PR-11, CORR-2)."""
    settings = get_settings()
    allowed = settings.allowed_extensions_list
    if not db_file.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    if not validate_file_extension(db_file.filename):
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(allowed)}")

    fd, temp_file = tempfile.mkstemp(prefix=f"{settings.temp_file_prefix}uploaded_", suffix=Path(db_file.filename).suffix.lower())
    try:
        written = 0
        with os.fdopen(fd, "wb") as buffer:
            while True:
                chunk = db_file.file.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_file_size_bytes:
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds the size limit.")
                buffer.write(chunk)
        return temp_file
    except HTTPException:
        cleanup_temp_file(temp_file)
        raise
    except Exception as e:
        cleanup_temp_file(temp_file)
        logger.error("upload error: %r", e)
        raise HTTPException(status_code=500, detail="Failed to save the uploaded file.")


def is_url_fetch_safe(url: str):
    """Reject non-http(s) URLs and any host resolving to an internal address (SSRF guard, SEC-03)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "Only http(s) URLs are allowed."
    host = parsed.hostname
    if not host:
        return False, "URL has no host."
    try:
        try:
            ips = [ipaddress.ip_address(host)]  # literal IP
        except ValueError:
            ips = [ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)]
    except Exception:
        return False, "Could not resolve the URL host."
    for ip in ips:
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False, "URL resolves to a disallowed (internal) address."
    return True, "OK"


def download_database_from_url(db_url: str) -> str:
    """Download a DB from a public URL into a unique temp file (SSRF-guarded, size-capped, no redirects)."""
    safe, reason = is_url_fetch_safe(db_url)
    if not safe:
        raise HTTPException(status_code=400, detail=reason)

    fd, temp_file = tempfile.mkstemp(prefix=f"{get_settings().temp_file_prefix}downloaded_", suffix=".db")
    try:
        with requests.get(db_url, timeout=get_settings().request_timeout_seconds, stream=True, allow_redirects=False) as response:
            if 300 <= response.status_code < 400:
                raise HTTPException(status_code=400, detail="Redirects are not allowed for database URLs.")
            response.raise_for_status()
            written = 0
            with os.fdopen(fd, "wb") as f:
                for chunk in response.iter_content(chunk_size=_CHUNK):
                    written += len(chunk)
                    if written > get_settings().max_file_size_bytes:
                        raise HTTPException(status_code=413, detail="Downloaded file exceeds the size limit.")
                    f.write(chunk)
        return temp_file
    except HTTPException:
        cleanup_temp_file(temp_file)
        raise
    except requests.RequestException as e:
        cleanup_temp_file(temp_file)
        logger.warning("download error: %r", e)
        raise HTTPException(status_code=400, detail="Failed to download the database from the URL.")
    except Exception as e:
        cleanup_temp_file(temp_file)
        logger.warning("download error: %r", e)
        raise HTTPException(status_code=500, detail="Error processing the database URL.")


def cleanup_temp_file(file_path: str) -> None:
    """Safely cleanup a temporary file."""
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except Exception as e:
            logger.debug("Failed to cleanup temporary file %s: %s", file_path, e)
