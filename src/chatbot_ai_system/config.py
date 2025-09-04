"""Configuration management for the chatbot system."""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # OpenAI Configuration
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", env="OPENAI_MODEL")

    # Anthropic Configuration
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-haiku-20240307", env="ANTHROPIC_MODEL")

    # Application Settings
    app_name: str = Field(default="AI Chatbot System", env="APP_NAME")
    api_base_url: Optional[str] = Field(default="http://localhost:8000", env="API_BASE_URL")
    debug_mode: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Database
    database_url: str = Field(
        default="postgresql://user:pass@localhost/chatbot", env="DATABASE_URL"
    )

    # Redis Cache
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")

    # Rate Limiting
    rate_limit_requests: int = Field(default=60, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")

    # Token Limits
    max_tokens: int = Field(default=4000, env="MAX_TOKENS")
    max_context_length: int = Field(default=8000, env="MAX_CONTEXT_LENGTH")

    # Timeout Settings
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")

    # Provider Selection
    default_provider: str = Field(default="openai", env="DEFAULT_PROVIDER")
    enable_fallback: bool = Field(default=True, env="ENABLE_FALLBACK")

    # Streaming
    enable_streaming: bool = Field(default=True, env="ENABLE_STREAMING")
    stream_chunk_size: int = Field(default=1024, env="STREAM_CHUNK_SIZE")

    # Security
    cors_origins: str = Field(default="*", env="CORS_ORIGINS")
    api_key_header: str = Field(default="X-API-Key", env="API_KEY_HEADER")

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Create a global settings instance
settings = get_settings()
