"""Pytest configuration and fixtures."""

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatbot_ai_system.config import Settings, settings
from chatbot_ai_system.sdk import ChatbotClient
from chatbot_ai_system.server.main import create_app

# Markers
pytest.mark.unit = pytest.mark.mark(name="unit")
pytest.mark.integration = pytest.mark.mark(name="integration")
pytest.mark.e2e = pytest.mark.mark(name="e2e")
pytest.mark.slow = pytest.mark.mark(name="slow")
pytest.mark.load = pytest.mark.mark(name="load")


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Test settings with mock values."""
    return Settings(
        environment="development",  # Changed from "testing" to match allowed values
        debug=True,
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/15",
        openai_api_key="sk-test-key",
        anthropic_api_key="sk-ant-test-key",
        jwt_secret_key="test-secret-key",
    )


@pytest.fixture
def app(test_settings, monkeypatch):
    """Create test FastAPI app."""
    # Override settings
    for key, value in test_settings.model_dump().items():
        monkeypatch.setattr(settings, key, value)

    return create_app()


@pytest.fixture
def client(app) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app) -> AsyncIterator[AsyncClient]:
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    with patch("chatbot_ai_system.providers.openai_provider.OpenAI") as mock:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                id="test-id",
                created=1234567890,
                model="gpt-3.5-turbo",
                choices=[
                    MagicMock(
                        message=MagicMock(content="Test response"),
                        index=0,
                        finish_reason="stop",
                    )
                ],
                usage=MagicMock(
                    prompt_tokens=10,
                    completion_tokens=20,
                    total_tokens=30,
                ),
            )
        )
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client."""
    with patch("chatbot_ai_system.providers.anthropic_provider.Anthropic") as mock:
        mock_instance = MagicMock()
        mock_instance.messages.create = AsyncMock(
            return_value=MagicMock(
                id="msg-test",
                type="message",
                content=[MagicMock(text="Test response", type="text")],
                model="claude-3-opus-20240229",
                usage=MagicMock(input_tokens=10, output_tokens=20),
            )
        )
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def chatbot_client(test_settings) -> ChatbotClient:
    """Create test chatbot client."""
    return ChatbotClient(
        base_url="http://test",
        api_key="test-key",
    )


@pytest.fixture
def sample_chat_request():
    """Sample chat request data."""
    return {
        "messages": [{"role": "user", "content": "Hello, how are you?"}],
        "model": "gpt-3.5-turbo",
        "provider": "openai",
        "temperature": 0.7,
        "stream": False,
    }
