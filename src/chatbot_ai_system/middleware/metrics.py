"""Prometheus request metrics middleware (pure ASGI).

Records ``http_requests_total{method,endpoint,status}`` and
``http_request_duration_seconds{method,endpoint}``; the duration covers the whole response,
including a streamed body. Pure ASGI rather than ``BaseHTTPMiddleware``: those make uvicorn close
streaming responses on keep-alive connections after 5 s.
"""

import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Define metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Active HTTP requests",
)


class MetricsMiddleware:
    """Collect request count and latency for Prometheus."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Skip the metrics endpoint itself and non-HTTP traffic (websockets, lifespan).
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        endpoint = scope.get("path", "")
        status = 0
        start_time = time.time()
        ACTIVE_REQUESTS.inc()

        async def send_observing(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_observing)
        finally:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(
                time.time() - start_time
            )
            ACTIVE_REQUESTS.dec()
