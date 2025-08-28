"""Application configuration management."""

from functools import lru_cache

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # API Configuration
    app_name: str = "Chatbot System"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    api_prefix: str = "/api/v1"

    # Server Configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=4, env="WORKERS")

    # CORS Configuration
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], env="ALLOWED_ORIGINS"
    )
    allowed_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: list[str] = ["*"]

    # Database Configuration
    database_url: str = Field(
        default="postgresql://user:password@localhost/chatbot_db", env="DATABASE_URL"
    )
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")

    # Provider Configuration
    provider_a_api_key: str | None = Field(default=None, env="PROVIDER_A_API_KEY")
    provider_b_api_key: str | None = Field(default=None, env="PROVIDER_B_API_KEY")
    provider_timeout: int = Field(default=30, env="PROVIDER_TIMEOUT")
    max_retries: int = Field(default=3, env="MAX_RETRIES")

    # Authentication
    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production", env="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")

    # WebSocket Configuration
    websocket_heartbeat_interval: int = Field(default=30, env="WEBSOCKET_HEARTBEAT_INTERVAL")
    websocket_max_connections: int = Field(default=1000, env="WEBSOCKET_MAX_CONNECTIONS")

    # Caching Configuration
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")  # 1 hour
    semantic_cache_threshold: float = Field(default=0.85, env="SEMANTIC_CACHE_THRESHOLD")

    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    enable_tracing: bool = Field(default=True, env="ENABLE_TRACING")
    jaeger_endpoint: str | None = Field(default=None, env="JAEGER_ENDPOINT")

    # Performance Configuration
    max_concurrent_requests: int = Field(default=1000, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(default=60, env="REQUEST_TIMEOUT")

    # Cost Tracking
    enable_cost_tracking: bool = Field(default=True, env="ENABLE_COST_TRACKING")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Global settings instance
settings = get_settings()
