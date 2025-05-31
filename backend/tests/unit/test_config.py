"""
Unit tests for the core configuration module.
"""

import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from core.config import Settings, DatabaseSettings, CacheSettings, SecuritySettings


class TestDatabaseSettings:
    """Test database configuration settings."""
    
    def test_database_settings_defaults(self):
        """Test default database settings."""
        settings = DatabaseSettings()
        
        assert settings.database_url == "sqlite:///./talk_to_data.db"
        assert settings.database_pool_size == 20
        assert settings.database_max_overflow == 30
        assert settings.database_pool_timeout == 30
        assert settings.database_echo is False
    
    def test_database_settings_postgresql(self):
        """Test PostgreSQL database settings."""
        settings = DatabaseSettings(
            database_url="postgresql+asyncpg://user:pass@localhost/db"
        )
        
        assert "postgresql" in settings.database_url
        assert settings.database_pool_size == 20
    
    def test_database_settings_validation(self):
        """Test database settings validation."""
        with pytest.raises(ValidationError):
            DatabaseSettings(database_pool_size=-1)
        
        with pytest.raises(ValidationError):
            DatabaseSettings(database_max_overflow=-1)


class TestCacheSettings:
    """Test cache configuration settings."""
    
    def test_cache_settings_defaults(self):
        """Test default cache settings."""
        settings = CacheSettings()
        
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.redis_cache_ttl == 3600
        assert settings.redis_max_connections == 50
        assert settings.enable_local_cache is True
    
    def test_cache_settings_custom(self):
        """Test custom cache settings."""
        settings = CacheSettings(
            redis_url="redis://remote:6379/1",
            redis_cache_ttl=7200,
            enable_local_cache=False
        )
        
        assert "remote" in settings.redis_url
        assert settings.redis_cache_ttl == 7200
        assert settings.enable_local_cache is False


class TestSecuritySettings:
    """Test security configuration settings."""
    
    def test_security_settings_defaults(self):
        """Test default security settings."""
        settings = SecuritySettings()
        
        assert settings.secret_key == "your-secret-key-change-in-production"
        assert settings.algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30
        assert settings.refresh_token_expire_days == 7
    
    def test_security_settings_custom(self):
        """Test custom security settings."""
        settings = SecuritySettings(
            secret_key="custom-secret-key",
            access_token_expire_minutes=60,
            refresh_token_expire_days=14
        )
        
        assert settings.secret_key == "custom-secret-key"
        assert settings.access_token_expire_minutes == 60
        assert settings.refresh_token_expire_days == 14
    
    def test_security_settings_validation(self):
        """Test security settings validation."""
        with pytest.raises(ValidationError):
            SecuritySettings(access_token_expire_minutes=-1)
        
        with pytest.raises(ValidationError):
            SecuritySettings(refresh_token_expire_days=0)


class TestSettings:
    """Test main application settings."""
    
    def test_settings_defaults(self):
        """Test default application settings."""
        settings = Settings()
        
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.log_level == "INFO"
    
    @patch.dict("os.environ", {
        "API_HOST": "127.0.0.1",
        "API_PORT": "9000",
        "DEBUG": "true",
        "ENVIRONMENT": "production"
    })
    def test_settings_from_environment(self):
        """Test settings loaded from environment variables."""
        settings = Settings()
        
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 9000
        assert settings.debug is True
        assert settings.environment == "production"
    
    def test_settings_database_integration(self):
        """Test database settings integration."""
        settings = Settings(
            database_url="postgresql://test:test@localhost/test"
        )
        
        assert settings.database_url == "postgresql://test:test@localhost/test"
        assert isinstance(settings.database_pool_size, int)
    
    def test_settings_cache_integration(self):
        """Test cache settings integration."""
        settings = Settings(
            redis_url="redis://test:6379/5"
        )
        
        assert settings.redis_url == "redis://test:6379/5"
        assert isinstance(settings.redis_cache_ttl, int)
    
    def test_settings_security_integration(self):
        """Test security settings integration."""
        settings = Settings(
            secret_key="test-secret-key",
            access_token_expire_minutes=45
        )
        
        assert settings.secret_key == "test-secret-key"
        assert settings.access_token_expire_minutes == 45
    
    def test_settings_validation_errors(self):
        """Test settings validation errors."""
        with pytest.raises(ValidationError):
            Settings(api_port=-1)
        
        with pytest.raises(ValidationError):
            Settings(api_port=70000)
    
    def test_settings_llm_configuration(self):
        """Test LLM configuration settings."""
        settings = Settings(
            gemini_api_key="test-api-key",
            llm_model="gemini-1.5-pro",
            llm_temperature=0.2
        )
        
        assert settings.gemini_api_key == "test-api-key"
        assert settings.llm_model == "gemini-1.5-pro"
        assert settings.llm_temperature == 0.2
    
    def test_settings_monitoring_configuration(self):
        """Test monitoring configuration settings."""
        settings = Settings(
            log_level="DEBUG",
            log_format="json",
            enable_metrics=True
        )
        
        assert settings.log_level == "DEBUG"
        assert settings.log_format == "json"
        assert settings.enable_metrics is True
    
    def test_settings_celery_configuration(self):
        """Test Celery configuration settings."""
        settings = Settings(
            celery_broker_url="redis://localhost:6379/1",
            celery_result_backend="redis://localhost:6379/2"
        )
        
        assert settings.celery_broker_url == "redis://localhost:6379/1"
        assert settings.celery_result_backend == "redis://localhost:6379/2"


class TestSettingsFactory:
    """Test settings factory patterns."""
    
    def test_development_settings(self):
        """Test development environment settings."""
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            settings = Settings()
            
            assert settings.environment == "development"
            assert settings.debug is False  # Explicit setting required
    
    def test_production_settings(self):
        """Test production environment settings."""
        with patch.dict("os.environ", {
            "ENVIRONMENT": "production",
            "DEBUG": "false"
        }):
            settings = Settings()
            
            assert settings.environment == "production"
            assert settings.debug is False
    
    def test_testing_settings(self):
        """Test testing environment settings."""
        with patch.dict("os.environ", {
            "ENVIRONMENT": "testing",
            "DATABASE_URL": "sqlite:///:memory:"
        }):
            settings = Settings()
            
            assert settings.environment == "testing"
            assert "memory" in settings.database_url
