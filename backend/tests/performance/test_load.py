"""
Performance tests for the enterprise application.
"""

import pytest
import asyncio
import time
import statistics
import psutil
import concurrent.futures
from typing import List, Dict, Any
from unittest.mock import patch, AsyncMock
import httpx

from enterprise_app import app


class TestLoadTesting:
    """Load testing for various endpoints."""
    
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_concurrent_user_load(self, test_client, performance_settings):
        """Test application under concurrent user load."""
        concurrent_users = performance_settings["concurrent_users"]
        requests_per_user = performance_settings["requests_per_user"]
        acceptable_response_time = performance_settings["acceptable_response_time"]
        
        async def simulate_user_session():
            """Simulate a user session with multiple requests."""
            session_times = []
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                # Login
                start_time = time.time()
                login_response = await client.post("/auth/register", json={
                    "username": f"loadtest_user_{int(time.time() * 1000000)}",
                    "email": f"loadtest_{int(time.time() * 1000000)}@test.com",
                    "password": "LoadTest123!",
                    "role": "ANALYST"
                })
                
                if login_response.status_code == 201:
                    # Extract token for subsequent requests
                    user_data = login_response.json()
                    
                    # Simulate login
                    login_response = await client.post("/auth/login", json={
                        "username": user_data["data"]["user"]["username"],
                        "password": "LoadTest123!"
                    })
                    
                    if login_response.status_code == 200:
                        token = login_response.json()["data"]["access_token"]
                        headers = {"Authorization": f"Bearer {token}"}
                        
                        # Make multiple requests
                        for _ in range(requests_per_user):
                            request_start = time.time()
                            
                            # Mix of different endpoint types
                            endpoints = [
                                ("/health", "GET", None),
                                ("/query/", "POST", {"question": "Show me user count"}),
                                ("/", "GET", None)
                            ]
                            
                            for endpoint, method, data in endpoints:
                                if method == "GET":
                                    response = await client.get(endpoint, headers=headers)
                                else:
                                    response = await client.post(endpoint, json=data, headers=headers)
                                
                                request_time = time.time() - request_start
                                session_times.append(request_time)
                                
                                if response.status_code >= 500:
                                    pytest.fail(f"Server error on {endpoint}: {response.status_code}")
            
            return session_times
        
        # Run concurrent user sessions
        tasks = [simulate_user_session() for _ in range(concurrent_users)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        all_response_times = []
        errors = 0
        
        for result in results:
            if isinstance(result, Exception):
                errors += 1
            else:
                all_response_times.extend(result)
        
        # Performance assertions
        if all_response_times:
            avg_response_time = statistics.mean(all_response_times)
            p95_response_time = statistics.quantiles(all_response_times, n=20)[18]  # 95th percentile
            
            error_rate = errors / len(results)
            
            print(f"\n=== Load Test Results ===")
            print(f"Concurrent Users: {concurrent_users}")
            print(f"Total Requests: {len(all_response_times)}")
            print(f"Average Response Time: {avg_response_time:.3f}s")
            print(f"95th Percentile Response Time: {p95_response_time:.3f}s")
            print(f"Error Rate: {error_rate:.1%}")
            
            # Assertions
            assert error_rate < performance_settings["acceptable_error_rate"], \
                f"Error rate {error_rate:.1%} exceeds acceptable rate"
            
            assert avg_response_time < acceptable_response_time, \
                f"Average response time {avg_response_time:.3f}s exceeds acceptable time"


class TestDatabasePerformance:
    """Test database performance under load."""
    
    @pytest.mark.performance
    async def test_connection_pool_performance(self, db_session):
        """Test database connection pool performance."""
        from core.database import DatabaseService
        from core.config import Settings
        
        settings = Settings(database_pool_size=20, database_max_overflow=10)
        db_service = DatabaseService(settings)
        
        async def execute_query():
            """Execute a simple query."""
            start_time = time.time()
            try:
                await db_service.execute_query("SELECT 1 as test")
                return time.time() - start_time
            except Exception as e:
                return None
        
        # Execute many concurrent queries
        tasks = [execute_query() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_queries = [r for r in results if isinstance(r, float)]
        failed_queries = len(results) - len(successful_queries)
        
        if successful_queries:
            avg_time = statistics.mean(successful_queries)
            max_time = max(successful_queries)
            
            print(f"\n=== Database Performance Results ===")
            print(f"Successful Queries: {len(successful_queries)}")
            print(f"Failed Queries: {failed_queries}")
            print(f"Average Query Time: {avg_time:.3f}s")
            print(f"Max Query Time: {max_time:.3f}s")
            
            # Assertions
            assert failed_queries < 5, "Too many failed queries"
            assert avg_time < 0.1, "Queries taking too long on average"
        
        await db_service.cleanup()
    
    @pytest.mark.performance
    async def test_query_optimization(self, db_session):
        """Test query performance optimization."""
        from core.database import DatabaseService
        from core.config import Settings
        
        settings = Settings()
        db_service = DatabaseService(settings)
        
        # Test different query types
        queries = [
            "SELECT COUNT(*) FROM users",
            "SELECT * FROM users LIMIT 10",
            "SELECT u.id, u.username FROM users u WHERE u.is_active = true",
        ]
        
        performance_results = {}
        
        for query in queries:
            times = []
            for _ in range(5):  # Run each query 5 times
                start_time = time.time()
                try:
                    await db_service.execute_query(query)
                    times.append(time.time() - start_time)
                except Exception:
                    times.append(None)
            
            valid_times = [t for t in times if t is not None]
            if valid_times:
                performance_results[query] = {
                    "avg_time": statistics.mean(valid_times),
                    "min_time": min(valid_times),
                    "max_time": max(valid_times)
                }
        
        # Print results
        print(f"\n=== Query Performance Results ===")
        for query, metrics in performance_results.items():
            print(f"Query: {query[:50]}...")
            print(f"  Avg: {metrics['avg_time']:.3f}s")
            print(f"  Min: {metrics['min_time']:.3f}s")
            print(f"  Max: {metrics['max_time']:.3f}s")
        
        await db_service.cleanup()


class TestCachePerformance:
    """Test cache performance under load."""
    
    @pytest.mark.performance
    async def test_cache_throughput(self, redis_client):
        """Test cache throughput under load."""
        from core.cache import CacheService
        
        cache_service = CacheService(redis_client)
        
        async def cache_operations():
            """Perform mixed cache operations."""
            times = {"set": [], "get": [], "delete": []}
            
            for i in range(100):
                key = f"perf_test_key_{i}"
                value = f"perf_test_value_{i}" * 10  # Larger value
                
                # Set operation
                start_time = time.time()
                await cache_service.set(key, value)
                times["set"].append(time.time() - start_time)
                
                # Get operation
                start_time = time.time()
                result = await cache_service.get(key)
                times["get"].append(time.time() - start_time)
                
                assert result == value, "Cache value mismatch"
                
                # Delete operation
                if i % 10 == 0:  # Delete every 10th item
                    start_time = time.time()
                    await cache_service.delete(key)
                    times["delete"].append(time.time() - start_time)
            
            return times
        
        # Run concurrent cache operations
        tasks = [cache_operations() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Aggregate results
        all_times = {"set": [], "get": [], "delete": []}
        for result in results:
            for op_type, times in result.items():
                all_times[op_type].extend(times)
        
        # Analyze results
        print(f"\n=== Cache Performance Results ===")
        for op_type, times in all_times.items():
            if times:
                avg_time = statistics.mean(times)
                p95_time = statistics.quantiles(times, n=20)[18]
                
                print(f"{op_type.upper()} operations:")
                print(f"  Count: {len(times)}")
                print(f"  Avg: {avg_time:.4f}s")
                print(f"  P95: {p95_time:.4f}s")
                
                # Assertions
                assert avg_time < 0.01, f"{op_type} operations too slow"
    
    @pytest.mark.performance
    async def test_cache_memory_usage(self, redis_client):
        """Test cache memory usage patterns."""
        from core.cache import CacheService
        
        cache_service = CacheService(redis_client)
        
        # Store large amounts of data
        large_data = {"key": "value"} * 1000  # Large dictionary
        
        memory_usage = []
        for i in range(100):
            await cache_service.set(f"large_key_{i}", large_data)
            
            # Monitor memory usage (simplified)
            if i % 10 == 0:
                memory_usage.append(psutil.Process().memory_info().rss)
        
        # Check for memory leaks (simplified)
        if len(memory_usage) > 1:
            memory_growth = memory_usage[-1] - memory_usage[0]
            print(f"\n=== Memory Usage Results ===")
            print(f"Initial Memory: {memory_usage[0] / 1024 / 1024:.2f} MB")
            print(f"Final Memory: {memory_usage[-1] / 1024 / 1024:.2f} MB")
            print(f"Memory Growth: {memory_growth / 1024 / 1024:.2f} MB")


class TestAPIPerformance:
    """Test API endpoint performance."""
    
    @pytest.mark.performance
    async def test_endpoint_response_times(self, test_client, auth_headers):
        """Test response times for critical endpoints."""
        endpoints = [
            ("/health", "GET", None),
            ("/", "GET", None),
            ("/query/", "POST", {"question": "Test query"}),
        ]
        
        performance_results = {}
        
        for endpoint, method, data in endpoints:
            times = []
            
            for _ in range(20):  # 20 requests per endpoint
                start_time = time.time()
                
                if method == "GET":
                    response = test_client.get(endpoint, headers=auth_headers)
                else:
                    response = test_client.post(endpoint, json=data, headers=auth_headers)
                
                response_time = time.time() - start_time
                times.append(response_time)
                
                assert response.status_code < 500, f"Server error on {endpoint}"
            
            performance_results[endpoint] = {
                "avg_time": statistics.mean(times),
                "min_time": min(times),
                "max_time": max(times),
                "p95_time": statistics.quantiles(times, n=20)[18]
            }
        
        # Print results
        print(f"\n=== API Performance Results ===")
        for endpoint, metrics in performance_results.items():
            print(f"Endpoint: {endpoint}")
            print(f"  Avg: {metrics['avg_time']:.3f}s")
            print(f"  Min: {metrics['min_time']:.3f}s")
            print(f"  Max: {metrics['max_time']:.3f}s")
            print(f"  P95: {metrics['p95_time']:.3f}s")
            
            # Assertions
            assert metrics["avg_time"] < 1.0, f"{endpoint} average response time too high"
            assert metrics["p95_time"] < 2.0, f"{endpoint} P95 response time too high"


class TestBackgroundTaskPerformance:
    """Test background task performance."""
    
    @pytest.mark.performance
    async def test_celery_task_throughput(self, celery_app):
        """Test Celery task processing throughput."""
        
        @celery_app.task
        def test_task(data):
            """Simple test task."""
            import time
            time.sleep(0.1)  # Simulate work
            return {"processed": data}
        
        # Submit many tasks
        task_count = 50
        start_time = time.time()
        
        results = []
        for i in range(task_count):
            result = test_task.delay(f"data_{i}")
            results.append(result)
        
        # Wait for all tasks to complete
        for result in results:
            result.get(timeout=10)
        
        total_time = time.time() - start_time
        throughput = task_count / total_time
        
        print(f"\n=== Celery Performance Results ===")
        print(f"Tasks: {task_count}")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.2f} tasks/second")
        
        # Assertions
        assert throughput > 10, "Task throughput too low"


class TestMemoryPerformance:
    """Test memory usage and garbage collection."""
    
    @pytest.mark.performance
    async def test_memory_leak_detection(self, test_client, auth_headers):
        """Test for memory leaks during sustained operation."""
        import gc
        
        # Get initial memory usage
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss
        
        # Perform many operations
        for _ in range(100):
            response = test_client.post(
                "/query/",
                json={"question": "Test memory usage"},
                headers=auth_headers
            )
            assert response.status_code in [200, 202]
        
        # Force garbage collection
        gc.collect()
        final_memory = psutil.Process().memory_info().rss
        
        memory_growth = final_memory - initial_memory
        memory_growth_mb = memory_growth / 1024 / 1024
        
        print(f"\n=== Memory Leak Detection Results ===")
        print(f"Initial Memory: {initial_memory / 1024 / 1024:.2f} MB")
        print(f"Final Memory: {final_memory / 1024 / 1024:.2f} MB")
        print(f"Memory Growth: {memory_growth_mb:.2f} MB")
        
        # Assertion - should not grow too much
        assert memory_growth_mb < 50, f"Potential memory leak: {memory_growth_mb:.2f} MB growth"


class TestScalabilityLimits:
    """Test scalability limits and breaking points."""
    
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_maximum_concurrent_connections(self, test_client):
        """Test maximum concurrent connections."""
        max_connections = 100
        successful_connections = 0
        
        async def make_connection():
            try:
                response = test_client.get("/health")
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            return False
        
        # Test increasing levels of concurrency
        for concurrency_level in [10, 25, 50, 100]:
            tasks = [make_connection() for _ in range(concurrency_level)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if r is True)
            success_rate = successful / concurrency_level
            
            print(f"Concurrency {concurrency_level}: {success_rate:.1%} success rate")
            
            if success_rate < 0.95:  # 95% success rate threshold
                print(f"Breaking point reached at {concurrency_level} connections")
                break
            
            successful_connections = concurrency_level
        
        assert successful_connections >= 50, "Low concurrent connection capacity"
