"""Unit tests for model factory and providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestModelFactory:
    """Test suite for model factory."""

    @pytest.mark.asyncio
    async def test_factory_initialization(self):
        """Test model factory initialization."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()
        assert factory.providers is not None
        assert "openai" in factory.providers
        assert "anthropic" in factory.providers
        assert factory.default_provider == "openai"

    @pytest.mark.asyncio
    async def test_provider_registration(self):
        """Test registering new provider."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()
        mock_provider = MagicMock()

        factory.register_provider("custom", mock_provider)
        assert "custom" in factory.providers
        assert factory.providers["custom"] == mock_provider

    @pytest.mark.asyncio
    async def test_provider_selection(self):
        """Test provider selection logic."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()

        openai_provider = factory.get_provider("gpt-4")
        assert openai_provider is not None

        anthropic_provider = factory.get_provider("claude-3-opus")
        assert anthropic_provider is not None

        with pytest.raises(ValueError, match="Unsupported model"):
            factory.get_provider("unknown-model")

    @pytest.mark.asyncio
    async def test_model_switching(self):
        """Test dynamic model switching."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()

        provider1 = factory.get_provider("gpt-4")
        provider2 = factory.get_provider("claude-3-opus")

        assert provider1 != provider2
        assert provider1.__class__.__name__ == "OpenAIProvider"
        assert provider2.__class__.__name__ == "AnthropicProvider"

    @pytest.mark.asyncio
    async def test_provider_health_check(self):
        """Test provider health check."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()

        with patch.object(factory.providers["openai"], "health_check", return_value=True):
            health = await factory.check_provider_health("openai")
            assert health is True

    @pytest.mark.asyncio
    async def test_load_balancing(self):
        """Test load balancing across providers."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory(load_balancing=True)

        selections = []
        for _ in range(10):
            provider = factory.get_provider_with_load_balancing()
            selections.append(provider)

        assert len(set(selections)) > 1


class TestOpenAIProvider:
    """Test suite for OpenAI provider."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self, mock_openai_client):
        """Test OpenAI provider initialization."""
        from api.core.models.openai_provider import OpenAIProvider

        provider = OpenAIProvider(client=mock_openai_client)
        assert provider.client == mock_openai_client
        assert provider.name == "openai"
        assert provider.supported_models is not None

    @pytest.mark.asyncio
    async def test_chat_completion(
        self, mock_openai_client, sample_chat_request, sample_chat_response
    ):
        """Test chat completion request."""
        from api.core.models.openai_provider import OpenAIProvider

        mock_openai_client.chat.completions.create.return_value = sample_chat_response

        provider = OpenAIProvider(client=mock_openai_client)
        response = await provider.chat_completion(sample_chat_request)

        assert response == sample_chat_response
        mock_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_completion(self, mock_openai_client, mock_stream_response):
        """Test streaming completion."""
        from api.core.models.openai_provider import OpenAIProvider

        mock_openai_client.chat.completions.create.return_value = mock_stream_response()

        provider = OpenAIProvider(client=mock_openai_client)
        stream = provider.stream_completion({"message": "test", "stream": True})

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_retry_logic(self, mock_openai_client):
        """Test retry logic on failure."""
        from api.core.models.openai_provider import OpenAIProvider

        mock_openai_client.chat.completions.create.side_effect = [
            ConnectionError("Network error"),
            ConnectionError("Network error"),
            {"response": "Success"},
        ]

        provider = OpenAIProvider(client=mock_openai_client, max_retries=3)
        response = await provider.chat_completion_with_retry({"message": "test"})

        assert response == {"response": "Success"}
        assert mock_openai_client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_token_counting(self, mock_openai_client):
        """Test token counting."""
        from api.core.models.openai_provider import OpenAIProvider

        provider = OpenAIProvider(client=mock_openai_client)

        text = "This is a test message for token counting."
        token_count = provider.count_tokens(text, model="gpt-4")

        assert token_count > 0
        assert isinstance(token_count, int)

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_openai_client):
        """Test error handling."""
        from api.core.models.openai_provider import OpenAIProvider

        mock_openai_client.chat.completions.create.side_effect = ValueError("Invalid request")

        provider = OpenAIProvider(client=mock_openai_client)

        with pytest.raises(ValueError, match="Invalid request"):
            await provider.chat_completion({"message": "test"})

    @pytest.mark.asyncio
    async def test_model_validation(self, mock_openai_client):
        """Test model validation."""
        from api.core.models.openai_provider import OpenAIProvider

        provider = OpenAIProvider(client=mock_openai_client)

        assert provider.is_model_supported("gpt-4") is True
        assert provider.is_model_supported("gpt-3.5-turbo") is True
        assert provider.is_model_supported("unknown-model") is False


class TestAnthropicProvider:
    """Test suite for Anthropic provider."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self, mock_anthropic_client):
        """Test Anthropic provider initialization."""
        from api.core.models.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(client=mock_anthropic_client)
        assert provider.client == mock_anthropic_client
        assert provider.name == "anthropic"
        assert provider.supported_models is not None

    @pytest.mark.asyncio
    async def test_message_formatting(self, mock_anthropic_client):
        """Test message formatting for Anthropic API."""
        from api.core.models.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(client=mock_anthropic_client)

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        formatted = provider.format_messages(messages)
        assert len(formatted) == 3
        assert formatted[0]["role"] == "user"
        assert formatted[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_chat_completion(self, mock_anthropic_client):
        """Test chat completion with Anthropic."""
        from api.core.models.anthropic_provider import AnthropicProvider

        mock_response = {
            "id": "test-id",
            "content": [{"text": "Test response"}],
            "model": "claude-3-opus",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        mock_anthropic_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(client=mock_anthropic_client)
        response = await provider.chat_completion({"message": "test", "model": "claude-3-opus"})

        assert response == mock_response
        mock_anthropic_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_support(self, mock_anthropic_client):
        """Test streaming support for Anthropic."""
        from api.core.models.anthropic_provider import AnthropicProvider

        async def mock_stream():
            chunks = ["Hello", " from", " Claude"]
            for chunk in chunks:
                yield {"delta": {"text": chunk}}

        mock_anthropic_client.messages.create.return_value = mock_stream()

        provider = AnthropicProvider(client=mock_anthropic_client)
        stream = provider.stream_completion({"message": "test", "stream": True})

        collected = []
        async for chunk in stream:
            collected.append(chunk)

        assert len(collected) == 3


class TestFallbackHandler:
    """Test suite for fallback handler."""

    @pytest.mark.asyncio
    async def test_fallback_initialization(self):
        """Test fallback handler initialization."""
        from api.core.models.fallback_handler import FallbackHandler

        primary = MagicMock()
        secondary = MagicMock()

        handler = FallbackHandler(primary=primary, secondary=secondary)
        assert handler.primary == primary
        assert handler.secondary == secondary
        assert handler.retry_count == 3

    @pytest.mark.asyncio
    async def test_automatic_failover(self):
        """Test automatic failover to secondary provider."""
        from api.core.models.fallback_handler import FallbackHandler

        primary = AsyncMock()
        primary.chat_completion.side_effect = ConnectionError("Primary failed")

        secondary = AsyncMock()
        secondary.chat_completion.return_value = {"response": "Secondary success"}

        handler = FallbackHandler(primary=primary, secondary=secondary)
        response = await handler.execute_with_fallback({"message": "test"})

        assert response == {"response": "Secondary success"}
        primary.chat_completion.assert_called_once()
        secondary.chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker pattern."""
        from api.core.models.fallback_handler import FallbackHandler

        primary = AsyncMock()
        primary.chat_completion.side_effect = ConnectionError("Primary failed")

        secondary = AsyncMock()
        secondary.chat_completion.return_value = {"response": "Secondary"}

        handler = FallbackHandler(primary=primary, secondary=secondary, circuit_breaker_threshold=2)

        for _ in range(3):
            await handler.execute_with_fallback({"message": "test"})

        assert handler.circuit_open is True
        assert primary.chat_completion.call_count == 2

    @pytest.mark.asyncio
    async def test_health_monitoring(self):
        """Test provider health monitoring."""
        from api.core.models.fallback_handler import FallbackHandler

        primary = AsyncMock()
        primary.health_check.return_value = False

        secondary = AsyncMock()
        secondary.health_check.return_value = True

        handler = FallbackHandler(primary=primary, secondary=secondary)

        healthy_provider = await handler.get_healthy_provider()
        assert healthy_provider == secondary

    @pytest.mark.asyncio
    async def test_fallback_metrics(self, mock_metrics_collector):
        """Test fallback metrics collection."""
        from api.core.models.fallback_handler import FallbackHandler

        primary = AsyncMock()
        primary.chat_completion.side_effect = ConnectionError("Failed")

        secondary = AsyncMock()
        secondary.chat_completion.return_value = {"response": "Success"}

        handler = FallbackHandler(
            primary=primary, secondary=secondary, metrics_collector=mock_metrics_collector
        )

        await handler.execute_with_fallback({"message": "test"})

        mock_metrics_collector.increment_counter.assert_called_with("fallback_triggered")
