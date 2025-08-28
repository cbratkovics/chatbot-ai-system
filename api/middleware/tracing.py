"""
OpenTelemetry Tracing Middleware
Author: Christopher J. Bratkovics
Purpose: Distributed tracing for observability
"""

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger(__name__)


class TracingMiddleware:
    """
    Comprehensive tracing middleware for AI chatbot system.
    Captures detailed spans for request lifecycle.
    """

    def __init__(
        self,
        service_name: str = "ai-chatbot-system",
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831,
        enabled: bool = True,
    ):
        self.service_name = service_name
        self.enabled = enabled
        self.tracer = None

        if self.enabled:
            self._initialize_tracing(jaeger_host, jaeger_port)

    def _initialize_tracing(self, host: str, port: int):
        """Initialize OpenTelemetry with Jaeger exporter"""

        # Create resource identifying the service
        resource = Resource.create(
            {
                SERVICE_NAME: self.service_name,
                SERVICE_VERSION: "1.0.0",
                "deployment.environment": "production",
                "service.namespace": "ai-platform",
                "service.instance.id": "instance-1",
            }
        )

        # Configure tracer provider
        provider = TracerProvider(resource=resource)

        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=host, agent_port=port, max_tag_value_length=1024
        )

        # Add batch processor for efficient span export
        span_processor = BatchSpanProcessor(
            jaeger_exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            max_export_interval_millis=5000,
        )

        provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer instance
        self.tracer = trace.get_tracer(
            instrumenting_module_name=__name__, instrumenting_library_version="1.0.0"
        )

        # Auto-instrument libraries
        FastAPIInstrumentor.instrument(tracer_provider=provider)
        RequestsInstrumentor.instrument(tracer_provider=provider)
        LoggingInstrumentor.instrument(tracer_provider=provider)

        logger.info(f"Tracing initialized with Jaeger at {host}:{port}")

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process request with comprehensive tracing"""

        if not self.enabled or not self.tracer:
            return await call_next(request)

        # Extract trace context from headers if present
        context = extract(request.headers)

        # Start main request span
        with self.tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            kind=SpanKind.SERVER,
            context=context,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname,
                "http.target": request.url.path,
                "http.user_agent": request.headers.get("user-agent", ""),
                "net.peer.ip": request.client.host if request.client else "unknown",
            },
        ) as span:
            try:
                # Add request processing spans
                response = await self._process_with_spans(request, call_next, span)

                # Set response attributes
                span.set_attribute("http.status_code", response.status_code)

                if response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR))
                else:
                    span.set_status(Status(StatusCode.OK))

                return response

            except Exception as e:
                # Record exception in span
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    async def _process_with_spans(
        self, request: Request, call_next: Callable, parent_span: trace.Span
    ) -> Response:
        """Process request with detailed sub-spans"""

        # Authentication span
        with self.tracer.start_as_current_span("authentication") as auth_span:
            auth_start = time.time()
            # Simulate authentication check
            auth_span.set_attribute("auth.method", "bearer_token")
            auth_span.set_attribute("auth.duration_ms", (time.time() - auth_start) * 1000)

        # Guardrails processing span
        with self.tracer.start_as_current_span("guardrails_check") as guard_span:
            guard_start = time.time()
            # Simulate guardrails check
            guard_span.set_attribute("guardrails.passed", True)
            guard_span.set_attribute("guardrails.rules_checked", 5)
            guard_span.set_attribute("guardrails.duration_ms", (time.time() - guard_start) * 1000)

        # Model routing span
        with self.tracer.start_as_current_span("model_routing") as route_span:
            route_start = time.time()
            # Simulate model selection
            route_span.set_attribute("routing.selected_model", "gpt-3.5-turbo")
            route_span.set_attribute("routing.strategy", "cost_optimized")
            route_span.set_attribute("routing.duration_ms", (time.time() - route_start) * 1000)

        # Process the actual request
        response = await call_next(request)

        return response

    @contextmanager
    def trace_cache_operation(self, operation: str, cache_key: str):
        """Context manager for tracing cache operations"""
        if not self.tracer:
            yield
            return

        with self.tracer.start_as_current_span(f"cache_{operation}") as span:
            span.set_attribute("cache.operation", operation)
            span.set_attribute("cache.key", cache_key[:50])  # Truncate for safety
            start_time = time.time()

            try:
                yield span
                span.set_attribute("cache.hit", operation == "get")
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                span.set_attribute("cache.duration_ms", (time.time() - start_time) * 1000)

    @contextmanager
    def trace_llm_call(self, provider: str, model: str, **kwargs):
        """Context manager for tracing LLM API calls"""
        if not self.tracer:
            yield
            return

        with self.tracer.start_as_current_span(f"llm_call_{provider}") as span:
            span.set_attribute("llm.provider", provider)
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.temperature", kwargs.get("temperature", 0.7))
            span.set_attribute("llm.max_tokens", kwargs.get("max_tokens", 0))

            start_time = time.time()

            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("llm.duration_ms", duration_ms)

                # Add token metrics if available
                if "input_tokens" in kwargs:
                    span.set_attribute("llm.input_tokens", kwargs["input_tokens"])
                if "output_tokens" in kwargs:
                    span.set_attribute("llm.output_tokens", kwargs["output_tokens"])
                if "total_cost" in kwargs:
                    span.set_attribute("llm.cost_usd", kwargs["total_cost"])

    @contextmanager
    def trace_embedding_generation(self, text_length: int, model: str = "text-embedding-ada-002"):
        """Context manager for tracing embedding generation"""
        if not self.tracer:
            yield
            return

        with self.tracer.start_as_current_span("embedding_generation") as span:
            span.set_attribute("embedding.model", model)
            span.set_attribute("embedding.text_length", text_length)

            start_time = time.time()

            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                span.set_attribute("embedding.duration_ms", (time.time() - start_time) * 1000)

    def trace_streaming_response(self, span_name: str = "streaming_response"):
        """Decorator for tracing streaming responses"""

        def decorator(func):
            async def wrapper(*args, **kwargs):
                if not self.tracer:
                    async for chunk in func(*args, **kwargs):
                        yield chunk
                    return

                with self.tracer.start_as_current_span(span_name) as span:
                    span.set_attribute("streaming.enabled", True)
                    chunk_count = 0
                    total_size = 0
                    start_time = time.time()

                    try:
                        async for chunk in func(*args, **kwargs):
                            chunk_count += 1
                            if isinstance(chunk, str | bytes):
                                total_size += len(chunk)
                            yield chunk

                        span.set_attribute("streaming.chunks", chunk_count)
                        span.set_attribute("streaming.total_size", total_size)
                        span.set_attribute(
                            "streaming.duration_ms", (time.time() - start_time) * 1000
                        )
                        span.set_status(Status(StatusCode.OK))

                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR))
                        raise

            return wrapper

        return decorator


def get_current_span() -> trace.Span | None:
    """Get the current active span"""
    return trace.get_current_span()


def add_span_event(name: str, attributes: dict[str, Any] = None):
    """Add an event to the current span"""
    span = get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})


def set_span_attribute(key: str, value: Any):
    """Set an attribute on the current span"""
    span = get_current_span()
    if span and span.is_recording():
        span.set_attribute(key, value)


# Global tracing instance
tracing_middleware = None


def initialize_tracing(
    service_name: str = "ai-chatbot-system",
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
    enabled: bool = True,
) -> TracingMiddleware:
    """Initialize global tracing middleware"""
    global tracing_middleware
    tracing_middleware = TracingMiddleware(
        service_name=service_name, jaeger_host=jaeger_host, jaeger_port=jaeger_port, enabled=enabled
    )
    return tracing_middleware
