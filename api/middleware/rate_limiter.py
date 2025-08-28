"""Rate limiting middleware for API protection."""

import asyncio
import logging
import time
from collections import deque

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket implementation for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket."""
        async with self._lock:
            now = time.time()

            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    @property
    def remaining_tokens(self) -> int:
        """Get the current number of available tokens."""
        return int(self.tokens)

    def time_until_refill(self, needed_tokens: int) -> float:
        """Calculate time until we have enough tokens."""
        if self.tokens >= needed_tokens:
            return 0.0

        tokens_needed = needed_tokens - self.tokens
        return tokens_needed / self.refill_rate


class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""

    def __init__(self, window_size: int, max_requests: int):
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests = deque()
        self._lock = asyncio.Lock()

    async def is_allowed(self) -> tuple[bool, dict[str, int]]:
        """Check if request is allowed within the sliding window."""
        async with self._lock:
            now = time.time()

            # Remove expired requests
            while self.requests and self.requests[0] <= now - self.window_size:
                self.requests.popleft()

            # Check if we're under the limit
            current_requests = len(self.requests)
            allowed = current_requests < self.max_requests

            if allowed:
                self.requests.append(now)

            # Calculate reset time
            reset_time = int(now + self.window_size) if self.requests else int(now)

            return allowed, {
                "remaining": max(0, self.max_requests - current_requests - (1 if allowed else 0)),
                "reset": reset_time,
                "limit": self.max_requests,
                "used": current_requests + (1 if allowed else 0),
            }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Advanced rate limiting middleware with multiple algorithms.

    Features:
    - Token bucket for burst handling
    - Sliding window for precise limits
    - Tenant-specific rate limits
    - Per-endpoint rate limits
    - IP-based rate limits
    - Graceful degradation
    """

    def __init__(self, app, default_rpm: int = 60, burst_size: int = 10):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.burst_size = burst_size

        # Rate limiters by key (tenant_id:endpoint, ip:endpoint, etc.)
        self.token_buckets: dict[str, TokenBucket] = {}
        self.sliding_windows: dict[str, SlidingWindowCounter] = {}

        # Endpoint-specific limits
        self.endpoint_limits = {
            "/api/v1/chat/completions": {"rpm": 100, "burst": 20},
            "/api/v1/chat/stream": {"rpm": 50, "burst": 10},
            "/api/v1/embeddings": {"rpm": 200, "burst": 50},
            "/api/v1/models": {"rpm": 30, "burst": 5},
        }

        # Cleanup task for old rate limiters
        asyncio.create_task(self._cleanup_old_limiters())

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to requests."""

        # Skip rate limiting for health checks and static files
        if request.url.path in ["/", "/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        try:
            # Get rate limiting key and limits
            rate_limit_key = self._get_rate_limit_key(request)
            rpm, burst = self._get_rate_limits(request)

            # Check rate limits
            allowed, headers = await self._check_rate_limit(rate_limit_key, rpm, burst)

            if not allowed:
                # Rate limit exceeded
                logger.warning(f"Rate limit exceeded for key: {rate_limit_key}")

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Limit: {rpm} requests per minute.",
                        "retry_after": headers.get("retry_after", 60),
                    },
                    headers={
                        "X-RateLimit-Limit": str(rpm),
                        "X-RateLimit-Remaining": str(headers.get("remaining", 0)),
                        "X-RateLimit-Reset": str(headers.get("reset", int(time.time()) + 60)),
                        "Retry-After": str(headers.get("retry_after", 60)),
                    },
                )

            # Process the request
            response = await call_next(request)

            # Add rate limit headers to response
            response.headers.update(
                {
                    "X-RateLimit-Limit": str(rpm),
                    "X-RateLimit-Remaining": str(headers.get("remaining", 0)),
                    "X-RateLimit-Reset": str(headers.get("reset", int(time.time()) + 60)),
                }
            )

            return response

        except Exception as e:
            logger.error(f"Rate limiting error: {str(e)}")
            # Allow request to proceed on rate limiting errors
            return await call_next(request)

    def _get_rate_limit_key(self, request: Request) -> str:
        """Generate unique key for rate limiting."""

        # Priority: tenant_id > user_id > ip_address
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return f"tenant:{tenant_id}:{request.url.path}"

        # Use IP address as fallback
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}:{request.url.path}"

    def _get_rate_limits(self, request: Request) -> tuple[int, int]:
        """Get rate limits for the request."""

        # Check endpoint-specific limits
        endpoint_config = self.endpoint_limits.get(request.url.path)
        if endpoint_config:
            return endpoint_config["rpm"], endpoint_config["burst"]

        # Check tenant-specific limits
        tenant_context = getattr(request.state, "tenant", None)
        if tenant_context:
            tenant_rpm = tenant_context.usage_limits.get("requests_per_minute")
            if tenant_rpm:
                return tenant_rpm, min(tenant_rpm // 5, 20)  # Burst is 20% of RPM

        # Default limits
        return self.default_rpm, self.burst_size

    async def _check_rate_limit(
        self, key: str, rpm: int, burst: int
    ) -> tuple[bool, dict[str, int]]:
        """Check if request is allowed based on rate limits."""

        # Token bucket for burst handling
        bucket_key = f"bucket:{key}"
        if bucket_key not in self.token_buckets:
            # Refill rate: RPM / 60 tokens per second
            refill_rate = rpm / 60.0
            self.token_buckets[bucket_key] = TokenBucket(burst, refill_rate)

        bucket = self.token_buckets[bucket_key]
        bucket_allowed = await bucket.consume(1)

        # Sliding window for precise RPM limits
        window_key = f"window:{key}"
        if window_key not in self.sliding_windows:
            self.sliding_windows[window_key] = SlidingWindowCounter(60, rpm)  # 60 second window

        window = self.sliding_windows[window_key]
        window_allowed, window_info = await window.is_allowed()

        # Request is allowed if both bucket and window allow it
        allowed = bucket_allowed and window_allowed

        # Calculate retry after time
        retry_after = 60
        if not bucket_allowed:
            retry_after = min(retry_after, int(bucket.time_until_refill(1)) + 1)

        return allowed, {
            "remaining": window_info["remaining"],
            "reset": window_info["reset"],
            "retry_after": retry_after,
        }

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check common proxy headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP from the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        return request.client.host if request.client else "unknown"

    async def _cleanup_old_limiters(self):
        """Periodically cleanup old rate limiters to prevent memory leaks."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                current_time = time.time()
                cleanup_threshold = current_time - 3600  # Remove limiters older than 1 hour

                # Cleanup token buckets
                old_buckets = [
                    key
                    for key, bucket in self.token_buckets.items()
                    if bucket.last_refill < cleanup_threshold
                ]
                for key in old_buckets:
                    del self.token_buckets[key]

                # Cleanup sliding windows
                old_windows = []
                for key, window in self.sliding_windows.items():
                    if not window.requests or window.requests[-1] < cleanup_threshold:
                        old_windows.append(key)

                for key in old_windows:
                    del self.sliding_windows[key]

                if old_buckets or old_windows:
                    logger.info(
                        f"Cleaned up {len(old_buckets)} token buckets and "
                        f"{len(old_windows)} sliding windows"
                    )

            except Exception as e:
                logger.error(f"Rate limiter cleanup error: {str(e)}")

    def get_rate_limit_status(self, key: str) -> dict[str, any]:
        """Get current rate limit status for a key (for monitoring)."""
        bucket_key = f"bucket:{key}"
        window_key = f"window:{key}"

        status = {"key": key, "timestamp": time.time()}

        if bucket_key in self.token_buckets:
            bucket = self.token_buckets[bucket_key]
            status["bucket"] = {
                "remaining_tokens": bucket.remaining_tokens,
                "capacity": bucket.capacity,
                "refill_rate": bucket.refill_rate,
            }

        if window_key in self.sliding_windows:
            window = self.sliding_windows[window_key]
            status["window"] = {
                "current_requests": len(window.requests),
                "max_requests": window.max_requests,
                "window_size": window.window_size,
            }

        return status
