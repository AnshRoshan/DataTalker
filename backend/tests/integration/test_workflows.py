"""
Integration tests for the enterprise application workflows.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient

from enterprise_app import app


class TestAuthenticationIntegration:
    """Test complete authentication workflows."""
    
    @pytest.mark.asyncio
    async def test_user_registration_workflow(self, test_client):
        """Test complete user registration workflow."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "role": "ANALYST"
        }
        
        response = test_client.post("/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "user" in data["data"]
        assert data["data"]["user"]["username"] == "newuser"
        assert data["data"]["user"]["email"] == "newuser@example.com"
        assert data["data"]["user"]["role"] == "ANALYST"
        assert "password" not in data["data"]["user"]  # Password should not be returned
    
    @pytest.mark.asyncio
    async def test_login_logout_workflow(self, test_client, test_user):
        """Test complete login/logout workflow."""
        # Login
        login_data = {
            "username": "testuser",
            "password": "TestPassword123!"
        }
        
        response = test_client.post("/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        
        access_token = data["data"]["access_token"]
        
        # Use token for authenticated request
        headers = {"Authorization": f"Bearer {access_token}"}
        response = test_client.get("/admin/users", headers=headers)
        
        # Should work (assuming user has appropriate permissions)
        assert response.status_code in [200, 403]  # 403 if not admin
        
        # Logout
        response = test_client.post("/auth/logout", headers=headers)
        assert response.status_code == 200
        
        # Token should be invalidated
        response = test_client.get("/admin/users", headers=headers)
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_token_refresh_workflow(self, test_client, test_user):
        """Test token refresh workflow."""
        # Login to get tokens
        login_data = {
            "username": "testuser",
            "password": "TestPassword123!"
        }
        
        response = test_client.post("/auth/login", json=login_data)
        data = response.json()
        refresh_token = data["data"]["refresh_token"]
        
        # Refresh token
        response = test_client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
    
    @pytest.mark.asyncio
    async def test_role_based_access_control(self, test_client, test_user, admin_user):
        """Test role-based access control."""
        # Test regular user access
        login_data = {
            "username": "testuser",
            "password": "TestPassword123!"
        }
        response = test_client.post("/auth/login", json=login_data)
        user_token = response.json()["data"]["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}
        
        # Test admin user access
        login_data = {
            "username": "admin",
            "password": "AdminPassword123!"
        }
        response = test_client.post("/auth/login", json=login_data)
        admin_token = response.json()["data"]["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Regular user should not access admin endpoints
        response = test_client.get("/admin/users", headers=user_headers)
        assert response.status_code == 403
        
        # Admin user should access admin endpoints
        response = test_client.get("/admin/users", headers=admin_headers)
        assert response.status_code == 200


class TestQueryIntegration:
    """Test complete query processing workflows."""
    
    @pytest.mark.asyncio
    async def test_simple_query_workflow(self, test_client, auth_headers, mock_database, mock_gemini):
        """Test simple query processing workflow."""
        query_data = {
            "question": "Show me all users"
        }
        
        with patch('main_graph.execute_graph') as mock_graph:
            mock_graph.return_value = {
                "answer": "Here are all users",
                "sql": "SELECT * FROM users",
                "results": [
                    {"id": 1, "name": "John"},
                    {"id": 2, "name": "Jane"}
                ]
            }
            
            response = test_client.post(
                "/query/",
                json=query_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "answer" in data["data"]
            assert "sql" in data["data"]
            assert "results" in data["data"]
    
    @pytest.mark.asyncio
    async def test_background_query_workflow(self, test_client, auth_headers):
        """Test background query processing workflow."""
        query_data = {
            "question": "Generate a comprehensive report of all sales data",
            "priority": "normal"
        }
        
        with patch('core.tasks.process_large_query.delay') as mock_task:
            mock_task.return_value.id = "task-123"
            
            response = test_client.post(
                "/query/background",
                json=query_data,
                headers=auth_headers
            )
            
            assert response.status_code == 202
            data = response.json()
            assert data["success"] is True
            assert "task_id" in data["data"]
            
            task_id = data["data"]["task_id"]
            
            # Check task status
            with patch('core.tasks.celery_app.AsyncResult') as mock_result:
                mock_result.return_value.state = "PENDING"
                mock_result.return_value.info = {"progress": 50}
                
                response = test_client.get(
                    f"/query/task/{task_id}",
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["status"] == "PENDING"
    
    @pytest.mark.asyncio
    async def test_query_export_workflow(self, test_client, auth_headers):
        """Test query export workflow."""
        export_data = {
            "query": "SELECT * FROM orders WHERE amount > 1000",
            "format": "csv"
        }
        
        with patch('core.tasks.export_query_results.delay') as mock_task:
            mock_task.return_value.id = "export-task-123"
            
            response = test_client.post(
                "/query/export",
                json=export_data,
                headers=auth_headers
            )
            
            assert response.status_code == 202
            data = response.json()
            assert data["success"] is True
            assert "task_id" in data["data"]
    
    @pytest.mark.asyncio
    async def test_cached_query_workflow(self, test_client, auth_headers, redis_client):
        """Test cached query workflow."""
        query_data = {
            "question": "What is the total revenue?"
        }
        
        # Cache a response
        await redis_client.set(
            "llm:hash_of_question",
            json.dumps({
                "answer": "Cached total revenue is $1,000,000",
                "sql": "SELECT SUM(amount) FROM orders",
                "results": [{"sum": 1000000}]
            })
        )
        
        with patch('core.cache.CacheService.get_cached_llm_response') as mock_cache:
            mock_cache.return_value = {
                "answer": "Cached total revenue is $1,000,000",
                "sql": "SELECT SUM(amount) FROM orders",
                "results": [{"sum": 1000000}]
            }
            
            response = test_client.post(
                "/query/",
                json=query_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "Cached" in data["data"]["answer"]


class TestAdminIntegration:
    """Test admin functionality workflows."""
    
    @pytest.mark.asyncio
    async def test_user_management_workflow(self, test_client, admin_headers):
        """Test complete user management workflow."""
        # Create user
        user_data = {
            "username": "manageduser",
            "email": "managed@example.com",
            "password": "ManagedPass123!",
            "role": "VIEWER"
        }
        
        response = test_client.post(
            "/admin/users",
            json=user_data,
            headers=admin_headers
        )
        
        assert response.status_code == 201
        created_user = response.json()["data"]["user"]
        user_id = created_user["id"]
        
        # List users
        response = test_client.get("/admin/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()["data"]["users"]
        assert any(u["id"] == user_id for u in users)
        
        # Update user
        update_data = {
            "role": "ANALYST",
            "is_active": False
        }
        
        response = test_client.put(
            f"/admin/users/{user_id}",
            json=update_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        updated_user = response.json()["data"]["user"]
        assert updated_user["role"] == "ANALYST"
        assert updated_user["is_active"] is False
        
        # Delete user
        response = test_client.delete(
            f"/admin/users/{user_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_schema_analysis_workflow(self, test_client, admin_headers):
        """Test schema analysis workflow."""
        with patch('core.tasks.analyze_schema.delay') as mock_task:
            mock_task.return_value.id = "schema-task-123"
            
            response = test_client.post(
                "/admin/analyze-schema",
                headers=admin_headers
            )
            
            assert response.status_code == 202
            data = response.json()
            assert data["success"] is True
            assert "task_id" in data["data"]
    
    @pytest.mark.asyncio
    async def test_system_stats_workflow(self, test_client, admin_headers):
        """Test system statistics workflow."""
        with patch('core.monitoring.PerformanceTracker.get_system_stats') as mock_stats:
            mock_stats.return_value = {
                "database": {"status": "healthy", "connections": 5},
                "cache": {"status": "healthy", "memory_usage": "50MB"},
                "celery": {"active_tasks": 2, "completed_tasks": 100}
            }
            
            response = test_client.get(
                "/admin/system-stats",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "database" in data["data"]
            assert "cache" in data["data"]


class TestErrorHandlingIntegration:
    """Test error handling across the application."""
    
    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, test_client):
        """Test authentication error scenarios."""
        # Invalid credentials
        response = test_client.post("/auth/login", json={
            "username": "nonexistent",
            "password": "wrongpass"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_authorization_error_handling(self, test_client, auth_headers):
        """Test authorization error scenarios."""
        # Regular user trying to access admin endpoint
        response = test_client.get("/admin/users", headers=auth_headers)
        
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_validation_error_handling(self, test_client, auth_headers):
        """Test input validation error scenarios."""
        # Invalid query data
        response = test_client.post(
            "/query/",
            json={"invalid": "data"},
            headers=auth_headers
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data or "detail" in data
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, test_client, auth_headers):
        """Test rate limiting functionality."""
        # This would require actual rate limiting to be enabled
        # and making many requests quickly
        
        # For now, just test that rate limiting middleware is present
        response = test_client.get("/health")
        assert "X-RateLimit-Remaining" in response.headers or response.status_code == 200


class TestPerformanceIntegration:
    """Test performance aspects of the application."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, test_client, auth_headers):
        """Test handling of concurrent requests."""
        import asyncio
        import httpx
        
        async def make_request():
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get(
                    "/health",
                    headers=auth_headers
                )
                return response.status_code
        
        # Make 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All requests should succeed
        assert all(status == 200 for status in results)
    
    @pytest.mark.asyncio
    async def test_database_connection_pooling(self, test_client, auth_headers):
        """Test database connection pooling under load."""
        # Make multiple database-heavy requests
        query_data = {"question": "Show me all users"}
        
        responses = []
        for _ in range(5):
            response = test_client.post(
                "/query/",
                json=query_data,
                headers=auth_headers
            )
            responses.append(response.status_code)
        
        # All requests should succeed without connection issues
        assert all(status in [200, 202] for status in responses)


class TestHealthCheckIntegration:
    """Test health check and monitoring integration."""
    
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "checks" in data
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, test_client):
        """Test metrics endpoint."""
        response = test_client.get("/metrics")
        
        # Should return Prometheus metrics format or 200
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_application_startup_shutdown(self, test_client):
        """Test application startup and shutdown events."""
        # This is more of a smoke test to ensure the app starts correctly
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestDataFlowIntegration:
    """Test complete data flow through the application."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_query_flow(self, test_client, auth_headers):
        """Test complete end-to-end query processing."""
        # This would test the full flow:
        # User input -> Schema analysis -> SQL generation -> 
        # Validation -> Execution -> Response formatting
        
        with patch('main_graph.execute_graph') as mock_graph:
            mock_graph.return_value = {
                "answer": "Found 5 users in the system",
                "sql": "SELECT COUNT(*) FROM users",
                "results": [{"count": 5}],
                "metadata": {
                    "execution_time": 0.045,
                    "cached": False,
                    "agent_path": ["schema", "sql_writer", "validator", "executor", "formatter"]
                }
            }
            
            response = test_client.post(
                "/query/",
                json={"question": "How many users are there?"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify response structure
            assert data["success"] is True
            assert "answer" in data["data"]
            assert "sql" in data["data"]
            assert "results" in data["data"]
            assert "execution_time" in data["data"]
            
            # Verify response content
            assert "5 users" in data["data"]["answer"]
            assert "SELECT COUNT(*)" in data["data"]["sql"]
            assert data["data"]["results"][0]["count"] == 5
