"""API v1 module."""

from typing import Any, Dict, List, Optional, Tuple

from api.v1.routes import health, websocket
from fastapi import APIRouter

# Create placeholder routers for missing modules
chat_router = APIRouter()
tenants_router = APIRouter()


# Create module-like objects with router attribute
class ChatModule:
    """Placeholder for chat module."""

    router = chat_router


class TenantsModule:
    """Placeholder for tenants module."""

    router = tenants_router


chat = ChatModule()
tenants = TenantsModule()

__all__ = ["chat", "health", "tenants", "websocket"]
