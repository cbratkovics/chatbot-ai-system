"""Distributed tracing with OpenTelemetry."""

import logging

from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ..app.config import settings

logger = logging.getLogger(__name__)


class TracingManager:
    """Manages distributed tracing with OpenTelemetry."""

    def __init__(self, service_name: str = None, jaeger_endpoint: str = None):
        self.service_name = service_name or settings.app_name
        self.jaeger_endpoint = jaeger_endpoint or settings.jaeger_endpoint
        self.tracer = None
        self.initialized = False

    def initialize(self, app=None):
        """Initialize tracing."""
        if not settings.enable_tracing:
            logger.info("Tracing disabled by configuration")
            return

        if self.initialized:
            logger.warning("Tracing already initialized")
            return

        try:
            # Create resource
            resource = Resource.create(
                {
                    "service.name": self.service_name,
                    "service.version": settings.app_version,
                    "deployment.environment": "production" if not settings.debug else "development",
                }
            )

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Add Jaeger exporter if endpoint configured
            if self.jaeger_endpoint:
                jaeger_exporter = JaegerExporter(
                    agent_host_name=self.jaeger_endpoint.split(":")[0],
                    agent_port=int(self.jaeger_endpoint.split(":")[1])
                    if ":" in self.jaeger_endpoint
                    else 6831,
                )

                span_processor = BatchSpanProcessor(jaeger_exporter)
                provider.add_span_processor(span_processor)

                logger.info(f"Jaeger exporter configured: {self.jaeger_endpoint}")

            # Set tracer provider
            trace.set_tracer_provider(provider)

            # Get tracer
            self.tracer = trace.get_tracer(__name__)

            # Instrument FastAPI if app provided
            if app:
                FastAPIInstrumentor.instrument_app(app)
                logger.info("FastAPI instrumentation enabled")

            self.initialized = True
            logger.info("Tracing initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")

    def get_tracer(self):
        """Get tracer instance."""
        if not self.initialized:
            self.initialize()

        return self.tracer or trace.get_tracer(__name__)

    def create_span(self, name: str, attributes: dict = None):
        """Create a new span."""
        tracer = self.get_tracer()
        span = tracer.start_span(name)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        return span

    def get_current_span(self):
        """Get current active span."""
        return trace.get_current_span()

    def add_event(self, name: str, attributes: dict = None):
        """Add event to current span."""
        span = self.get_current_span()
        if span:
            span.add_event(name, attributes=attributes)

    def set_attribute(self, key: str, value):
        """Set attribute on current span."""
        span = self.get_current_span()
        if span:
            span.set_attribute(key, value)

    def record_exception(self, exception: Exception):
        """Record exception in current span."""
        span = self.get_current_span()
        if span:
            span.record_exception(exception)
            span.set_status(trace.Status(trace.StatusCode.ERROR))


# Global tracing manager instance
tracing_manager = TracingManager()
