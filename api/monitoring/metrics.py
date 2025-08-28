"""Prometheus metrics collection."""


from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class MetricsCollector:
    """Collects and exposes Prometheus metrics."""

    def __init__(self):
        # Request metrics
        self.http_requests_total = Counter(
            "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
        )

        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["method", "endpoint"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        )

        # WebSocket metrics
        self.websocket_connections_active = Gauge(
            "websocket_connections_active", "Active WebSocket connections"
        )

        self.websocket_messages_total = Counter(
            "websocket_messages_total",
            "Total WebSocket messages",
            ["direction", "type"],  # direction: sent/received, type: message type
        )

        # Provider metrics
        self.provider_requests_total = Counter(
            "provider_requests_total", "Total provider requests", ["provider", "model", "status"]
        )

        self.provider_latency_seconds = Histogram(
            "provider_latency_seconds",
            "Provider response latency",
            ["provider", "model"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        self.provider_tokens_total = Counter(
            "provider_tokens_total",
            "Total tokens processed",
        )

        self.provider_cost_total = Counter(
            "provider_cost_total", "Total provider cost in cents", ["provider", "model"]
        )

        # Cache metrics
        self.cache_hits_total = Counter("cache_hits_total", "Total cache hits", ["tenant"])

        self.cache_misses_total = Counter("cache_misses_total", "Total cache misses", ["tenant"])

        self.cache_hit_rate = Gauge("cache_hit_rate", "Cache hit rate percentage")

        self.cache_entries_total = Gauge("cache_entries_total", "Total cache entries")

        # System metrics
        self.active_tenants = Gauge("active_tenants", "Number of active tenants")

        self.active_users = Gauge("active_users", "Number of active users")

        self.conversations_active = Gauge("conversations_active", "Active conversations")

        # Rate limiting metrics
        self.rate_limit_exceeded_total = Counter(
            "rate_limit_exceeded_total", "Rate limit exceeded count", ["tenant", "endpoint"]
        )

        # Error metrics
        self.errors_total = Counter("errors_total", "Total errors", ["type", "code"])

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            "circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["provider"],
        )

        self.circuit_breaker_failures = Counter(
            "circuit_breaker_failures", "Circuit breaker failure count", ["provider"]
        )

    def record_http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics."""
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()

        self.http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
            duration
        )

    def record_websocket_connection(self, delta: int):
        """Record WebSocket connection change."""
        if delta > 0:
            self.websocket_connections_active.inc(delta)
        else:
            self.websocket_connections_active.dec(abs(delta))

    def record_websocket_message(self, direction: str, message_type: str):
        """Record WebSocket message."""
        self.websocket_messages_total.labels(direction=direction, type=message_type).inc()

    def record_provider_request(
        self,
        provider: str,
        model: str,
        status: str,
        latency: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_cents: float = 0,
    ):
        """Record provider request metrics."""
        self.provider_requests_total.labels(provider=provider, model=model, status=status).inc()

        if status == "success":
            self.provider_latency_seconds.labels(provider=provider, model=model).observe(latency)

            if prompt_tokens > 0:
                self.provider_tokens_total.labels(
                    provider=provider, model=model, type="prompt"
                ).inc(prompt_tokens)

            if completion_tokens > 0:
                self.provider_tokens_total.labels(
                    provider=provider, model=model, type="completion"
                ).inc(completion_tokens)

            if cost_cents > 0:
                self.provider_cost_total.labels(provider=provider, model=model).inc(cost_cents)

    def record_cache_access(self, hit: bool, tenant: str | None = None):
        """Record cache access."""
        tenant = tenant or "global"

        if hit:
            self.cache_hits_total.labels(tenant=tenant).inc()
        else:
            self.cache_misses_total.labels(tenant=tenant).inc()

    def update_cache_stats(self, hit_rate: float, total_entries: int):
        """Update cache statistics."""
        self.cache_hit_rate.set(hit_rate * 100)
        self.cache_entries_total.set(total_entries)

    def update_system_stats(
        self, active_tenants: int, active_users: int, active_conversations: int
    ):
        """Update system statistics."""
        self.active_tenants.set(active_tenants)
        self.active_users.set(active_users)
        self.conversations_active.set(active_conversations)

    def record_rate_limit_exceeded(self, tenant: str, endpoint: str):
        """Record rate limit exceeded."""
        self.rate_limit_exceeded_total.labels(tenant=tenant, endpoint=endpoint).inc()

    def record_error(self, error_type: str, error_code: str):
        """Record error occurrence."""
        self.errors_total.labels(type=error_type, code=error_code).inc()

    def update_circuit_breaker(self, provider: str, state: str, failures: int = 0):
        """Update circuit breaker metrics."""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        self.circuit_breaker_state.labels(provider=provider).set(state_map.get(state, 0))

        if failures > 0:
            self.circuit_breaker_failures.labels(provider=provider).inc(failures)

    def get_metrics(self) -> bytes:
        """Generate metrics in Prometheus format."""
        return generate_latest()

    async def metrics_endpoint(self) -> Response:
        """FastAPI endpoint for metrics."""
        metrics = self.get_metrics()
        return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)


# Global metrics collector instance
metrics_collector = MetricsCollector()
