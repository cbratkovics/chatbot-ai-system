"""Multi-tenant middleware for request isolation and context injection."""

import logging
from typing import Any
from uuid import UUID

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class TenantContext:
    """Tenant context for request processing."""

    def __init__(self, tenant_id: UUID, tenant_config: dict[str, Any] | None = None):
        self.tenant_id = tenant_id
        self.tenant_config = tenant_config or {}
        self.usage_limits = tenant_config.get("usage_limits", {}) if tenant_config else {}
        self.features = tenant_config.get("features", []) if tenant_config else []


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle multi-tenant request processing.

    - Extracts tenant ID from headers or API key
    - Injects tenant context into request state
    - Enforces tenant-specific rate limits and quotas
    - Provides tenant isolation
    """

    def __init__(self, app):
        super().__init__(app)
        # In production, this would connect to a tenant configuration service
        self._tenant_configs = {
            "tenant-1": {
                "name": "Demo Tenant 1",
                "plan": "enterprise",
                "usage_limits": {
                    "requests_per_minute": 1000,
                    "tokens_per_day": 1000000,
                    "concurrent_connections": 100,
                },
                "features": ["streaming", "semantic_cache", "analytics"],
                "cost_center": "engineering",
            },
            "tenant-2": {
                "name": "Demo Tenant 2",
                "plan": "startup",
                "usage_limits": {
                    "requests_per_minute": 100,
                    "tokens_per_day": 100000,
                    "concurrent_connections": 10,
                },
                "features": ["streaming"],
                "cost_center": "marketing",
            },
        }

    async def dispatch(self, request: Request, call_next):
        """Process tenant context for each request."""

        # Skip tenant middleware for health checks and docs
        if request.url.path in ["/", "/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        try:
            # Extract tenant ID from various sources
            tenant_id = await self._extract_tenant_id(request)

            if not tenant_id:
                # For demo purposes, use a default tenant
                tenant_id = "tenant-1"

            # Get tenant configuration
            tenant_config = self._tenant_configs.get(tenant_id)
            if not tenant_config:
                logger.warning(f"Unknown tenant ID: {tenant_id}")
                # Create default config for unknown tenants
                tenant_config = {
                    "name": f"Tenant {tenant_id}",
                    "plan": "basic",
                    "usage_limits": {
                        "requests_per_minute": 60,
                        "tokens_per_day": 10000,
                        "concurrent_connections": 5,
                    },
                    "features": [],
                    "cost_center": "default",
                }

            # Create tenant context
            tenant_context = TenantContext(tenant_id, tenant_config)

            # Inject into request state
            request.state.tenant = tenant_context
            request.state.tenant_id = tenant_id

            # Add tenant ID to headers for downstream services
            response = await call_next(request)
            response.headers["x-tenant-id"] = tenant_id

            logger.debug(f"Request processed for tenant: {tenant_id}")

            return response

        except Exception as e:
            logger.error(f"Tenant middleware error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Tenant processing failed", "detail": str(e)},
            )

    async def _extract_tenant_id(self, request: Request) -> str | None:
        """
        Extract tenant ID from request headers, API key, or path.
        Priority: x-tenant-id header > API key mapping > subdomain > default
        """

        # 1. Check x-tenant-id header (highest priority)
        tenant_id = request.headers.get("x-tenant-id")
        if tenant_id:
            return tenant_id

        # 2. Extract from API key (if present)
        api_key = request.headers.get("authorization")
        if api_key and api_key.startswith("Bearer "):
            # In production, map API keys to tenant IDs via database lookup
            api_key_value = api_key.replace("Bearer ", "")
            tenant_id = await self._get_tenant_from_api_key(api_key_value)
            if tenant_id:
                return tenant_id

        # 3. Extract from subdomain (e.g., tenant1.api.example.com)
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain and subdomain not in ["api", "www", "localhost"]:
                return subdomain

        # 4. Extract from path parameter (e.g., /api/v1/tenants/tenant-1/chat)
        path_parts = request.url.path.split("/")
        if "tenants" in path_parts:
            try:
                tenant_idx = path_parts.index("tenants") + 1
                if tenant_idx < len(path_parts):
                    return path_parts[tenant_idx]
            except (IndexError, ValueError):
                pass

        return None

    async def _get_tenant_from_api_key(self, api_key: str) -> str | None:
        """Map API key to tenant ID (mock implementation)."""
        # Mock mapping for demo - in production this would be a database lookup
        api_key_mappings = {
            "demo-key-1": "tenant-1",
            "demo-key-2": "tenant-2",
            "test-key": "tenant-1",
        }

        return api_key_mappings.get(api_key)

    def get_tenant_config(self, tenant_id: str) -> dict[str, Any] | None:
        """Get tenant configuration (for external access)."""
        return self._tenant_configs.get(tenant_id)

    def is_feature_enabled(self, request: Request, feature: str) -> bool:
        """Check if a feature is enabled for the current tenant."""
        tenant_context = getattr(request.state, "tenant", None)
        if not tenant_context:
            return False

        return feature in tenant_context.features

    def get_usage_limit(self, request: Request, limit_type: str) -> int | None:
        """Get usage limit for the current tenant."""
        tenant_context = getattr(request.state, "tenant", None)
        if not tenant_context:
            return None

        return tenant_context.usage_limits.get(limit_type)
