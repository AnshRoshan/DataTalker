"""
Test configuration and fixtures for the enterprise application.
"""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
import redis.asyncio as redis

from core.config import Settings
from core.database import get_async_session, get_database
from core.cache import get_cache_service
from core.auth import AuthService
from core.security import SecurityService
from enterprise_app import app


# Test Settings
@pytest.fixture
def test_settings():
    """Test configuration settings."""
    return Settings(
        # Database
        database_url="sqlite+aiosqlite:///:memory:",
        database_pool_size=1,
        database_max_overflow=0,
        
        # Redis (use fakeredis for testing)
        redis_url="redis://localhost:6379/15",
        redis_cache_ttl=60,
        
        # Security
        secret_key="test-secret-key-for-testing-only",
        access_token_expire_minutes=30,
        
        # API
        api_host="localhost",
        api_port=8000,
        debug=True,
        environment="testing",
        
        # LLM (mock for testing)
        gemini_api_key="test-api-key",
        llm_model="gemini-1.5-pro",
        
        # Logging
        log_level="DEBUG",
        log_format="text"
    )


# Database Fixtures
@pytest_asyncio.fixture
async def async_engine(test_settings):
    """Create async database engine for testing."""
    engine = create_async_engine(
        test_settings.database_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create tables
    from core.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session


# Redis Fixtures
@pytest_asyncio.fixture
async def redis_client():
    """Create Redis client for testing."""
    # Use fakeredis for testing
    import fakeredis.aioredis
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.flushall()
    await client.close()


# Application Fixtures
@pytest.fixture
def test_client(test_settings, db_session, redis_client):
    """Create test client with dependency overrides."""
    
    async def override_get_session():
        yield db_session
    
    async def override_get_database():
        return Mock()
    
    async def override_get_cache():
        from core.cache import CacheService
        return CacheService(redis_client)
    
    app.dependency_overrides[get_async_session] = override_get_session
    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_cache_service] = override_get_cache
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


# Authentication Fixtures
@pytest_asyncio.fixture
async def auth_service(db_session, redis_client, test_settings):
    """Create authentication service for testing."""
    security_service = SecurityService(test_settings)
    return AuthService(db_session, redis_client, security_service)


@pytest_asyncio.fixture
async def test_user(auth_service):
    """Create test user."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com", 
        "password": "TestPassword123!",
        "role": "ANALYST"
    }
    
    user = await auth_service.create_user(**user_data)
    return user


@pytest_asyncio.fixture
async def admin_user(auth_service):
    """Create admin test user."""
    user_data = {
        "username": "admin",
        "email": "admin@example.com",
        "password": "AdminPassword123!",
        "role": "ADMIN"
    }
    
    user = await auth_service.create_user(**user_data)
    return user


@pytest_asyncio.fixture
async def auth_headers(auth_service, test_user):
    """Create authentication headers for test user."""
    tokens = await auth_service.create_tokens(test_user.id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture
async def admin_headers(auth_service, admin_user):
    """Create authentication headers for admin user."""
    tokens = await auth_service.create_tokens(admin_user.id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# Mock LLM Fixtures
@pytest.fixture
def mock_gemini():
    """Mock Gemini LLM for testing."""
    mock = Mock()
    mock.generate_response = AsyncMock()
    mock.generate_response.return_value = {
        "answer": "Test response",
        "sql": "SELECT * FROM test_table;",
        "confidence": 0.95
    }
    return mock


# Mock Database Fixtures
@pytest.fixture
def mock_database():
    """Mock database connection for testing."""
    mock = Mock()
    mock.execute_query = AsyncMock()
    mock.execute_query.return_value = [
        {"id": 1, "name": "Test Record 1"},
        {"id": 2, "name": "Test Record 2"}
    ]
    mock.get_schema = AsyncMock()
    mock.get_schema.return_value = {
        "tables": {
            "test_table": {
                "columns": {
                    "id": {"type": "INTEGER", "nullable": False},
                    "name": {"type": "VARCHAR", "nullable": True}
                }
            }
        }
    }
    return mock


# Celery Testing
@pytest.fixture
def celery_app():
    """Mock Celery app for testing."""
    from celery import Celery
    
    app = Celery('test_app')
    app.config_from_object({
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
        'task_always_eager': True,
        'task_eager_propagates': True
    })
    
    return app


# Performance Testing Fixtures
@pytest.fixture
def performance_settings():
    """Settings for performance testing."""
    return {
        "concurrent_users": 10,
        "requests_per_user": 100,
        "test_duration": 60,  # seconds
        "acceptable_response_time": 1.0,  # seconds
        "acceptable_error_rate": 0.01  # 1%
    }


# Event Loop Fixture
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Pytest Configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for workflows"
    )
    config.addinivalue_line(
        "markers", "performance: Performance and load tests"
    )
    config.addinivalue_line(
        "markers", "security: Security and authentication tests"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take longer to run"
    )


def pytest_collection_modifyitems(config, items):
    """Add markers to tests based on their location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        elif "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)
