"""Distributed tracing support."""

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from chatbot_ai_system.config.settings import settings
from chatbot_ai_system.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SpanContext:
    """Context for a tracing span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    operation: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"


class TracingManager:
    """Manager for distributed tracing."""

    def __init__(self):
        """Initialize tracing manager."""
        self.enabled = settings.JAEGER_ENABLED
        self.tracer = None
        self._active_spans: dict[str, SpanContext] = {}

        if self.enabled:
            self._setup_tracing()

    def _setup_tracing(self):
        """Set up OpenTelemetry tracing."""
        try:
            resource = Resource.create(
                {
                    "service.name": settings.JAEGER_SERVICE_NAME,
                    "service.version": settings.VERSION,
                }
            )

            provider = TracerProvider(resource=resource)

            jaeger_exporter = JaegerExporter(
                agent_host_name=settings.JAEGER_AGENT_HOST,
                agent_port=settings.JAEGER_AGENT_PORT,
            )

            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            trace.set_tracer_provider(provider)

            self.tracer = trace.get_tracer(__name__)
            logger.info(
                "Tracing initialized",
                host=settings.JAEGER_AGENT_HOST,
                port=settings.JAEGER_AGENT_PORT,
            )
        except Exception as e:
            logger.error("Failed to initialize tracing", error=str(e))
            self.enabled = False

    @contextmanager
    def span(
        self,
        operation: str,
        tags: dict[str, Any] | None = None,
        parent_span: SpanContext | None = None,
    ):
        """Create a new tracing span."""
        if not self.enabled:
            yield None
            return

        span_context = SpanContext(
            trace_id=parent_span.trace_id if parent_span else str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_span_id=parent_span.span_id if parent_span else None,
            operation=operation,
            tags=tags or {},
        )

        self._active_spans[span_context.span_id] = span_context

        try:
            if self.tracer:
                with self.tracer.start_as_current_span(operation) as span:
                    if tags:
                        for key, value in tags.items():
                            span.set_attribute(key, str(value))

                    span_context.span = span
                    yield span_context
            else:
                yield span_context
        except Exception as e:
            span_context.status = "error"
            span_context.logs.append(
                {
                    "timestamp": time.time(),
                    "level": "error",
                    "message": str(e),
                }
            )
            raise
        finally:
            span_context.end_time = time.time()
            if span_context.span_id in self._active_spans:
                del self._active_spans[span_context.span_id]

    def add_tags(self, span_id: str, tags: dict[str, Any]):
        """Add tags to an active span."""
        if span_id in self._active_spans:
            self._active_spans[span_id].tags.update(tags)

    def add_log(self, span_id: str, message: str, level: str = "info"):
        """Add log to an active span."""
        if span_id in self._active_spans:
            self._active_spans[span_id].logs.append(
                {
                    "timestamp": time.time(),
                    "level": level,
                    "message": message,
                }
            )

    def get_active_trace_id(self) -> str | None:
        """Get current active trace ID."""
        if self._active_spans:
            return next(iter(self._active_spans.values())).trace_id
        return None

    def inject_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Inject tracing headers for propagation."""
        trace_id = self.get_active_trace_id()
        if trace_id:
            headers["X-Trace-Id"] = trace_id

            # Add B3 headers for compatibility
            if self._active_spans:
                span = next(iter(self._active_spans.values()))
                headers["X-B3-TraceId"] = span.trace_id
                headers["X-B3-SpanId"] = span.span_id
                if span.parent_span_id:
                    headers["X-B3-ParentSpanId"] = span.parent_span_id

        return headers

    def extract_headers(self, headers: dict[str, str]) -> SpanContext | None:
        """Extract tracing context from headers."""
        trace_id = headers.get("X-Trace-Id") or headers.get("X-B3-TraceId")
        span_id = headers.get("X-B3-SpanId")
        parent_span_id = headers.get("X-B3-ParentSpanId")

        if trace_id:
            return SpanContext(
                trace_id=trace_id,
                span_id=span_id or str(uuid.uuid4()),
                parent_span_id=parent_span_id,
            )

        return None


# Global tracing instance
tracing = TracingManager()
