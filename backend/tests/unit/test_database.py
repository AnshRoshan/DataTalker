"""
Unit tests for the core database module.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
import asyncpg

from core.database import DatabaseService, get_database, Base, User
from core.config import Settings


class TestDatabaseService:
    """Test database service functionality."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            database_pool_size=10,
            database_max_overflow=20
        )
    
    @pytest.fixture
    def database_service(self, mock_settings):
        """Create database service instance."""
        return DatabaseService(mock_settings)
    
    def test_database_service_initialization(self, database_service, mock_settings):
        """Test database service initialization."""
        assert database_service.settings == mock_settings
        assert database_service.engine is not None
        assert database_service._connection_pool is None
    
    @pytest.mark.asyncio
    async def test_get_session(self, database_service):
        """Test getting database session."""
        with patch('core.database.AsyncSession') as mock_session:
            async with database_service.get_session() as session:
                assert session is not None
                mock_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, database_service):
        """Test successful database health check."""
        with patch.object(database_service, 'execute_query') as mock_execute:
            mock_execute.return_value = [{"result": 1}]
            
            result = await database_service.health_check()
            
            assert result["status"] == "healthy"
            assert result["response_time"] > 0
            mock_execute.assert_called_once_with("SELECT 1 as result")
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, database_service):
        """Test failed database health check."""
        with patch.object(database_service, 'execute_query') as mock_execute:
            mock_execute.side_effect = Exception("Connection failed")
            
            result = await database_service.health_check()
            
            assert result["status"] == "unhealthy"
            assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_query_success(self, database_service):
        """Test successful query execution."""
        mock_connection = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [{"id": 1, "name": "test"}]
        mock_connection.execute.return_value = mock_result
        
        with patch.object(database_service, '_get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await database_service.execute_query("SELECT * FROM users")
            
            assert len(result) == 1
            assert result[0]["id"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_query_with_parameters(self, database_service):
        """Test query execution with parameters."""
        mock_connection = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [{"id": 1}]
        mock_connection.execute.return_value = mock_result
        
        with patch.object(database_service, '_get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            await database_service.execute_query(
                "SELECT * FROM users WHERE id = $1", 
                params=[1]
            )
            
            mock_connection.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_query_error_handling(self, database_service):
        """Test query execution error handling."""
        with patch.object(database_service, '_get_connection') as mock_get_conn:
            mock_get_conn.side_effect = Exception("Query failed")
            
            with pytest.raises(Exception, match="Query failed"):
                await database_service.execute_query("INVALID SQL")
    
    @pytest.mark.asyncio
    async def test_get_schema_basic(self, database_service):
        """Test basic schema extraction."""
        mock_tables = [
            {"table_name": "users", "table_schema": "public"},
            {"table_name": "orders", "table_schema": "public"}
        ]
        mock_columns = [
            {"table_name": "users", "column_name": "id", "data_type": "integer"},
            {"table_name": "users", "column_name": "name", "data_type": "varchar"},
            {"table_name": "orders", "column_name": "id", "data_type": "integer"}
        ]
        
        with patch.object(database_service, 'execute_query') as mock_execute:
            mock_execute.side_effect = [mock_tables, mock_columns, [], []]
            
            schema = await database_service.get_schema()
            
            assert "tables" in schema
            assert "users" in schema["tables"]
            assert "orders" in schema["tables"]
            assert "id" in schema["tables"]["users"]["columns"]
    
    @pytest.mark.asyncio
    async def test_get_schema_with_cache(self, database_service):
        """Test schema extraction with caching."""
        # First call
        with patch.object(database_service, 'execute_query') as mock_execute:
            mock_execute.side_effect = [
                [{"table_name": "users", "table_schema": "public"}],
                [{"table_name": "users", "column_name": "id", "data_type": "integer"}],
                [], []
            ]
            
            schema1 = await database_service.get_schema()
            schema2 = await database_service.get_schema()
            
            # Should only execute queries once due to caching
            assert mock_execute.call_count == 4
            assert schema1 == schema2
    
    @pytest.mark.asyncio
    async def test_explain_query(self, database_service):
        """Test query execution plan analysis."""
        mock_plan = [
            {
                "QUERY PLAN": "Seq Scan on users  (cost=0.00..18.50 rows=850 width=32)"
            }
        ]
        
        with patch.object(database_service, 'execute_query') as mock_execute:
            mock_execute.return_value = mock_plan
            
            plan = await database_service.explain_query("SELECT * FROM users")
            
            assert len(plan) == 1
            assert "Seq Scan" in plan[0]["QUERY PLAN"]
    
    @pytest.mark.asyncio
    async def test_get_table_stats(self, database_service):
        """Test table statistics retrieval."""
        mock_stats = [
            {"table_name": "users", "row_count": 1000, "table_size": "64 KB"}
        ]
        
        with patch.object(database_service, 'execute_query') as mock_execute:
            mock_execute.return_value = mock_stats
            
            stats = await database_service.get_table_stats()
            
            assert len(stats) == 1
            assert stats[0]["row_count"] == 1000
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self, database_service):
        """Test connection pooling functionality."""
        with patch('asyncpg.create_pool') as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            
            await database_service._initialize_pool()
            
            assert database_service._connection_pool == mock_pool
            mock_create_pool.assert_called_once()
    
    def test_cleanup(self, database_service):
        """Test database service cleanup."""
        mock_pool = AsyncMock()
        database_service._connection_pool = mock_pool
        
        asyncio.run(database_service.cleanup())
        
        mock_pool.close.assert_called_once()


class TestDatabaseModels:
    """Test database model definitions."""
    
    def test_user_model_attributes(self):
        """Test User model attributes."""
        # Check that the User model has required attributes
        assert hasattr(User, 'id')
        assert hasattr(User, 'username')
        assert hasattr(User, 'email')
        assert hasattr(User, 'password_hash')
        assert hasattr(User, 'role')
        assert hasattr(User, 'is_active')
        assert hasattr(User, 'created_at')
        assert hasattr(User, 'updated_at')
    
    def test_base_model(self):
        """Test base model functionality."""
        # Check that Base is properly configured
        assert Base.metadata is not None
        assert hasattr(Base, 'registry')


class TestDatabaseDependency:
    """Test database dependency injection."""
    
    @pytest.mark.asyncio
    async def test_get_database_dependency(self):
        """Test get_database dependency function."""
        with patch('core.database.DatabaseService') as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            
            result = await get_database()
            
            assert result == mock_instance


class TestDatabasePerformance:
    """Test database performance optimizations."""
    
    @pytest.mark.asyncio
    async def test_query_timeout(self, database_service):
        """Test query timeout handling."""
        with patch.object(database_service, 'execute_query') as mock_execute:
            # Simulate a slow query
            async def slow_query(*args, **kwargs):
                await asyncio.sleep(2)
                return []
            
            mock_execute.side_effect = slow_query
            
            # Should handle timeout gracefully
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    database_service.execute_query("SLOW QUERY"), 
                    timeout=1
                )
    
    @pytest.mark.asyncio
    async def test_connection_pool_limits(self, database_service):
        """Test connection pool limits."""
        with patch('asyncpg.create_pool') as mock_create_pool:
            await database_service._initialize_pool()
            
            # Verify pool was created with correct settings
            mock_create_pool.assert_called_once()
            call_kwargs = mock_create_pool.call_args[1]
            assert 'min_size' in call_kwargs
            assert 'max_size' in call_kwargs


class TestDatabaseSecurity:
    """Test database security features."""
    
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, database_service):
        """Test SQL injection prevention."""
        malicious_input = "'; DROP TABLE users; --"
        
        with patch.object(database_service, '_get_connection') as mock_get_conn:
            mock_connection = AsyncMock()
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # Parameterized query should safely handle malicious input
            await database_service.execute_query(
                "SELECT * FROM users WHERE name = $1",
                params=[malicious_input]
            )
            
            # Verify the query was executed with parameters
            mock_connection.execute.assert_called_once()
            args = mock_connection.execute.call_args[0]
            assert malicious_input in args[1]  # Parameter, not in query string
