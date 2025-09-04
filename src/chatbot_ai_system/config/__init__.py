"""Configuration module"""
from functools import lru_cache
from .settings import Settings


@lru_cache()
def get_settings():
    """Get cached settings instance"""
    return Settings()


# Create a global settings instance
settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
