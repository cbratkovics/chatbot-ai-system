"""Unit tests for package structure and imports."""

import pytest
from packaging.version import Version


@pytest.mark.unit
class TestPackageStructure:
    """Test package structure and metadata."""

    def test_package_imports(self):
        """Test that package can be imported."""
        import chatbot_ai_system

        assert chatbot_ai_system.__version__
        assert chatbot_ai_system.__author__ == "Christopher Bratkovics"

    def test_version_format(self):
        """Test version follows semantic versioning."""
        from chatbot_ai_system import __version__

        version = Version(__version__)
        assert version.major == 0
        assert version.minor == 1
        assert version.micro == 0

    def test_public_api_exports(self):
        """Test public API exports."""
        from chatbot_ai_system import (
            ChatbotClient,
            Settings,
            __version__,
            app,
            settings,
            start_server,
        )

        assert __version__
        assert Settings
        assert settings
        assert ChatbotClient
        assert app
        assert callable(start_server)

    def test_get_version_function(self):
        """Test get_version utility."""
        from chatbot_ai_system import get_version

        assert get_version() == "0.1.0"


@pytest.mark.unit
class TestSchemas:
    """Test data schemas."""

    def test_chat_request_schema(self):
        """Test ChatRequest schema."""
        from chatbot_ai_system.schemas import ChatRequest

        request = ChatRequest(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-3.5-turbo",
            provider="openai",
        )

        assert request.model == "gpt-3.5-turbo"
        assert request.provider == "openai"
        assert len(request.messages) == 1
        assert request.temperature == 0.7  # default

    def test_chat_response_schema(self):
        """Test ChatResponse schema."""
        from chatbot_ai_system.schemas import ChatResponse

        response = ChatResponse(
            id="test-123",
            created=1234567890,
            model="gpt-3.5-turbo",
            provider="openai",
            choices=[{"index": 0, "message": {"role": "assistant", "content": "Hi!"}}],
        )

        assert response.id == "test-123"
        assert response.provider == "openai"
        assert len(response.choices) == 1

    def test_health_status_schema(self):
        """Test HealthStatus schema."""
        from chatbot_ai_system.schemas import HealthStatus

        status = HealthStatus(
            status="healthy",
            version="0.1.0",
        )

        assert status.status == "healthy"
        assert status.service == "ai-chatbot-system"


@pytest.mark.unit
class TestConfiguration:
    """Test configuration management."""

    def test_settings_defaults(self):
        """Test default settings."""
        from chatbot_ai_system.config import Settings

        settings = Settings()
        assert settings.app_name == "AI Chatbot System"
        assert settings.environment == "development"
        assert settings.port == 8000

    def test_settings_from_env(self, monkeypatch):
        """Test settings from environment variables."""
        from chatbot_ai_system.config import Settings

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        settings = Settings()
        assert settings.environment == "production"
        assert settings.port == 9000
        assert settings.openai_api_key.get_secret_value() == "sk-test-key"

    def test_settings_validation(self):
        """Test settings validation."""
        from chatbot_ai_system.config import Settings
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Settings(port="not-a-number")  # Should fail validation


@pytest.mark.unit
class TestExceptions:
    """Test custom exceptions."""

    def test_base_exception(self):
        """Test ChatbotException."""
        from chatbot_ai_system.exceptions import ChatbotException

        exc = ChatbotException("Test error", error_code="TEST_ERROR", status_code=400)
        assert str(exc) == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 400

    def test_provider_exception(self):
        """Test ProviderException."""
        from chatbot_ai_system.exceptions import ProviderException

        exc = ProviderException("Provider failed", provider="openai")
        assert exc.provider == "openai"
        assert exc.status_code == 503
        assert exc.details["provider"] == "openai"

    def test_rate_limit_exception(self):
        """Test RateLimitException."""
        from chatbot_ai_system.exceptions import RateLimitException

        exc = RateLimitException()
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
