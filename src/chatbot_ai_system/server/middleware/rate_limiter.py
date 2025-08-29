"""Rate limiting middleware using token bucket algorithm."""

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ...config import settings

logger = structlog.get_logger()


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """Initialize token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False otherwise
        """
        async with self.lock:
            # Refill tokens based on time passed
            now = time.time()
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * self.refill_rate

            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now

            # Try to consume tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm."""

    def __init__(self, app):
        """Initialize rate limiter."""
        super().__init__(app)
        self.buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=settings.RATE_LIMIT_BURST_SIZE,
                refill_rate=settings.RATE_LIMIT_REQUESTS / 60.0,  # Convert to per-second
            )
        )

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request.

        Args:
            request: Incoming request

        Returns:
            Client identifier (tenant ID or IP address)
        """
        # Try to get tenant ID first
        tenant_id = request.headers.get(settings.TENANT_HEADER)
        if tenant_id:
            return f"tenant:{tenant_id}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting."""
        # Skip rate limiting if disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        client_id = self._get_client_id(request)
        bucket = self.buckets[client_id]

        # Try to consume a token
        if await bucket.consume():
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
            response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))

            return response

        # Rate limit exceeded
        logger.warning(
            "Rate limit exceeded",
            client_id=client_id,
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
        )

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate Limit Exceeded",
                "message": f"Too many requests. Please retry after {60} seconds.",
                "request_id": getattr(request.state, "request_id", None),
            },
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + 60)),
            },
        )
