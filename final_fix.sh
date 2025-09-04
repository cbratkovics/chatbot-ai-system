#!/bin/bash

# Install pydantic-settings
poetry add pydantic-settings

# Fix all settings imports
find . -name "*.py" -type f -exec sed -i '' 's/from pydantic import BaseSettings/from pydantic_settings import BaseSettings/g' {} \;

# Fix the specific settings.py file
cat > src/chatbot_ai_system/config/settings.py << 'EOF'
"""Settings configuration"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    app_name: str = "AI Chatbot System"
    version: str = "1.0.0"
    api_base_url: Optional[str] = Field(default="http://localhost:8000", env="API_BASE_URL")

    # API Keys
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")

    # Database
    database_url: str = Field(
        default="postgresql://user:pass@localhost/chatbot",
        env="DATABASE_URL"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
EOF

# Fix other config.py files that might have the same issue
cat > src/chatbot_ai_system/config.py << 'EOF'
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
        default="postgresql://user:pass@localhost/chatbot",
        env="DATABASE_URL"
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
EOF

echo "Fixes applied! Running tests..."
poetry run pytest tests/test_basic.py tests/test_simple.py tests/unit/test_basic.py -v

echo ""
echo "If tests pass, run:"
echo "git add -A"
echo "git commit -m 'fix: update to pydantic-settings for Pydantic v2 compatibility'"
echo "git push origin main"
