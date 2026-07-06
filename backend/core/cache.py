# core/cache.py
"""Schema caching functionality."""

import time
from typing import Dict, Any, Optional

from .config import CACHE_EXPIRY_SECONDS

# Global schema cache
# Key: database_hash, Value: {schema_data, timestamp, db_path, db_uri}
schema_cache: Dict[str, Dict[str, Any]] = {}


def get_cached_schema(db_hash: str) -> Optional[Dict[str, Any]]:
    """Get cached schema if available and not expired."""
    if db_hash not in schema_cache:
        return None

    cached_data = schema_cache[db_hash]
    current_time = time.time()

    # Check if cache is expired
    if current_time - cached_data["timestamp"] > CACHE_EXPIRY_SECONDS:
        del schema_cache[db_hash]
        return None

    return cached_data["schema_data"]


def cache_schema(db_hash: str, schema_data: Dict[str, Any], db_path: str, db_uri: str) -> None:
    """Cache schema data."""
    schema_cache[db_hash] = {
        "schema_data": schema_data,
        "timestamp": time.time(),
        "db_path": db_path,
        "db_uri": db_uri,
    }


def get_cache_info() -> Dict[str, Any]:
    """Get information about cached schemas."""
    cache_info = []
    current_time = time.time()

    for db_hash, cached_data in schema_cache.items():
        age_seconds = current_time - cached_data["timestamp"]
        cache_info.append({
            "database_hash": db_hash,
            "database_path": cached_data["db_path"],
            "database_uri": cached_data["db_uri"],
            "cached_at": cached_data["timestamp"],
            "age_seconds": age_seconds,
            "expires_in_seconds": max(0, CACHE_EXPIRY_SECONDS - age_seconds),
            "tables": [
                table["table_name"]
                for table in cached_data["schema_data"].get("detailed_schema", [])
            ],
        })

    return {
        "cached_schemas": cache_info,
        "cache_expiry_seconds": CACHE_EXPIRY_SECONDS,
        "total_cached": len(cache_info),
    }


def clear_cache() -> Dict[str, Any]:
    """Clear all cached schemas."""
    cleared_count = len(schema_cache)
    schema_cache.clear()
    return {
        "message": f"Cleared {cleared_count} cached schemas",
        "cleared_count": cleared_count,
    }