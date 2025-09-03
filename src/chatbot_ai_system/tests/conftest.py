import os
from unittest.mock import AsyncMock, Mock

import pytest

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["ANTHROPIC_API_KEY"] = "test-key"


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    mock = Mock()
    mock.chat.completions.create = AsyncMock()
    mock.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="Test response"))], usage=Mock(total_tokens=100)
    )
    return mock


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    mock = Mock()
    mock.messages.create = AsyncMock()
    mock.messages.create.return_value = Mock(
        content=[Mock(text="Test response")], usage=Mock(input_tokens=50, output_tokens=50)
    )
    return mock


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=False)
    mock.delete = AsyncMock(return_value=1)
    mock.ping = AsyncMock(return_value=True)
    return mock
