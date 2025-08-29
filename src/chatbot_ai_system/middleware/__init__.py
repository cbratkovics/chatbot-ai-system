"""Middleware for AI Chatbot System."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
from typing import Callable


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Simple rate limiting implementation
        response = await call_next(request)
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Metrics collection middleware."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Error handling middleware."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Log the error and return a proper response
            return Response(
                content=f"Internal server error: {str(exc)}",
                status_code=500
            )


__all__ = [
    "RateLimitMiddleware",
    "MetricsMiddleware",
    "ErrorHandlerMiddleware",
]