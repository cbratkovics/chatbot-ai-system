"""API route definitions."""


from .health import router as health_router
from .v1 import router as v1_router
from .v2 import router as v2_router
from .websocket import router as websocket_router

__all__ = ["health_router", "v1_router", "v2_router", "websocket_router"]
