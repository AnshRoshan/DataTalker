"""
Unit tests for the core cache module.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from core.cache import CacheService, LocalCache, get_cache_service


class TestLocalCache:
    """Test local in-memory cache functionality."""
    
    @pytest.fixture
    def local_cache(self):
        """Create local cache instance."""
        return LocalCache(max_size=100, ttl=60)
    
    def test_local_cache_initialization(self, local_cache):
        """Test local cache initialization."""
        assert local_cache.max_size == 100
        assert local_cache.ttl == 60
        assert len(local_cache._cache) == 0
    
    def test_local_cache_set_get(self, local_cache):
        """Test setting and getting values."""
        local_cache.set("test_key", "test_value")
        
        result = local_cache.get("test_key")
        assert result == "test_value"
    
    def test_local_cache_expiration(self, local_cache):
        """Test cache expiration."""
        local_cache.set("test_key", "test_value")
        
        # Simulate expiration by modifying timestamp
        entry = local_cache._cache["test_key"]
        entry["timestamp"] = datetime.now() - timedelta(seconds=120)
        
        result = local_cache.get("test_key")
        assert result is None
        assert "test_key" not in local_cache._cache
    
    def test_local_cache_max_size(self, local_cache):
        """Test cache size limits."""
        # Fill cache to capacity
        for i in range(150):  # More than max_size
            local_cache.set(f"key_{i}", f"value_{i}")
        
        # Should not exceed max size
        assert len(local_cache._cache) <= local_cache.max_size
    
    def test_local_cache_delete(self, local_cache):
        """Test cache deletion."""
        local_cache.set("test_key", "test_value")
        assert local_cache.get("test_key") == "test_value"
        
        local_cache.delete("test_key")
        assert local_cache.get("test_key") is None
    
    def test_local_cache_clear(self, local_cache):
        """Test cache clearing."""
        local_cache.set("key1", "value1")
        local_cache.set("key2", "value2")
        
        local_cache.clear()
        assert len(local_cache._cache) == 0
    
    def test_local_cache_exists(self, local_cache):
        """Test cache key existence check."""
        assert not local_cache.exists("test_key")
        
        local_cache.set("test_key", "test_value")
        assert local_cache.exists("test_key")


class TestCacheService:
    """Test Redis-based cache service functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        mock = AsyncMock()
        mock.get.return_value = None
        mock.set.return_value = True
        mock.delete.return_value = 1
        mock.exists.return_value = False
        mock.flushall.return_value = True
        return mock
    
    @pytest.fixture
    def cache_service(self, mock_redis):
        """Create cache service instance."""
        return CacheService(mock_redis, enable_local_cache=True)
    
    def test_cache_service_initialization(self, cache_service, mock_redis):
        """Test cache service initialization."""
        assert cache_service.redis == mock_redis
        assert cache_service.enable_local_cache is True
        assert cache_service.local_cache is not None
    
    @pytest.mark.asyncio
    async def test_cache_set_get_redis_only(self, cache_service, mock_redis):
        """Test setting and getting values from Redis."""
        cache_service.enable_local_cache = False
        
        await cache_service.set("test_key", "test_value", ttl=300)
        
        mock_redis.set.assert_called_once_with(
            "test_key", 
            json.dumps("test_value"), 
            ex=300
        )
        
        mock_redis.get.return_value = json.dumps("test_value")
        result = await cache_service.get("test_key")
        
        assert result == "test_value"
        mock_redis.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_cache_set_get_with_local_cache(self, cache_service, mock_redis):
        """Test setting and getting values with local cache."""
        await cache_service.set("test_key", "test_value", ttl=300)
        
        # Should set in both Redis and local cache
        mock_redis.set.assert_called_once()
        assert cache_service.local_cache.get("test_key") == "test_value"
        
        # First get should check local cache
        result = await cache_service.get("test_key")
        assert result == "test_value"
        
        # Should not call Redis since it's in local cache
        mock_redis.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_miss_redis_fallback(self, cache_service, mock_redis):
        """Test cache miss with Redis fallback."""
        # Local cache miss, Redis hit
        mock_redis.get.return_value = json.dumps("redis_value")
        
        result = await cache_service.get("test_key")
        
        assert result == "redis_value"
        mock_redis.get.assert_called_once_with("test_key")
        
        # Should now be in local cache
        assert cache_service.local_cache.get("test_key") == "redis_value"
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_service, mock_redis):
        """Test cache deletion."""
        # Set in both caches first
        await cache_service.set("test_key", "test_value")
        
        await cache_service.delete("test_key")
        
        mock_redis.delete.assert_called_once_with("test_key")
        assert cache_service.local_cache.get("test_key") is None
    
    @pytest.mark.asyncio
    async def test_cache_clear_all(self, cache_service, mock_redis):
        """Test clearing all cache."""
        await cache_service.clear_all()
        
        mock_redis.flushall.assert_called_once()
        assert len(cache_service.local_cache._cache) == 0
    
    @pytest.mark.asyncio
    async def test_cache_exists(self, cache_service, mock_redis):
        """Test cache key existence check."""
        mock_redis.exists.return_value = True
        
        result = await cache_service.exists("test_key")
        
        assert result is True
        mock_redis.exists.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_cache_schema_methods(self, cache_service, mock_redis):
        """Test schema-specific cache methods."""
        schema_data = {
            "tables": {
                "users": {"columns": {"id": "integer", "name": "varchar"}}
            }
        }
        
        # Test schema caching
        await cache_service.cache_schema("test_db", schema_data)
        mock_redis.set.assert_called_with(
            "schema:test_db",
            json.dumps(schema_data),
            ex=7200  # Default schema TTL
        )
        
        # Test schema retrieval
        mock_redis.get.return_value = json.dumps(schema_data)
        result = await cache_service.get_cached_schema("test_db")
        
        assert result == schema_data
        mock_redis.get.assert_called_with("schema:test_db")
    
    @pytest.mark.asyncio
    async def test_cache_query_methods(self, cache_service, mock_redis):
        """Test query-specific cache methods."""
        query = "SELECT * FROM users"
        results = [{"id": 1, "name": "John"}]
        
        # Test query result caching
        await cache_service.cache_query_result(query, results)
        
        expected_key = cache_service._generate_query_key(query)
        mock_redis.set.assert_called_with(
            expected_key,
            json.dumps(results),
            ex=1800  # Default query TTL
        )
        
        # Test query result retrieval
        mock_redis.get.return_value = json.dumps(results)
        result = await cache_service.get_cached_query_result(query)
        
        assert result == results
    
    @pytest.mark.asyncio
    async def test_cache_llm_methods(self, cache_service, mock_redis):
        """Test LLM response cache methods."""
        prompt = "What are the top customers?"
        response = {
            "answer": "Here are the top customers...",
            "sql": "SELECT * FROM customers ORDER BY revenue DESC LIMIT 10",
            "confidence": 0.95
        }
        
        # Test LLM response caching
        await cache_service.cache_llm_response(prompt, response)
        
        expected_key = cache_service._generate_llm_key(prompt)
        mock_redis.set.assert_called_with(
            expected_key,
            json.dumps(response),
            ex=3600  # Default LLM TTL
        )
        
        # Test LLM response retrieval
        mock_redis.get.return_value = json.dumps(response)
        result = await cache_service.get_cached_llm_response(prompt)
        
        assert result == response
    
    def test_generate_query_key(self, cache_service):
        """Test query key generation."""
        query = "SELECT * FROM users WHERE age > 25"
        key = cache_service._generate_query_key(query)
        
        assert key.startswith("query:")
        assert len(key) > len("query:")  # Should include hash
    
    def test_generate_llm_key(self, cache_service):
        """Test LLM key generation."""
        prompt = "Show me user statistics"
        key = cache_service._generate_llm_key(prompt)
        
        assert key.startswith("llm:")
        assert len(key) > len("llm:")  # Should include hash
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_service, mock_redis):
        """Test cache error handling."""
        # Simulate Redis connection error
        mock_redis.get.side_effect = Exception("Redis connection failed")
        
        # Should fallback gracefully
        result = await cache_service.get("test_key")
        assert result is None
        
        # Should still work with local cache if enabled
        if cache_service.enable_local_cache:
            cache_service.local_cache.set("test_key", "local_value")
            result = await cache_service.get("test_key")
            assert result == "local_value"
    
    @pytest.mark.asyncio
    async def test_cache_serialization(self, cache_service, mock_redis):
        """Test cache serialization of complex objects."""
        complex_data = {
            "users": [
                {"id": 1, "name": "John", "created_at": "2024-01-01"},
                {"id": 2, "name": "Jane", "created_at": "2024-01-02"}
            ],
            "metadata": {
                "total": 2,
                "query_time": 0.045
            }
        }
        
        await cache_service.set("complex_key", complex_data)
        
        # Should serialize to JSON
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args[0]
        assert json.loads(call_args[1]) == complex_data


class TestCacheDependency:
    """Test cache dependency injection."""
    
    @pytest.mark.asyncio
    async def test_get_cache_service_dependency(self):
        """Test get_cache_service dependency function."""
        with patch('core.cache.CacheService') as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            
            result = await get_cache_service()
            
            assert result == mock_instance


class TestCachePerformance:
    """Test cache performance optimizations."""
    
    @pytest.mark.asyncio
    async def test_cache_batch_operations(self, cache_service, mock_redis):
        """Test batch cache operations."""
        # Set multiple keys
        keys_values = [
            ("key1", "value1"),
            ("key2", "value2"),
            ("key3", "value3")
        ]
        
        # Simulate batch set operation
        tasks = [
            cache_service.set(key, value) 
            for key, value in keys_values
        ]
        await asyncio.gather(*tasks)
        
        # Should call Redis for each key
        assert mock_redis.set.call_count == 3
    
    @pytest.mark.asyncio
    async def test_cache_ttl_optimization(self, cache_service, mock_redis):
        """Test TTL optimization based on data type."""
        # Schema data should have longer TTL
        await cache_service.cache_schema("db", {})
        schema_call = mock_redis.set.call_args
        
        # Query results should have medium TTL
        await cache_service.cache_query_result("SELECT 1", [])
        query_call = mock_redis.set.call_args
        
        # LLM responses should have medium TTL
        await cache_service.cache_llm_response("test", {})
        llm_call = mock_redis.set.call_args
        
        # Verify different TTL values
        assert schema_call[1]["ex"] == 7200  # Schema TTL
        # Note: We would need to track previous calls to compare all TTLs


class TestCacheIntegration:
    """Test cache integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_pattern(self, cache_service, mock_redis):
        """Test cache invalidation patterns."""
        # Cache some schema data
        await cache_service.cache_schema("test_db", {"tables": {}})
        
        # Simulate schema change requiring invalidation
        await cache_service.delete("schema:test_db")
        
        mock_redis.delete.assert_called_with("schema:test_db")
    
    @pytest.mark.asyncio
    async def test_cache_warming(self, cache_service, mock_redis):
        """Test cache warming strategies."""
        # Simulate warming cache with frequently accessed data
        common_queries = [
            "SELECT COUNT(*) FROM users",
            "SELECT * FROM products LIMIT 10",
            "SELECT AVG(price) FROM orders"
        ]
        
        for query in common_queries:
            await cache_service.cache_query_result(query, [])
        
        assert mock_redis.set.call_count == 3
