"""Rate limiting middleware."""

import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from chatbot_ai_system.config.settings import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm."""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = RateLimiter()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        await self.rate_limiter.check(request)
        response = await call_next(request)
        return response


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self):
        self.buckets: dict[str, dict] = defaultdict(
            lambda: {
                "tokens": settings.rate_limit_requests,
                "last_refill": time.time(),
            }
        )

    async def check(self, request: Request) -> None:
        """Check if request is within rate limits."""
        # Get client identifier (IP or API key)
        client_id = request.client.host if request.client else "anonymous"

        bucket = self.buckets[client_id]
        now = time.time()

        # Refill tokens
        time_passed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            settings.rate_limit_requests,
            bucket["tokens"]
            + (time_passed * settings.rate_limit_requests / settings.rate_limit_period),
        )
        bucket["last_refill"] = now

        # Check if request is allowed
        if bucket["tokens"] < 1:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(settings.rate_limit_period)},
            )

        # Consume token
        bucket["tokens"] -= 1
