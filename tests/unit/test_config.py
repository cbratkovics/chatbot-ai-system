"""Test configuration loading."""

import pytest

from chatbot_system_core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.app_name == "AI Chatbot System"
    assert settings.api_prefix == "/api/v1"
    assert settings.rate_limit_requests == 100


def test_env_override(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("DEBUG", "true")
    settings = Settings()
    assert settings.app_name == "Test App"
    assert settings.debug is True
