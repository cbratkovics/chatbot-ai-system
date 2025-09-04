"""
Configuration module for the AI Chatbot System.
Handles environment variables and application settings.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # API Keys
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")

    # Application Settings
    environment: str = Field(
        "development", description="Environment (development, staging, production)"
    )
    log_level: str = Field("INFO", description="Logging level")
    debug: bool = Field(False, description="Debug mode")

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(True, description="Allow credentials in CORS")
    cors_allow_methods: List[str] = Field(["*"], description="Allowed HTTP methods")
    cors_allow_headers: List[str] = Field(["*"], description="Allowed HTTP headers")

    # Rate Limiting
    rate_limit_requests: int = Field(30, description="Max requests per minute")
    rate_limit_period: int = Field(60, description="Rate limit period in seconds")

    # Server Configuration
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    reload: bool = Field(False, description="Auto-reload on code changes")
    workers: int = Field(1, description="Number of worker processes")

    # Request Configuration
    request_timeout: int = Field(30, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum number of retries for API calls")
    retry_delay: float = Field(1.0, description="Initial retry delay in seconds")
    max_retry_delay: float = Field(10.0, description="Maximum retry delay in seconds")

    # Security
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production", description="Secret key for JWT tokens"
    )
    algorithm: str = Field("HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(30, description="Access token expiration time")

    # Database Configuration (for future use)
    database_url: Optional[str] = Field(None, description="Database connection URL")

    # Redis Configuration
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection URL")
    redis_max_connections: int = Field(50, description="Maximum Redis connections in pool")
    redis_connection_timeout: int = Field(5, description="Redis connection timeout in seconds")
    redis_socket_timeout: int = Field(5, description="Redis socket timeout in seconds")

    # Cache Configuration
    cache_enabled: bool = Field(True, description="Enable caching")
    cache_ttl_seconds: int = Field(3600, description="Default cache TTL in seconds (1 hour)")
    cache_compression_enabled: bool = Field(True, description="Enable cache compression")
    cache_compression_threshold: int = Field(
        1000, description="Compress responses larger than this (bytes)"
    )
    semantic_cache_enabled: bool = Field(True, description="Enable semantic similarity caching")
    semantic_cache_threshold: float = Field(
        0.95, description="Similarity threshold for semantic cache"
    )
    cache_warming_enabled: bool = Field(True, description="Enable cache warming on startup")
    cache_circuit_breaker_enabled: bool = Field(
        True, description="Enable circuit breaker for cache failures"
    )

    # Model Defaults
    default_temperature: float = Field(0.7, description="Default temperature for LLM responses")
    default_max_tokens: int = Field(2048, description="Default max tokens for LLM responses")
    default_openai_model: str = Field("gpt-3.5-turbo", description="Default OpenAI model")
    default_anthropic_model: str = Field(
        "claude-3-haiku-20240307", description="Default Anthropic model"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment value."""
        allowed = ["development", "staging", "production", "testing"]
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key)

    @property
    def has_anthropic_key(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(self.anthropic_api_key)


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Application settings instance
    """
    return Settings()


# Create a global settings instance
settings = get_settings()
