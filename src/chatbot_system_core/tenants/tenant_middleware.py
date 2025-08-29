"""Multi-tenant middleware with JWT context injection and quota validation."""

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware for multi-tenant context extraction and validation."""

    def __init__(self, app, secret_key: str, algorithm: str = "HS256"):
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm

    async def dispatch(self, request: Request, call_next):
        """Process request with tenant context."""
        # Skip middleware for health and docs endpoints
        if request.url.path in ["/health", "/docs", "/openapi.json", "/metrics"]:
            return await call_next(request)

        try:
            # Extract tenant context from JWT
            tenant_context = await self._extract_tenant_context(request)

            if tenant_context:
                # Inject tenant context into request state
                request.state.tenant_id = tenant_context.get("tenant_id")
                request.state.tenant_tier = tenant_context.get("tier", "basic")
                request.state.user_id = tenant_context.get("user_id")
                request.state.tenant_preferences = tenant_context.get("preferences", {})

                # Validate tenant quotas
                quota_check = await self._validate_quota(
                    tenant_context.get("tenant_id"),
                    request.url.path,
                    tenant_context.get("tier", "basic"),
                )

                if not quota_check["allowed"]:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": "Quota exceeded",
                            "detail": quota_check.get("reason", "Rate limit exceeded"),
                            "remaining": quota_check.get("remaining", 0),
                        },
                    )

                # Track usage for billing
                await self._track_request(
                    tenant_context.get("tenant_id"), request.url.path, request.method
                )

            # Process request
            response = await call_next(request)

            # Add tenant headers to response
            if tenant_context:
                response.headers["X-Tenant-ID"] = tenant_context.get("tenant_id", "")
                response.headers["X-Rate-Limit-Remaining"] = str(quota_check.get("remaining", -1))

            return response

        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"error": e.detail})
        except Exception as e:
            logger.error(f"Tenant middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal server error"},
            )

    async def _extract_tenant_context(self, request: Request) -> dict[str, Any] | None:
        """Extract tenant context from JWT claims.

        Args:
            request: FastAPI request object

        Returns:
            Tenant context dictionary or None
        """
        # Try to get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Try to get from cookie for web clients
            token = request.cookies.get("auth_token")
            if not token:
                return None
        else:
            token = auth_header.replace("Bearer ", "")

        try:
            # Decode JWT and extract claims
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Extract tenant-specific claims
            tenant_context = {
                "tenant_id": payload.get("tenant_id"),
                "user_id": payload.get("sub"),
                "tier": payload.get("tier", "basic"),
                "permissions": payload.get("permissions", []),
                "preferences": payload.get("preferences", {}),
                "exp": payload.get("exp"),
            }

            # Validate tenant_id exists
            if not tenant_context["tenant_id"]:
                logger.warning("JWT missing tenant_id claim")
                return None

            return tenant_context

        except JWTError as e:
            logger.error(f"JWT validation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract tenant context: {e}")
            return None

    async def _validate_quota(self, tenant_id: str, endpoint: str, tier: str) -> dict[str, Any]:
        """Validate tenant quotas before processing request.

        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint being accessed
            tier: Tenant tier level

        Returns:
            Quota validation result
        """
        # Get tier-specific limits
        tier_limits = self._get_tier_limits(tier)

        # Check rate limits from cache
        from api.core.cache.cache_manager import CacheManager

        cache = CacheManager()

        # Create rate limit key
        rate_key = f"rate_limit:{tenant_id}:{endpoint}"
        minute_key = f"{rate_key}:minute"
        hour_key = f"{rate_key}:hour"

        # Get current usage
        minute_count = await cache.get(minute_key) or 0
        hour_count = await cache.get(hour_key) or 0

        # Check against limits
        if minute_count >= tier_limits["requests_per_minute"]:
            return {
                "allowed": False,
                "reason": f"Exceeded {tier_limits['requests_per_minute']} requests per minute",
                "remaining": 0,
            }

        if hour_count >= tier_limits["requests_per_hour"]:
            return {
                "allowed": False,
                "reason": f"Exceeded {tier_limits['requests_per_hour']} requests per hour",
                "remaining": 0,
            }

        # Increment counters
        await cache.increment(minute_key, ttl=60)
        await cache.increment(hour_key, ttl=3600)

        return {"allowed": True, "remaining": tier_limits["requests_per_minute"] - minute_count - 1}

    async def _track_request(self, tenant_id: str, endpoint: str, method: str):
        """Track API request for usage and billing.

        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint
            method: HTTP method
        """
        try:
            # Track in cache for real-time analytics
            from api.core.cache.cache_manager import CacheManager

            cache = CacheManager()

            # Create usage key
            usage_key = f"usage:{tenant_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"

            # Track endpoint usage
            endpoint_key = f"{usage_key}:{endpoint}:{method}"
            await cache.increment(endpoint_key, ttl=86400)  # 24 hour TTL

            # Track total daily requests
            total_key = f"{usage_key}:total"
            await cache.increment(total_key, ttl=86400)

            # Log for audit trail
            logger.info(
                f"Request tracked - Tenant: {tenant_id}, Endpoint: {endpoint}, Method: {method}"
            )

        except Exception as e:
            logger.error(f"Failed to track request: {e}")

    def _get_tier_limits(self, tier: str) -> dict[str, int]:
        """Get rate limits for tenant tier.

        Args:
            tier: Tenant tier level

        Returns:
            Rate limit configuration
        """
        limits = {
            "basic": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "tokens_per_day": 100000,
                "concurrent_connections": 5,
            },
            "professional": {
                "requests_per_minute": 300,
                "requests_per_hour": 10000,
                "tokens_per_day": 1000000,
                "concurrent_connections": 20,
            },
            "enterprise": {
                "requests_per_minute": 1000,
                "requests_per_hour": 50000,
                "tokens_per_day": 10000000,
                "concurrent_connections": 100,
            },
        }

        return limits.get(tier, limits["basic"])


class TenantContextManager:
    """Manager for tenant-specific context and preferences."""

    @staticmethod
    def get_model_preferences(tenant_context: dict[str, Any]) -> dict[str, Any]:
        """Get tenant-specific model preferences.

        Args:
            tenant_context: Tenant context from JWT

        Returns:
            Model selection preferences
        """
        preferences = tenant_context.get("preferences", {})
        tier = tenant_context.get("tier", "basic")

        # Default preferences by tier
        tier_defaults = {
            "basic": {
                "preferred_model": "gpt-3.5-turbo",
                "max_tokens": 2000,
                "temperature": 0.7,
                "allow_function_calling": False,
                "enable_streaming": True,
            },
            "professional": {
                "preferred_model": "gpt-4",
                "max_tokens": 4000,
                "temperature": 0.7,
                "allow_function_calling": True,
                "enable_streaming": True,
                "enable_vision": True,
            },
            "enterprise": {
                "preferred_model": "gpt-4-turbo",
                "max_tokens": 8000,
                "temperature": 0.7,
                "allow_function_calling": True,
                "enable_streaming": True,
                "enable_vision": True,
                "enable_code_interpreter": True,
                "custom_models": ["claude-3-opus", "llama-3-70b"],
            },
        }

        # Merge tier defaults with tenant preferences
        defaults = tier_defaults.get(tier, tier_defaults["basic"])
        return {**defaults, **preferences}

    @staticmethod
    def validate_model_access(tenant_tier: str, requested_model: str) -> bool:
        """Validate if tenant can access requested model.

        Args:
            tenant_tier: Tenant tier level
            requested_model: Model requested

        Returns:
            True if access is allowed
        """
        model_tiers = {
            "gpt-3.5-turbo": ["basic", "professional", "enterprise"],
            "gpt-4": ["professional", "enterprise"],
            "gpt-4-turbo": ["enterprise"],
            "claude-3-opus": ["enterprise"],
            "claude-3-sonnet": ["professional", "enterprise"],
            "llama-3-70b": ["enterprise"],
            "llama-3-8b": ["professional", "enterprise"],
        }

        allowed_tiers = model_tiers.get(requested_model, [])
        return tenant_tier in allowed_tiers

    @staticmethod
    async def get_tenant_usage_stats(tenant_id: str, period: str = "today") -> dict[str, Any]:
        """Get tenant usage statistics.

        Args:
            tenant_id: Tenant identifier
            period: Time period (today, week, month)

        Returns:
            Usage statistics
        """
        from api.core.cache.cache_manager import CacheManager

        cache = CacheManager()

        # Get usage data from cache
        if period == "today":
            date_key = datetime.utcnow().strftime("%Y-%m-%d")
        else:
            date_key = datetime.utcnow().strftime("%Y-%m")

        usage_key = f"usage:{tenant_id}:{date_key}"

        # Get all usage data
        total_requests = await cache.get(f"{usage_key}:total") or 0
        total_tokens = await cache.get(f"{usage_key}:tokens") or 0

        return {
            "tenant_id": tenant_id,
            "period": period,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "timestamp": datetime.utcnow().isoformat(),
        }
