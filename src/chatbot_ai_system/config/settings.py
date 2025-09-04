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
