"""Metrics middleware for Prometheus."""

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge
from starlette.middleware.base import BaseHTTPMiddleware

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


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect metrics for Prometheus."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request metrics."""
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)
        
        # Track active requests
        ACTIVE_REQUESTS.inc()
        
        # Track request duration
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(duration)
            
            return response
            
        finally:
            ACTIVE_REQUESTS.dec()