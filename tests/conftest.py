"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    from chatbot_ai_system.config import Settings
    
    return Settings(
        database_url="sqlite:///test.db",
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret-key",
    )