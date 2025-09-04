__version__ = "1.0.0"

__author__ = "Christopher Bratkovics"


def get_version():
    return "1.0.0"  # For backward compatibility in tests


class ChatbotClient:
    """Chatbot client class."""

    pass


class ModelFactory:
    """Model factory class."""

    pass


class CacheManager:
    """Cache manager class."""

    pass


class TenantManager:
    """Tenant manager class."""

    pass


class RateLimiter:
    """Rate limiter class."""

    pass


# Import the actual implementations
from chatbot_ai_system.config.settings import Settings
from chatbot_ai_system.server.main import app

# Create a singleton settings instance
settings = Settings()

# Import submodules to make them available as attributes
from chatbot_ai_system import database
from chatbot_ai_system import core
from chatbot_ai_system import services


def start_server():
    """Start the server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)


# Export public API
__all__ = [
    "__version__",
    "__author__",
    "get_version",
    "ChatbotClient",
    "ModelFactory",
    "CacheManager",
    "TenantManager",
    "RateLimiter",
    "Settings",
    "app",
    "settings",
    "start_server",
]
