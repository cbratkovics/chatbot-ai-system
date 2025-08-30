"""Centralized configuration using Pydantic Settings."""

from typing import Any, Dict, List, Tuple, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Settings
    app_name: str = "AI Chatbot System"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost/chatbot"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Provider Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    # Monitoring
    enable_metrics: bool = True
    enable_tracing: bool = True
    otel_exporter_endpoint: str = "http://localhost:4317"
