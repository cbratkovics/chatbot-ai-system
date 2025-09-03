"""
Prometheus metrics collection for monitoring system performance and usage.
"""

from typing import Optional, Callable
from functools import wraps
import time
import asyncio
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY
)
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
import logging

logger = logging.getLogger(__name__)

# Request metrics
REQUEST_COUNT = Counter(
    'chatbot_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'chatbot_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

RESPONSE_SIZE = Summary(
    'chatbot_response_size_bytes',
    'Response size in bytes',
    ['method', 'endpoint']
)

# WebSocket metrics
WEBSOCKET_CONNECTIONS = Gauge(
    'chatbot_websocket_connections',
    'Number of active WebSocket connections'
)

WEBSOCKET_MESSAGES = Counter(
    'chatbot_websocket_messages_total',
    'Total number of WebSocket messages',
    ['direction', 'type']  # direction: sent/received, type: message type
)

# Cache metrics
CACHE_HITS = Counter(
    'chatbot_cache_hits_total',
    'Total number of cache hits'
)

CACHE_MISSES = Counter(
    'chatbot_cache_misses_total',
    'Total number of cache misses'
)

CACHE_SIZE = Gauge(
    'chatbot_cache_size_bytes',
    'Current cache size in bytes'
)

CACHE_EVICTIONS = Counter(
    'chatbot_cache_evictions_total',
    'Total number of cache evictions'
)

# Provider metrics
PROVIDER_REQUESTS = Counter(
    'chatbot_provider_requests_total',
    'Total number of provider requests',
    ['provider', 'model', 'status']
)

PROVIDER_DURATION = Histogram(
    'chatbot_provider_duration_seconds',
    'Provider request duration in seconds',
    ['provider', 'model'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0)
)

PROVIDER_TOKENS = Counter(
    'chatbot_provider_tokens_total',
    'Total number of tokens processed',
    ['provider', 'model', 'type']  # type: prompt/completion
)

PROVIDER_COST = Counter(
    'chatbot_provider_cost_dollars',
    'Estimated cost in dollars',
    ['provider', 'model']
)

# System metrics
ACTIVE_REQUESTS = Gauge(
    'chatbot_active_requests',
    'Number of active requests'
)

ERROR_RATE = Counter(
    'chatbot_errors_total',
    'Total number of errors',
    ['type', 'endpoint']
)

# Application info
APP_INFO = Info(
    'chatbot_app',
    'Application information'
)

# Rate limiting metrics
RATE_LIMIT_EXCEEDED = Counter(
    'chatbot_rate_limit_exceeded_total',
    'Number of rate limit exceeded events',
    ['endpoint']
)

# Database metrics (for future use)
DB_CONNECTIONS = Gauge(
    'chatbot_db_connections',
    'Number of active database connections'
)

DB_QUERY_DURATION = Histogram(
    'chatbot_db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)


class MetricsMiddleware:
    """Middleware for collecting request metrics."""
    
    def __init__(self):
        self.excluded_paths = {'/metrics', '/health', '/favicon.ico'}
    
    async def __call__(self, request: Request, call_next):
        # Skip metrics for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Track active requests
        ACTIVE_REQUESTS.inc()
        
        # Start timing
        start_time = time.time()
        
        # Extract endpoint (remove path parameters)
        endpoint = request.url.path
        for route in request.app.routes:
            if hasattr(route, 'path_regex') and route.path_regex.match(request.url.path):
                endpoint = route.path
                break
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)
            
            # Estimate response size
            content_length = response.headers.get('content-length', 0)
            if content_length:
                RESPONSE_SIZE.labels(
                    method=request.method,
                    endpoint=endpoint
                ).observe(int(content_length))
            
            # Track errors
            if response.status_code >= 400:
                ERROR_RATE.labels(
                    type='http_error',
                    endpoint=endpoint
                ).inc()
            
            # Track rate limiting
            if response.status_code == 429:
                RATE_LIMIT_EXCEEDED.labels(endpoint=endpoint).inc()
            
            return response
            
        except Exception:
            # Track exceptions
            ERROR_RATE.labels(
                type='exception',
                endpoint=endpoint
            ).inc()
            raise
        
        finally:
            ACTIVE_REQUESTS.dec()


class MetricsCollector:
    """Collector for application-specific metrics."""
    
    @staticmethod
    def record_cache_hit():
        """Record a cache hit."""
        CACHE_HITS.inc()
    
    @staticmethod
    def record_cache_miss():
        """Record a cache miss."""
        CACHE_MISSES.inc()
    
    @staticmethod
    def update_cache_size(size_bytes: int):
        """Update current cache size."""
        CACHE_SIZE.set(size_bytes)
    
    @staticmethod
    def record_cache_eviction():
        """Record a cache eviction."""
        CACHE_EVICTIONS.inc()
    
    @staticmethod
    def record_websocket_connection(delta: int):
        """Update WebSocket connection count."""
        if delta > 0:
            WEBSOCKET_CONNECTIONS.inc(delta)
        else:
            WEBSOCKET_CONNECTIONS.dec(abs(delta))
    
    @staticmethod
    def record_websocket_message(direction: str, msg_type: str):
        """Record a WebSocket message."""
        WEBSOCKET_MESSAGES.labels(direction=direction, type=msg_type).inc()
    
    @staticmethod
    def record_provider_request(
        provider: str,
        model: str,
        duration: float,
        success: bool,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        estimated_cost: Optional[float] = None
    ):
        """Record provider API request metrics."""
        status = 'success' if success else 'error'
        
        PROVIDER_REQUESTS.labels(
            provider=provider,
            model=model,
            status=status
        ).inc()
        
        PROVIDER_DURATION.labels(
            provider=provider,
            model=model
        ).observe(duration)
        
        if prompt_tokens:
            PROVIDER_TOKENS.labels(
                provider=provider,
                model=model,
                type='prompt'
            ).inc(prompt_tokens)
        
        if completion_tokens:
            PROVIDER_TOKENS.labels(
                provider=provider,
                model=model,
                type='completion'
            ).inc(completion_tokens)
        
        if estimated_cost:
            PROVIDER_COST.labels(
                provider=provider,
                model=model
            ).inc(estimated_cost)
    
    @staticmethod
    def update_db_connections(count: int):
        """Update database connection count."""
        DB_CONNECTIONS.set(count)
    
    @staticmethod
    def record_db_query(operation: str, duration: float):
        """Record database query metrics."""
        DB_QUERY_DURATION.labels(operation=operation).observe(duration)


def track_time(metric: Histogram = None):
    """Decorator to track function execution time."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if metric:
                    metric.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if metric:
                    metric.observe(duration)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost based on provider and model pricing."""
    # Pricing per 1K tokens (approximate as of 2024)
    pricing = {
        'openai': {
            'gpt-4': {'prompt': 0.03, 'completion': 0.06},
            'gpt-4-32k': {'prompt': 0.06, 'completion': 0.12},
            'gpt-3.5-turbo': {'prompt': 0.0015, 'completion': 0.002},
            'gpt-3.5-turbo-16k': {'prompt': 0.003, 'completion': 0.004}
        },
        'anthropic': {
            'claude-3-opus': {'prompt': 0.015, 'completion': 0.075},
            'claude-3-sonnet': {'prompt': 0.003, 'completion': 0.015},
            'claude-3-haiku': {'prompt': 0.00025, 'completion': 0.00125},
            'claude-2.1': {'prompt': 0.008, 'completion': 0.024},
            'claude-instant-1.2': {'prompt': 0.00163, 'completion': 0.00551}
        }
    }
    
    # Get pricing for provider and model
    provider_pricing = pricing.get(provider, {})
    model_pricing = None
    
    # Find matching model pricing
    for model_key, prices in provider_pricing.items():
        if model_key in model.lower():
            model_pricing = prices
            break
    
    if not model_pricing:
        # Default conservative estimate
        model_pricing = {'prompt': 0.01, 'completion': 0.03}
    
    # Calculate cost
    prompt_cost = (prompt_tokens / 1000) * model_pricing['prompt']
    completion_cost = (completion_tokens / 1000) * model_pricing['completion']
    total_cost = prompt_cost + completion_cost
    
    return total_cost


async def get_metrics(request: Request) -> Response:
    """Endpoint to expose metrics for Prometheus scraping."""
    # Update application info
    APP_INFO.info({
        'version': '1.0.0',
        'environment': request.app.state.settings.environment,
        'python_version': '3.11'
    })
    
    # Generate metrics in Prometheus format
    metrics_output = generate_latest(REGISTRY)
    
    return PlainTextResponse(
        content=metrics_output.decode('utf-8'),
        media_type=CONTENT_TYPE_LATEST
    )


# Create global metrics collector instance
metrics_collector = MetricsCollector()