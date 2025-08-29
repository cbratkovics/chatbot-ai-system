"""Configuration management for AI Chatbot System."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="AI Chatbot System", description="Application name")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Environment"
    )
    debug: bool = Field(default=False, description="Debug mode")

    # API Server
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, description="API port")
    api_base_url: str | None = Field(default=None, description="API base URL")
    api_key: SecretStr | None = Field(default=None, description="API key")
    cors_origins: str | list[str] = Field(
        default="http://localhost:3000,http://localhost:8000", description="CORS origins"
    )

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    # Database
    database_url: str | None = Field(
        default="postgresql://user:pass@localhost/chatbot", description="Database URL"
    )
    redis_url: str | None = Field(default="redis://localhost:6379", description="Redis URL")

    # AI Providers
    openai_api_key: SecretStr | None = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, env="ANTHROPIC_API_KEY")
    llama_api_endpoint: str | None = Field(default=None, env="LLAMA_API_ENDPOINT")

    # Security
    jwt_secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production"), description="JWT secret key"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_minutes: int = Field(default=30, description="JWT expiration")

    # Performance
    cache_ttl_seconds: int = Field(default=3600, description="Cache TTL")
    connection_pool_size: int = Field(default=100, description="Connection pool size")
    circuit_breaker_threshold: int = Field(default=5, description="Circuit breaker threshold")
    rate_limit_requests: int = Field(default=100, description="Rate limit requests")
    rate_limit_period: int = Field(default=60, description="Rate limit period (seconds)")


# Global settings instance
settings = Settings()

__all__ = ["Settings", "settings"]
