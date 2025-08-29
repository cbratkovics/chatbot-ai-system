"""Multi-tenant middleware for tenant isolation."""

from collections.abc import Callable

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ...config import settings

logger = structlog.get_logger()


class TenantMiddleware(BaseHTTPMiddleware):
    """Ensure tenant isolation for multi-tenant operations."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Extract and validate tenant ID."""
        # Skip tenant validation for public endpoints
        if request.url.path in ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Extract tenant ID from header
        tenant_id = request.headers.get(settings.TENANT_HEADER)

        # Use default tenant if not required
        if not tenant_id and not settings.REQUIRE_TENANT_ID:
            tenant_id = settings.DEFAULT_TENANT_ID

        # Validate tenant ID is present when required
        if not tenant_id and settings.REQUIRE_TENANT_ID:
            logger.warning(
                "Missing tenant ID",
                path=request.url.path,
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Missing Tenant ID",
                    "message": f"Header '{settings.TENANT_HEADER}' is required",
                    "request_id": getattr(request.state, "request_id", None),
                },
            )

        # Store tenant ID in request state
        request.state.tenant_id = tenant_id

        # Bind tenant ID to logger context
        structlog.contextvars.bind_contextvars(tenant_id=tenant_id)

        response = await call_next(request)

        # Add tenant ID to response headers
        if tenant_id:
            response.headers[settings.TENANT_HEADER] = tenant_id

        return response
