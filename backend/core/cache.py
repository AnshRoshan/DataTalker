# core/cache.py
"""Schema caching — the single owner of in-memory schema cache state (ARCH-08).

Two layers share this module:
- the service-level cache (keyed by db_hash) that SchemaService checks before
  invoking the schema graph; this is what /schema/cache GET/DELETE exposes;
- the SchemaAgent's in-memory layer (keyed by the agent's own cache key), which
  used to be a private LRUCache and could diverge from the endpoint view.
  It now delegates here, so DELETE /schema/cache clears both.
"""
import time
from typing import Any, Dict, Optional

from .settings import get_settings

# Service-level cache. Key: database_hash, Value: {schema_data, timestamp, db_path, db_uri}
schema_cache: Dict[str, Dict[str, Any]] = {}

# SchemaAgent in-memory layer. Key: agent cache key,
# Value: {schema_data, mod_time (sqlite files), saved_at}
agent_cache: Dict[str, Dict[str, Any]] = {}


def get_cached_schema(db_hash: str) -> Optional[Dict[str, Any]]:
    """Get cached schema if available and not expired."""
    if db_hash not in schema_cache:
        return None

    cached_data = schema_cache[db_hash]
    current_time = time.time()

    # Check if cache is expired
    if current_time - cached_data["timestamp"] > get_settings().cache_ttl_seconds:
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


def get_agent_cached(key: str) -> Optional[Dict[str, Any]]:
    """SchemaAgent in-memory lookup, TTL-bounded via the entry's saved_at."""
    entry = agent_cache.get(key)
    if entry is None:
        return None
    if time.time() - entry.get("saved_at", 0) > get_settings().cache_ttl_seconds:
        del agent_cache[key]
        return None
    return entry


def set_agent_cached(key: str, schema_data: Dict[str, Any], mod_time: Optional[float]) -> None:
    """SchemaAgent in-memory store."""
    agent_cache[key] = {
        "schema_data": schema_data,
        "mod_time": mod_time,
        "saved_at": time.time(),
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
            "expires_in_seconds": max(0, get_settings().cache_ttl_seconds - age_seconds),
            "tables": [
                table["table_name"]
                for table in cached_data["schema_data"].get("detailed_schema", [])
            ],
        })

    return {
        "cached_schemas": cache_info,
        "cache_expiry_seconds": get_settings().cache_ttl_seconds,
        "total_cached": len(cache_info),
        "agent_cache_entries": len(agent_cache),
    }


def clear_cache() -> Dict[str, Any]:
    """Clear all cached schemas (service-level AND agent in-memory layer)."""
    cleared_count = len(schema_cache) + len(agent_cache)
    schema_cache.clear()
    agent_cache.clear()
    return {
        "message": f"Cleared {cleared_count} cached schemas",
        "cleared_count": cleared_count,
    }
