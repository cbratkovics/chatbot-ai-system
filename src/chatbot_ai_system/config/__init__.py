"""Configuration module"""
from .settings import Settings

def get_settings():
    """Get settings instance"""
    return Settings()

__all__ = ["Settings", "get_settings"]
