"""
Enterprise Redis Caching Layer
Multi-layer caching for schema, queries, and LLM responses
"""

import redis.asyncio as redis
import json
import pickle
import hashlib
import asyncio
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import logging

from core.config import settings
from core.monitoring import get_logger, track_performance


logger = get_logger(__name__)


class CacheManager:
    """Enterprise-grade caching with Redis backend"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Any] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0
        }
    
    async def initialize(self) -> None:
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.cache.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We'll handle encoding ourselves
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            logger.warning("Falling back to local memory cache")
            self.redis_client = None
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis cache connection closed")
    
    def _generate_cache_key(self, prefix: str, key: str) -> str:
        """Generate consistent cache key"""
        return f"{settings.cache.CACHE_PREFIX}:{prefix}:{key}"
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for caching"""
        try:
            # Try JSON first for simple types
            if isinstance(data, (dict, list, str, int, float, bool, type(None))):
                return json.dumps(data, default=str).encode('utf-8')
            else:
                # Fall back to pickle for complex objects
                return pickle.dumps(data)
        except Exception as e:
            logger.error(f"Failed to serialize cache data: {e}")
            return pickle.dumps(data)
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize cached data"""
        try:
            # Try JSON first
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                # Fall back to pickle
                return pickle.loads(data)
            except Exception as e:
                logger.error(f"Failed to deserialize cache data: {e}")
                return None
    
    @track_performance("cache_get")
    async def get(self, prefix: str, key: str) -> Optional[Any]:
        """Get value from cache with fallback to local cache"""
        cache_key = self._generate_cache_key(prefix, key)
        
        try:
            # Try Redis first
            if self.redis_client:
                data = await self.redis_client.get(cache_key)
                if data:
                    self.cache_stats["hits"] += 1
                    logger.debug(f"Cache hit (Redis): {cache_key}")
                    return self._deserialize_data(data)
            
            # Try local cache
            if cache_key in self.local_cache:
                entry = self.local_cache[cache_key]
                if entry["expires_at"] > datetime.utcnow():
                    self.cache_stats["hits"] += 1
                    logger.debug(f"Cache hit (local): {cache_key}")
                    return entry["data"]
                else:
                    # Remove expired entry
                    del self.local_cache[cache_key]
            
            self.cache_stats["misses"] += 1
            logger.debug(f"Cache miss: {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    @track_performance("cache_set")
    async def set(self, prefix: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        cache_key = self._generate_cache_key(prefix, key)
        
        try:
            serialized_data = self._serialize_data(value)
            
            # Set in Redis
            if self.redis_client:
                ttl_seconds = ttl or self._get_default_ttl(prefix)
                await self.redis_client.setex(cache_key, ttl_seconds, serialized_data)
                logger.debug(f"Cache set (Redis): {cache_key}, TTL: {ttl_seconds}s")
            
            # Set in local cache as backup
            if len(self.local_cache) < settings.cache.MAX_CACHE_SIZE:
                ttl_seconds = ttl or self._get_default_ttl(prefix)
                expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
                self.local_cache[cache_key] = {
                    "data": value,
                    "expires_at": expires_at
                }
                logger.debug(f"Cache set (local): {cache_key}")
            
            self.cache_stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, prefix: str, key: str) -> bool:
        """Delete value from cache"""
        cache_key = self._generate_cache_key(prefix, key)
        
        try:
            # Delete from Redis
            if self.redis_client:
                await self.redis_client.delete(cache_key)
            
            # Delete from local cache
            if cache_key in self.local_cache:
                del self.local_cache[cache_key]
            
            logger.debug(f"Cache delete: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def clear_prefix(self, prefix: str) -> int:
        """Clear all keys with given prefix"""
        try:
            pattern = self._generate_cache_key(prefix, "*")
            count = 0
            
            # Clear from Redis
            if self.redis_client:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    count = await self.redis_client.delete(*keys)
            
            # Clear from local cache
            local_keys = [k for k in self.local_cache.keys() if k.startswith(f"{settings.cache.CACHE_PREFIX}:{prefix}:")]
            for key in local_keys:
                del self.local_cache[key]
                count += 1
            
            logger.info(f"Cleared {count} cache entries with prefix: {prefix}")
            return count
            
        except Exception as e:
            logger.error(f"Cache clear prefix error: {e}")
            return 0
    
    def _get_default_ttl(self, prefix: str) -> int:
        """Get default TTL for cache prefix"""
        ttl_mapping = {
            "schema": settings.cache.SCHEMA_CACHE_TTL,
            "query": settings.cache.QUERY_CACHE_TTL,
            "result": settings.cache.RESULT_CACHE_TTL,
            "llm": settings.cache.LLM_CACHE_TTL
        }
        return ttl_mapping.get(prefix, 300)  # Default 5 minutes
    
    async def cleanup_expired(self) -> int:
        """Clean up expired local cache entries"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.local_cache.items()
            if entry["expires_at"] <= now
        ]
        
        for key in expired_keys:
            del self.local_cache[key]
            self.cache_stats["evictions"] += 1
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    # Specialized cache methods
    
    async def get_schema(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached schema information"""
        return await self.get("schema", key)
    
    async def set_schema(self, key: str, schema_data: Dict[str, Any]) -> bool:
        """Cache schema information"""
        return await self.set("schema", key, schema_data, settings.cache.SCHEMA_CACHE_TTL)
    
    async def get_query_result(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached query result"""
        return await self.get("result", query_hash)
    
    async def set_query_result(self, query_hash: str, result_data: Dict[str, Any]) -> bool:
        """Cache query result"""
        return await self.set("result", query_hash, result_data, settings.cache.RESULT_CACHE_TTL)
    
    async def get_llm_response(self, prompt_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached LLM response"""
        return await self.get("llm", prompt_hash)
    
    async def set_llm_response(self, prompt_hash: str, response_data: Dict[str, Any]) -> bool:
        """Cache LLM response"""
        return await self.set("llm", prompt_hash, response_data, settings.cache.LLM_CACHE_TTL)
    
    async def invalidate_schema_cache(self) -> int:
        """Invalidate all schema cache entries"""
        return await self.clear_prefix("schema")
    
    async def invalidate_query_cache(self) -> int:
        """Invalidate all query result cache entries"""
        return await self.clear_prefix("result")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            **self.cache_stats,
            "hit_rate_percentage": round(hit_rate, 2),
            "local_cache_size": len(self.local_cache),
            "redis_connected": self.redis_client is not None
        }
        
        # Get Redis info if available
        if self.redis_client:
            try:
                redis_info = await self.redis_client.info("memory")
                stats["redis_memory_usage"] = redis_info.get("used_memory_human", "unknown")
                stats["redis_memory_peak"] = redis_info.get("used_memory_peak_human", "unknown")
            except Exception as e:
                logger.debug(f"Could not get Redis memory info: {e}")
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Cache health check"""
        health_info = {
            "status": "healthy",
            "redis_connected": False,
            "local_cache_size": len(self.local_cache),
            "errors": []
        }
        
        try:
            # Test Redis connection
            if self.redis_client:
                await self.redis_client.ping()
                health_info["redis_connected"] = True
            
            # Test cache operations
            test_key = "health_check_test"
            test_value = {"timestamp": datetime.utcnow().isoformat()}
            
            await self.set("test", test_key, test_value, 60)
            retrieved_value = await self.get("test", test_key)
            
            if retrieved_value != test_value:
                health_info["errors"].append("Cache set/get test failed")
                health_info["status"] = "degraded"
            
            await self.delete("test", test_key)
            
        except Exception as e:
            health_info["status"] = "unhealthy"
            health_info["errors"].append(str(e))
            logger.error(f"Cache health check failed: {e}")
        
        return health_info


# Background task for cache maintenance
async def cache_maintenance_task(cache_manager: CacheManager):
    """Background task for cache maintenance"""
    while True:
        try:
            await cache_manager.cleanup_expired()
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            logger.error(f"Cache maintenance task error: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error


# Global cache manager instance
cache_manager = CacheManager()
