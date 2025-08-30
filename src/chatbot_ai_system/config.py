"""Application configuration management."""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    APP_NAME: str = Field(default="Chatbot System", alias="app_name")
    APP_VERSION: str = Field(default="1.0.0", alias="app_version")
    APP_ENV: str = Field(default="development", alias="app_env")
    DEBUG: bool = Field(default=False)
    API_PREFIX: str = Field(default="/api/v1", alias="api_prefix")
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Server Configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    WORKERS: int = Field(default=4)

    # CORS Configuration
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:8000")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000")
    ALLOWED_METHODS: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    ALLOWED_HEADERS: List[str] = Field(default=["*"])

    # Database Configuration
    DATABASE_URL: str = Field(default="postgresql://user:password@localhost/chatbot_db")
    database_url: str = Field(default="postgresql://user:password@localhost/chatbot_db")
    DATABASE_ECHO: bool = Field(default=False)

    # Redis Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    redis_url: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = Field(default=100)

    # Provider Configuration
    provider_a_api_key: Optional[str] = Field(default=None)
    provider_b_api_key: Optional[str] = Field(default=None)
    PROVIDER_TIMEOUT: int = Field(default=30)
    MAX_RETRIES: int = Field(default=3)

    # Authentication
    JWT_SECRET_KEY: str = Field(default="your-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    rate_limit_requests: int = Field(default=100)
    RATE_LIMIT_WINDOW: int = Field(default=60)
    rate_limit_window: int = Field(default=60)
    rate_limit_period: int = Field(default=60)
    RATE_LIMIT_BURST_SIZE: int = Field(default=20)

    # WebSocket Configuration
    WS_ENABLED: bool = Field(default=True)
    WS_MAX_CONNECTIONS: int = Field(default=1000)
    WS_MAX_CONNECTIONS_PER_USER: int = Field(default=5)
    WS_HEARTBEAT_INTERVAL: int = Field(default=30)
    WEBSOCKET_HEARTBEAT_INTERVAL: int = Field(default=30)
    WEBSOCKET_MAX_CONNECTIONS: int = Field(default=1000)

    # Caching Configuration
    CACHE_TTL: int = Field(default=3600)
    SEMANTIC_CACHE_THRESHOLD: float = Field(default=0.85)

    # Monitoring Configuration
    ENABLE_METRICS: bool = Field(default=True)
    ENABLE_TRACING: bool = Field(default=True)
    JAEGER_ENDPOINT: Optional[str] = Field(default=None)

    # Performance Configuration
    MAX_CONCURRENT_REQUESTS: int = Field(default=1000)
    REQUEST_TIMEOUT: int = Field(default=60)

    # Cost Tracking
    ENABLE_COST_TRACKING: bool = Field(default=True)
    
    # Tenant Configuration
    TENANT_HEADER: str = Field(default="X-Tenant-ID")
    REQUIRE_TENANT_ID: bool = Field(default=False)
    DEFAULT_TENANT_ID: str = Field(default="default")
    
    # API Base URL and Keys
    api_base_url: str = Field(default="http://localhost:8000")
    api_key: Optional[str] = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


settings = get_settings()
