"""API routes package."""

from .health import router as health_router
from .websocket import router as websocket_router

__all__ = ["websocket_router", "health_router"]
