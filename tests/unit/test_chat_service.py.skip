"""Unit tests for chat service."""
from unittest.mock import AsyncMock, Mock

import pytest

from api.core.services.chat_service import ChatService


class TestChatService:
    """Test chat service functionality."""

    @pytest.fixture
    def chat_service(self):
        """Create chat service instance."""
        return ChatService()

    @pytest.mark.asyncio
    async def test_create_completion(self, chat_service):
        """Test chat completion creation."""
        # Mock provider
        chat_service.provider = AsyncMock()
        chat_service.provider.create_completion.return_value = {
            "id": "test-id",
            "choices": [{"message": {"content": "Test response"}}],
        }

        result = await chat_service.create_completion(
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert result["id"] == "test-id"
        assert "choices" in result

    @pytest.mark.asyncio
    async def test_semantic_cache(self, chat_service):
        """Test semantic caching functionality."""
        # Test cache hit
        chat_service.cache = Mock()
        chat_service.cache.get.return_value = {"cached": True}

        result = await chat_service.get_cached_response("test query")
        assert result["cached"] is True
