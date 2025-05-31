"""
Enterprise Configuration Management
Centralized configuration for all application components
"""

from pydantic import BaseSettings, Field
from typing import Optional, List
import os
from functools import lru_cache


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    
    # PostgreSQL Configuration
    DB_HOST: str = Field(default="localhost", env="DB_HOST")
    DB_PORT: int = Field(default=5432, env="DB_PORT")
    DB_NAME: str = Field(default="talktodata", env="DB_NAME")
    DB_USER: str = Field(default="postgres", env="DB_USER")
    DB_PASSWORD: str = Field(env="DB_PASSWORD")
    
    # Connection Pool Settings
    DB_POOL_SIZE: int = Field(default=20, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=30, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")
    
    # Query Settings
    MAX_QUERY_TIMEOUT: int = Field(default=30, env="MAX_QUERY_TIMEOUT")
    MAX_RESULT_SIZE: int = Field(default=10000, env="MAX_RESULT_SIZE")
    PAGINATION_SIZE: int = Field(default=100, env="PAGINATION_SIZE")
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


class CacheSettings(BaseSettings):
    """Redis cache configuration"""
    
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
      # Cache TTL Settings (in seconds)
    SCHEMA_CACHE_TTL: int = Field(default=3600, env="SCHEMA_CACHE_TTL")  # 1 hour
    QUERY_CACHE_TTL: int = Field(default=300, env="QUERY_CACHE_TTL")     # 5 minutes
    RESULT_CACHE_TTL: int = Field(default=600, env="RESULT_CACHE_TTL")   # 10 minutes
    LLM_CACHE_TTL: int = Field(default=1800, env="LLM_CACHE_TTL")        # 30 minutes
    CACHE_USER_INPUT_TTL: int = Field(default=1800, env="CACHE_USER_INPUT_TTL")  # 30 minutes
    CACHE_SQL_VALIDATION_TTL: int = Field(default=3600, env="CACHE_SQL_VALIDATION_TTL")  # 1 hour
    
    # Cache Settings
    MAX_CACHE_SIZE: int = Field(default=1000, env="MAX_CACHE_SIZE")
    CACHE_PREFIX: str = Field(default="talktodata", env="CACHE_PREFIX")
    
    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


class LLMSettings(BaseSettings):
    """LLM and AI configuration"""
    
    GEMINI_API_KEY: str = Field(env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")
    
    # Rate Limiting
    LLM_RATE_LIMIT: int = Field(default=100, env="LLM_RATE_LIMIT")  # requests per minute
    LLM_TIMEOUT: int = Field(default=30, env="LLM_TIMEOUT")  # seconds
    
    # Retry Settings
    LLM_MAX_RETRIES: int = Field(default=3, env="LLM_MAX_RETRIES")
    LLM_RETRY_DELAY: int = Field(default=1, env="LLM_RETRY_DELAY")  # seconds


class SecuritySettings(BaseSettings):
    """Security and authentication configuration"""
    
    # JWT Settings
    JWT_SECRET_KEY: str = Field(env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_TIME: int = Field(default=3600, env="JWT_EXPIRATION_TIME")  # 1 hour
    JWT_REFRESH_EXPIRATION: int = Field(default=604800, env="JWT_REFRESH_EXPIRATION")  # 7 days
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    RATE_LIMIT_PER_HOUR: int = Field(default=1000, env="RATE_LIMIT_PER_HOUR")
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:8501"], env="ALLOWED_ORIGINS")
    ALLOWED_METHODS: List[str] = Field(default=["GET", "POST", "PUT", "DELETE"], env="ALLOWED_METHODS")
    
    # Security Headers
    SECURITY_HEADERS_ENABLED: bool = Field(default=True, env="SECURITY_HEADERS_ENABLED")


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration"""
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")  # json or text
    
    # Metrics
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")
    
    # Health Checks
    HEALTH_CHECK_INTERVAL: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")  # seconds
    
    # Tracing
    ENABLE_TRACING: bool = Field(default=True, env="ENABLE_TRACING")
    JAEGER_ENDPOINT: Optional[str] = Field(default=None, env="JAEGER_ENDPOINT")


class CelerySettings(BaseSettings):
    """Background task processing configuration"""
    
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1", env="CELERY_RESULT_BACKEND")
    
    # Task Settings
    TASK_SERIALIZER: str = Field(default="json", env="TASK_SERIALIZER")
    RESULT_SERIALIZER: str = Field(default="json", env="RESULT_SERIALIZER")
    TASK_TRACK_STARTED: bool = Field(default=True, env="TASK_TRACK_STARTED")
    
    # Worker Settings
    WORKER_CONCURRENCY: int = Field(default=4, env="WORKER_CONCURRENCY")
    WORKER_PREFETCH_MULTIPLIER: int = Field(default=1, env="WORKER_PREFETCH_MULTIPLIER")


class AppSettings(BaseSettings):
    """Main application settings"""
    
    # Application
    APP_NAME: str = Field(default="TalkToData Enterprise", env="APP_NAME")
    APP_VERSION: str = Field(default="2.0.0", env="APP_VERSION")
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="production", env="ENVIRONMENT")
    
    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=4, env="WORKERS")
    
    # Feature Flags
    ENABLE_CACHING: bool = Field(default=True, env="ENABLE_CACHING")
    ENABLE_BACKGROUND_TASKS: bool = Field(default=True, env="ENABLE_BACKGROUND_TASKS")
    ENABLE_QUERY_OPTIMIZATION: bool = Field(default=True, env="ENABLE_QUERY_OPTIMIZATION")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


class Settings:
    """Aggregated settings class"""
    
    def __init__(self):
        self.app = AppSettings()
        self.database = DatabaseSettings()
        self.cache = CacheSettings()
        self.llm = LLMSettings()
        self.security = SecuritySettings()
        self.monitoring = MonitoringSettings()
        self.celery = CelerySettings()


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
