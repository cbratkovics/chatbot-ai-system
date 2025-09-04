"""
AI Chatbot System - Enterprise-grade conversational AI platform
"""

__version__ = "1.0.0"
__author__ = "Christopher Bratkovics"
__email__ = "christopher.bratkovics@gmail.com"

# Conditional imports to avoid failures
try:
    from chatbot_ai_system.config.settings import Settings
    settings = Settings()
except ImportError:
    Settings = None
    settings = None

try:
    from chatbot_ai_system.sdk.client import ChatbotClient
except ImportError:
    ChatbotClient = None

def get_version():
    """Get the current version of the package"""
    return __version__

__all__ = [
    "ChatbotClient",
    "Settings",
    "settings",
    "get_version",
    "__version__",
    "__author__",
    "__email__",
]
