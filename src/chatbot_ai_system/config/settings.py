"""Settings configuration"""
import json
from typing import Optional, List
from pydantic import Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # This allows extra fields in .env to be ignored
    )

    app_name: str = "AI Chatbot System"
    version: str = "1.0.0"
    api_base_url: Optional[str] = Field(default="http://localhost:8000", env="API_BASE_URL")

    # API Keys
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")

    # Database
    database_url: str = Field(
        default="postgresql://user:pass@localhost/chatbot", env="DATABASE_URL"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Server Configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    reload: bool = Field(default=False, env="RELOAD")
    workers: int = Field(default=1, env="WORKERS")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # API Configuration
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    debug: bool = Field(default=False, env="DEBUG")

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")

    # CORS Configuration - parse from environment
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: List[str] = Field(default=["*"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default=["*"], env="CORS_ALLOW_HEADERS")

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
