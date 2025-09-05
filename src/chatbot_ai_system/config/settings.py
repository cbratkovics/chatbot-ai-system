"""Settings configuration"""
import json
from typing import Optional, List
from pydantic import Field, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with complete configuration"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False,
        validate_assignment=True
    )

    # Application
    app_name: str = Field(default="AI Chatbot System", validation_alias="APP_NAME")
    version: str = "1.0.0"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    api_prefix: str = Field(default="/api/v1", validation_alias="API_PREFIX")
    api_base_url: Optional[str] = Field(default="http://localhost:8000", validation_alias="API_BASE_URL")

    # Server
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT", ge=1, le=65535)
    workers: int = Field(default=1, validation_alias="WORKERS", ge=1)
    reload: bool = Field(default=False, validation_alias="RELOAD")

    # API Keys
    openai_api_key: Optional[SecretStr] = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[SecretStr] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, validation_alias="REDIS_MAX_CONNECTIONS")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, validation_alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, validation_alias="RATE_LIMIT_PERIOD")

    api_key: Optional[str] = Field(default=None, validation_alias="API_KEY")
    # Cache
    cache_enabled: bool = Field(default=True, validation_alias="CACHE_ENABLED")
    cache_ttl_seconds: int = Field(default=3600, validation_alias="CACHE_TTL_SECONDS")
    semantic_cache_threshold: float = Field(default=0.85, validation_alias="SEMANTIC_CACHE_THRESHOLD")
    cache_compression_enabled: bool = Field(default=False, validation_alias="CACHE_COMPRESSION_ENABLED")
    cache_compression_threshold: int = Field(default=1024, validation_alias="CACHE_COMPRESSION_THRESHOLD")
    semantic_cache_enabled: bool = Field(default=True, validation_alias="SEMANTIC_CACHE_ENABLED")
    cache_circuit_breaker_enabled: bool = Field(default=True, validation_alias="CACHE_CIRCUIT_BREAKER_ENABLED")
    cache_warming_enabled: bool = Field(default=False, validation_alias="CACHE_WARMING_ENABLED")

    # Model Defaults
    default_model: str = Field(default="gpt-3.5-turbo", validation_alias="DEFAULT_MODEL")
    default_temperature: float = Field(default=0.7, validation_alias="DEFAULT_TEMPERATURE")
    default_max_tokens: int = Field(default=2048, validation_alias="DEFAULT_MAX_TOKENS")
    openai_model: str = Field(default="gpt-3.5-turbo", validation_alias="OPENAI_MODEL")
    anthropic_model: str = Field(default="claude-3-haiku-20240307", validation_alias="ANTHROPIC_MODEL")
    default_provider: str = Field(default="openai", validation_alias="DEFAULT_PROVIDER")
    enable_fallback: bool = Field(default=True, validation_alias="ENABLE_FALLBACK")
    max_retries: int = Field(default=3, validation_alias="MAX_RETRIES")

    # Database
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    # WebSocket
    ws_max_connections: int = Field(default=100, validation_alias="WS_MAX_CONNECTIONS")
    ws_heartbeat_interval: int = Field(default=30, validation_alias="WS_HEARTBEAT_INTERVAL")

    # Security
    jwt_secret_key: Optional[SecretStr] = Field(default=None, validation_alias="JWT_SECRET_KEY")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], validation_alias="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, validation_alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: List[str] = Field(default=["*"], validation_alias="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default=["*"], validation_alias="CORS_ALLOW_HEADERS")

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Timeouts
    request_timeout: int = Field(default=30, validation_alias="REQUEST_TIMEOUT")
    max_context_length: int = Field(default=8000, validation_alias="MAX_CONTEXT_LENGTH")
    max_tokens: int = Field(default=4000, validation_alias="MAX_TOKENS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Handle JSON array format
            if v.startswith("["):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            # Handle comma-separated format
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("cors_allow_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v):
        if isinstance(v, str):
            # Handle JSON array format
            if v.startswith("["):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            # Handle comma-separated format
            return [method.strip() for method in v.split(",")]
        return v

    @field_validator("cors_allow_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v):
        if isinstance(v, str):
            # Handle JSON array format
            if v.startswith("["):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            # Handle comma-separated format or wildcard
            if v == "*":
                return ["*"]
            return [header.strip() for header in v.split(",")]
        return v

    # Properties
    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic_key(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
