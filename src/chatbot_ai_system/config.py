"""Application configuration management."""

from typing import Any, Dict, List, Tuple, Optional
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # API Configuration
    app_name: str = "Chatbot System"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False)
    api_prefix: str = "/api/v1"

    # Server Configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=4)

    # CORS Configuration
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    allowed_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: list[str] = ["*"]

    # Database Configuration
    database_url: str = Field(
        default="postgresql://user:password@localhost/chatbot_db"
    )
    database_echo: bool = Field(default=False)

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_max_connections: int = Field(default=100)

    # Provider Configuration
    provider_a_api_key: str | None = Field(default=None)
    provider_b_api_key: str | None = Field(default=None)
    provider_timeout: int = Field(default=30)
    max_retries: int = Field(default=3)

    # Authentication
    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=60)

    # WebSocket Configuration
    websocket_heartbeat_interval: int = Field(default=30)
    websocket_max_connections: int = Field(default=1000)

    # Caching Configuration
    cache_ttl: int = Field(default=3600)  # 1 hour
    semantic_cache_threshold: float = Field(default=0.85)

    # Monitoring Configuration
    enable_metrics: bool = Field(default=True)
    enable_tracing: bool = Field(default=True)
    jaeger_endpoint: str | None = Field(default=None)

    # Performance Configuration
    max_concurrent_requests: int = Field(default=1000)
    request_timeout: int = Field(default=60)

    # Cost Tracking
    enable_cost_tracking: bool = Field(default=True)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from .env


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Global settings instance
settings = get_settings()
