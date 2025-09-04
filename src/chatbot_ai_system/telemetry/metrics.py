"""Metrics collection and reporting with Prometheus integration."""

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from prometheus_client import (REGISTRY, Counter, Gauge, Histogram, Info,
                               Summary, generate_latest)


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time."""

    timestamp: float
    counters: dict[str, float] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, dict[str, float]] = field(default_factory=dict)
    summaries: dict[str, dict[str, float]] = field(default_factory=dict)


class MetricsCollector:
    """Centralized metrics collection with Prometheus integration."""

    def __init__(self, namespace: str = "chatbot_ai_system"):
        """Initialize metrics collector."""
        self.namespace = namespace
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._summaries: dict[str, Summary] = {}
        self._info: dict[str, Info] = {}
        self._custom_metrics: dict[str, Any] = defaultdict(float)

        # SLI/SLO tracking
        self._sli_metrics: dict[str, float] = {}
        self._slo_targets: dict[str, float] = {
            "availability": 0.995,  # 99.5%
            "latency_p95": 0.2,  # 200ms
            "error_rate": 0.005,  # 0.5%
        }

        # Initialize default metrics
        self._init_default_metrics()
        self._init_sli_metrics()

    def _init_default_metrics(self):
        """Initialize default application metrics."""
        # Build info
        self._info["build"] = Info(
            f"{self.namespace}_build_info",
            "Build information",
        )

        # Request metrics
        self._counters["requests_total"] = Counter(
            f"{self.namespace}_requests_total",
            "Total number of requests",
            ["method", "endpoint", "status", "tenant_id"],
        )

        self._histograms["request_duration"] = Histogram(
            f"{self.namespace}_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        # Model metrics
        self._counters["model_requests"] = Counter(
            f"{self.namespace}_model_requests_total",
            "Total model requests",
            ["provider", "model", "status", "tenant_id"],
        )

        self._histograms["model_latency"] = Histogram(
            f"{self.namespace}_model_latency_seconds",
            "Model response latency",
            ["provider", "model"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
        )

        # Cost tracking
        self._counters["cost_usd_total"] = Counter(
            f"{self.namespace}_cost_usd_total",
            "Total cost in USD",
            ["provider", "model", "tenant_id"],
        )

        # Token metrics
        self._counters["tokens_processed"] = Counter(
            f"{self.namespace}_tokens_processed_total",
            "Total tokens processed",
            ["provider", "model", "type"],
        )

        # WebSocket metrics
        self._gauges["websocket_connections"] = Gauge(
            f"{self.namespace}_websocket_connections",
            "Current WebSocket connections",
        )

        # Cache metrics
        self._counters["cache_hits"] = Counter(
            f"{self.namespace}_cache_hits_total",
            "Cache hits",
            ["cache_type"],
        )

        self._counters["cache_misses"] = Counter(
            f"{self.namespace}_cache_misses_total",
            "Cache misses",
            ["cache_type"],
        )

        # Error metrics
        self._counters["errors"] = Counter(
            f"{self.namespace}_errors_total",
            "Total errors",
            ["error_type", "component"],
        )

        # System metrics
        self._gauges["memory_usage"] = Gauge(
            f"{self.namespace}_memory_usage_bytes",
            "Memory usage in bytes",
        )

        self._gauges["cpu_usage"] = Gauge(
            f"{self.namespace}_cpu_usage_percent",
            "CPU usage percentage",
        )

        # Circuit breaker metrics
        self._gauges["circuit_breaker_state"] = Gauge(
            f"{self.namespace}_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["provider"],
        )

        # Rate limiting metrics
        self._counters["rate_limit_exceeded"] = Counter(
            f"{self.namespace}_rate_limit_exceeded_total",
            "Rate limit exceeded count",
            ["tenant_id", "limit_type"],
        )

    def _init_sli_metrics(self):
        """Initialize SLI metrics for SLO tracking."""
        # Availability SLI
        self._gauges["sli_availability"] = Gauge(
            f"{self.namespace}_sli_availability",
            "Service availability (success rate)",
        )

        # Latency SLI
        self._summaries["sli_latency"] = Summary(
            f"{self.namespace}_sli_latency_seconds",
            "Request latency for SLI",
            ["endpoint"],
        )

        # Error rate SLI
        self._gauges["sli_error_rate"] = Gauge(
            f"{self.namespace}_sli_error_rate",
            "Error rate",
        )

        # SLO compliance
        self._gauges["slo_compliance"] = Gauge(
            f"{self.namespace}_slo_compliance",
            "SLO compliance (1=meeting, 0=not meeting)",
            ["slo_name"],
        )

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ):
        """Increment a counter metric."""
        if name in self._counters:
            if labels:
                self._counters[name].labels(**labels).inc(value)
            else:
                self._counters[name].inc(value)
        else:
            self._custom_metrics[name] += value

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ):
        """Set a gauge metric."""
        if name in self._gauges:
            if labels:
                self._gauges[name].labels(**labels).set(value)
            else:
                self._gauges[name].set(value)
        else:
            self._custom_metrics[name] = value

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ):
        """Observe a histogram value."""
        if name in self._histograms:
            if labels:
                self._histograms[name].labels(**labels).observe(value)
            else:
                self._histograms[name].observe(value)

    @contextmanager
    def timer(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.observe_histogram(name, duration, labels)

    def record_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
        tenant_id: str | None = None,
    ):
        """Record HTTP request metrics."""
        labels = {
            "method": method,
            "endpoint": endpoint,
            "status": str(status),
            "tenant_id": tenant_id or "unknown",
        }
        self.increment_counter("requests_total", labels=labels)
        self.observe_histogram(
            "request_duration",
            duration,
            labels={"method": method, "endpoint": endpoint},
        )

        # Update SLI metrics
        self._update_sli_metrics(status, duration, endpoint)

    def record_model_request(
        self,
        provider: str,
        model: str,
        success: bool,
        latency: float,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost: float = 0.0,
        tenant_id: str | None = None,
    ):
        """Record model request metrics."""
        status = "success" if success else "failure"
        tenant = tenant_id or "unknown"

        self.increment_counter(
            "model_requests",
            labels={"provider": provider, "model": model, "status": status, "tenant_id": tenant},
        )

        if success:
            self.observe_histogram(
                "model_latency",
                latency,
                labels={"provider": provider, "model": model},
            )

            if tokens_input > 0:
                self.increment_counter(
                    "tokens_processed",
                    value=tokens_input,
                    labels={"provider": provider, "model": model, "type": "input"},
                )

            if tokens_output > 0:
                self.increment_counter(
                    "tokens_processed",
                    value=tokens_output,
                    labels={"provider": provider, "model": model, "type": "output"},
                )

            if cost > 0:
                self.increment_counter(
                    "cost_usd_total",
                    value=cost,
                    labels={"provider": provider, "model": model, "tenant_id": tenant},
                )

    def record_cache_hit(self, cache_type: str = "default"):
        """Record cache hit."""
        self.increment_counter("cache_hits", labels={"cache_type": cache_type})

    def record_cache_miss(self, cache_type: str = "default"):
        """Record cache miss."""
        self.increment_counter("cache_misses", labels={"cache_type": cache_type})

    def record_circuit_breaker_state(self, provider: str, state: int):
        """Record circuit breaker state (0=closed, 1=open, 2=half-open)."""
        self.set_gauge("circuit_breaker_state", value=state, labels={"provider": provider})

    def record_rate_limit_exceeded(self, tenant_id: str, limit_type: str = "api"):
        """Record rate limit exceeded event."""
        self.increment_counter(
            "rate_limit_exceeded",
            labels={"tenant_id": tenant_id, "limit_type": limit_type},
        )

    def record_error(
        self,
        error_type: str,
        component: str,
    ):
        """Record error metrics."""
        self.increment_counter(
            "errors",
            labels={"error_type": error_type, "component": component},
        )

    def _update_sli_metrics(self, status: int, duration: float, endpoint: str):
        """Update SLI metrics based on request."""
        # Availability (success rate)
        is_success = 200 <= status < 500
        if "availability_total" not in self._sli_metrics:
            self._sli_metrics["availability_total"] = 0
            self._sli_metrics["availability_success"] = 0

        self._sli_metrics["availability_total"] += 1
        if is_success:
            self._sli_metrics["availability_success"] += 1

        availability = (
            self._sli_metrics["availability_success"] / self._sli_metrics["availability_total"]
            if self._sli_metrics["availability_total"] > 0
            else 1.0
        )
        self.set_gauge("sli_availability", availability)

        # Latency
        if endpoint in self._summaries.get("sli_latency", {}):
            self._summaries["sli_latency"].labels(endpoint=endpoint).observe(duration)

        # Error rate
        error_rate = 1.0 - availability
        self.set_gauge("sli_error_rate", error_rate)

        # Check SLO compliance
        self._check_slo_compliance(availability, error_rate)

    def _check_slo_compliance(self, availability: float, error_rate: float):
        """Check and record SLO compliance."""
        # Availability SLO
        self.set_gauge(
            "slo_compliance",
            value=1.0 if availability >= self._slo_targets["availability"] else 0.0,
            labels={"slo_name": "availability"},
        )

        # Error rate SLO
        self.set_gauge(
            "slo_compliance",
            value=1.0 if error_rate <= self._slo_targets["error_rate"] else 0.0,
            labels={"slo_name": "error_rate"},
        )

    def set_build_info(self, version: str, commit: str, build_time: str):
        """Set build information."""
        if "build" in self._info:
            self._info["build"].info(
                {
                    "version": version,
                    "commit": commit,
                    "build_time": build_time,
                }
            )

    def get_snapshot(self) -> MetricSnapshot:
        """Get current metrics snapshot."""
        snapshot = MetricSnapshot(timestamp=time.time())

        # Add custom metrics
        snapshot.counters.update(self._custom_metrics)

        # Add SLI metrics
        snapshot.gauges["sli_availability"] = self._sli_metrics.get(
            "availability_success", 0
        ) / max(self._sli_metrics.get("availability_total", 1), 1)

        return snapshot

    def reset_custom_metrics(self):
        """Reset custom metrics."""
        self._custom_metrics.clear()

    def export_prometheus(self) -> bytes:
        """Export metrics in Prometheus format."""
        return generate_latest(REGISTRY)


# Global metrics instance
metrics_collector = MetricsCollector()
