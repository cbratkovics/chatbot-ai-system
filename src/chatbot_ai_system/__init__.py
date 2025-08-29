"""AI Chatbot System - Production-ready multi-provider AI chatbot platform."""

__version__ = "0.1.0"
__author__ = "Christopher Bratkovics"
__email__ = "cbratkovics@gmail.com"

# Core imports for public API
from chatbot_ai_system.config import Settings, settings
from chatbot_ai_system.sdk import ChatbotClient
from chatbot_ai_system.server import app, start_server

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "Settings",
    "settings",
    "ChatbotClient",
    "app",
    "start_server",
]

# Version check
def get_version() -> str:
    """Return the current version."""
    return __version__