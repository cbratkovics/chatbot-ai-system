"""Request ID middleware for correlation tracking."""

import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with unique ID."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Bind request ID to logger context
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Clear context after request
        structlog.contextvars.clear_contextvars()

        return response
