"""Coarse per-IP request limit for every route (pure ASGI).

Replaces the ``slowapi`` middleware, which is a Starlette ``BaseHTTPMiddleware`` and, under
uvicorn, closed streaming responses on keep-alive connections five seconds after the previous
request on that connection (``tests/unit/test_keepalive_streaming.py``). The demo guardrails
(ADR 0004) remain the real per-IP limits for the chat route; this is the outer safety net for
everything else, configured by ``RATE_LIMIT_ENABLED`` / ``RATE_LIMIT_REQUESTS`` /
``RATE_LIMIT_PERIOD``.
"""

import time
from collections import deque
from typing import Deque, Dict

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from .errors import error_response
from .guardrails import client_ip_from_headers

EXEMPT_PATHS = {"/health", "/metrics"}


class RateLimitMiddleware:
    """Sliding window: at most ``limit`` requests per ``period`` seconds per client IP."""

    def __init__(self, app: ASGIApp, limit: int = 100, period: int = 60, enabled: bool = True):
        self.app = app
        self.limit = max(1, limit)
        self.period = max(1, period)
        self.enabled = enabled
        self._hits: Dict[str, Deque[float]] = {}

    def _retry_after(self, client: str, now: float) -> int:
        """0 when the request is allowed; otherwise seconds until the oldest hit expires."""
        window = self._hits.setdefault(client, deque())
        cutoff = now - self.period
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= self.limit:
            return max(1, int(window[0] + self.period - now) + 1)
        window.append(now)
        return 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] != "http" or scope.get("path") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        peer = scope.get("client")
        client = client_ip_from_headers(headers.get("x-forwarded-for"), peer[0] if peer else None)
        retry_after = self._retry_after(client, time.monotonic())
        if retry_after:
            response = error_response(
                429,
                "rate_limited",
                f"Rate limit exceeded: {self.limit} requests per {self.period} s",
                request_id=scope.get("state", {}).get("request_id"),
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
