"""Metrics collection and reporting."""

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from prometheus_client import Counter, Gauge, Histogram, Summary


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time."""
    
    timestamp: float
    counters: Dict[str, float] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)
    histograms: Dict[str, Dict[str, float]] = field(default_factory=dict)
    summaries: Dict[str, Dict[str, float]] = field(default_factory=dict)


class MetricsCollector:
    """Centralized metrics collection."""
    
    def __init__(self, namespace: str = "chatbot"):
        """Initialize metrics collector."""
        self.namespace = namespace
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._summaries: Dict[str, Summary] = {}
        self._custom_metrics: Dict[str, Any] = defaultdict(float)
        
        # Initialize default metrics
        self._init_default_metrics()
    
    def _init_default_metrics(self):
        """Initialize default application metrics."""
        # Request metrics
        self._counters["requests_total"] = Counter(
            f"{self.namespace}_requests_total",
            "Total number of requests",
            ["method", "endpoint", "status"],
        )
        
        self._histograms["request_duration"] = Histogram(
            f"{self.namespace}_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint"],
        )
        
        # Model metrics
        self._counters["model_requests"] = Counter(
            f"{self.namespace}_model_requests_total",
            "Total model requests",
            ["provider", "model", "status"],
        )
        
        self._histograms["model_latency"] = Histogram(
            f"{self.namespace}_model_latency_seconds",
            "Model response latency",
            ["provider", "model"],
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
    
    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
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
        labels: Optional[Dict[str, str]] = None,
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
        labels: Optional[Dict[str, str]] = None,
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
        labels: Optional[Dict[str, str]] = None,
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
    ):
        """Record HTTP request metrics."""
        labels = {"method": method, "endpoint": endpoint, "status": str(status)}
        self.increment_counter("requests_total", labels=labels)
        self.observe_histogram(
            "request_duration",
            duration,
            labels={"method": method, "endpoint": endpoint},
        )
    
    def record_model_request(
        self,
        provider: str,
        model: str,
        success: bool,
        latency: float,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ):
        """Record model request metrics."""
        status = "success" if success else "failure"
        
        self.increment_counter(
            "model_requests",
            labels={"provider": provider, "model": model, "status": status},
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
    
    def record_cache_access(
        self,
        cache_type: str,
        hit: bool,
    ):
        """Record cache access metrics."""
        if hit:
            self.increment_counter("cache_hits", labels={"cache_type": cache_type})
        else:
            self.increment_counter("cache_misses", labels={"cache_type": cache_type})
    
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
    
    def get_snapshot(self) -> MetricSnapshot:
        """Get current metrics snapshot."""
        snapshot = MetricSnapshot(timestamp=time.time())
        
        # Add custom metrics
        snapshot.counters.update(self._custom_metrics)
        
        return snapshot
    
    def reset_custom_metrics(self):
        """Reset custom metrics."""
        self._custom_metrics.clear()


# Global metrics instance
metrics = MetricsCollector()