"""
Cache middleware for FastAPI to check cache before processing requests.
"""

import json
import logging
import time
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..cache.cache_key_generator import CacheKeyGenerator
from ..cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class CacheMiddleware(BaseHTTPMiddleware):
    """Middleware to handle caching for chat requests."""
    
    def __init__(
        self,
        app,
        redis_cache: RedisCache,
        key_generator: CacheKeyGenerator,
        cache_endpoints: Optional[list] = None
    ):
        """
        Initialize cache middleware.
        
        Args:
            app: FastAPI application
            redis_cache: Redis cache instance
            key_generator: Cache key generator
            cache_endpoints: List of endpoints to cache (default: ["/chat/completions"])
        """
        super().__init__(app)
        self.redis_cache = redis_cache
        self.key_generator = key_generator
        self.cache_endpoints = cache_endpoints or ["/chat/completions"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through cache middleware.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
        
        Returns:
            Response with cache headers
        """
        # Check if this endpoint should be cached
        if not self._should_cache(request):
            return await call_next(request)
        
        # Check cache control headers
        if self._should_bypass_cache(request):
            logger.info("Cache bypass requested via headers")
            response = await call_next(request)
            response.headers["X-Cache"] = "BYPASS"
            return response
        
        # Try to get from cache
        cache_result = await self._check_cache(request)
        
        if cache_result:
            # Cache hit
            logger.info("Cache hit, returning cached response")
            return await self._create_cached_response(cache_result, request)
        
        # Cache miss - process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add cache headers
        response.headers["X-Cache"] = "MISS"
        response.headers["X-Cache-Process-Time"] = f"{process_time:.3f}"
        
        # Cache successful responses
        if response.status_code == 200:
            await self._cache_response(request, response)
        
        return response
    
    def _should_cache(self, request: Request) -> bool:
        """
        Check if request should be cached.
        
        Args:
            request: Incoming request
        
        Returns:
            True if request should be cached
        """
        # Only cache specific endpoints
        path = request.url.path
        
        for endpoint in self.cache_endpoints:
            if endpoint in path:
                # Only cache POST requests for chat endpoints
                if request.method == "POST":
                    return True
        
        return False
    
    def _should_bypass_cache(self, request: Request) -> bool:
        """
        Check if cache should be bypassed.
        
        Args:
            request: Incoming request
        
        Returns:
            True if cache should be bypassed
        """
        # Check Cache-Control header
        cache_control = request.headers.get("Cache-Control", "")
        
        if "no-cache" in cache_control or "no-store" in cache_control:
            return True
        
        # Check custom bypass header
        if request.headers.get("X-Cache-Bypass") == "true":
            return True
        
        return False
    
    async def _check_cache(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Check cache for request.
        
        Args:
            request: Incoming request
        
        Returns:
            Cached response data or None
        """
        try:
            # Read request body
            body = await request.body()
            request_data = json.loads(body) if body else {}
            
            # Store body for later use
            request._body = body
            
            # Generate cache key
            messages = request_data.get("messages", [])
            model = request_data.get("model", "unknown")
            temperature = request_data.get("temperature", 0.7)
            
            # Get user ID from headers or auth
            user_id = request.headers.get("X-User-ID")
            
            # Generate cache key
            cache_key = self.key_generator.generate_key(
                messages=messages,
                model=model,
                temperature=temperature,
                user_id=user_id
            )
            
            # Check cache
            cached = await self.redis_cache.get_cached_response(
                key=cache_key,
                check_semantic=True,
                semantic_threshold=0.95
            )
            
            if cached:
                # Add metadata
                cached["_cache_key"] = cache_key
                cached["_cache_hit"] = True
                return cached
            
            # Store key in request state for later caching
            request.state.cache_key = cache_key
            request.state.cache_data = {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "user_id": user_id
            }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking cache: {e}")
            return None
    
    async def _create_cached_response(
        self,
        cached_data: Dict[str, Any],
        request: Request
    ) -> JSONResponse:
        """
        Create response from cached data.
        
        Args:
            cached_data: Cached response data
            request: Original request
        
        Returns:
            JSON response with cache headers
        """
        # Remove internal cache metadata
        cache_key = cached_data.pop("_cache_key", "unknown")
        cached_data.pop("_cache_hit", None)
        
        # Add cache status to response if it's not already there
        if "cached" not in cached_data:
            cached_data["cached"] = True
        
        # Create response
        response = JSONResponse(
            content=cached_data,
            status_code=200,
            headers={
                "X-Cache": "HIT",
                "X-Cache-Key": cache_key[:32],  # Truncated for security
                "Cache-Control": "private, max-age=3600",
                "Vary": "X-User-ID"
            }
        )
        
        return response
    
    async def _cache_response(self, request: Request, response: Response):
        """
        Cache successful response.
        
        Args:
            request: Original request
            response: Response to cache
        """
        try:
            # Check if we have cache key from request
            cache_key = getattr(request.state, "cache_key", None)
            cache_data = getattr(request.state, "cache_data", None)
            
            if not cache_key or not cache_data:
                return
            
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Parse response
            response_data = json.loads(body) if body else {}
            
            # Cache the response
            await self.redis_cache.cache_response(
                key=cache_key,
                response=response_data,
                tags=[cache_data.get("model", "unknown")]
            )
            
            # Add to semantic index
            self.key_generator.add_to_similarity_index(
                cache_key,
                cache_data.get("messages", [])
            )
            
            # Recreate response body for client
            response._body = body
            
        except Exception as e:
            logger.error(f"Error caching response: {e}")


class CachePerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to track cache performance metrics."""
    
    def __init__(self, app, redis_cache: RedisCache):
        """
        Initialize performance middleware.
        
        Args:
            app: FastAPI application
            redis_cache: Redis cache instance
        """
        super().__init__(app)
        self.redis_cache = redis_cache
        self.request_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Track cache performance.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
        
        Returns:
            Response with performance headers
        """
        # Process request
        response = await call_next(request)
        
        # Track cache performance
        cache_status = response.headers.get("X-Cache", "")
        
        if cache_status == "HIT":
            self.cache_hits += 1
        elif cache_status == "MISS":
            self.cache_misses += 1
        
        if cache_status in ["HIT", "MISS"]:
            self.request_count += 1
        
        # Calculate hit rate
        hit_rate = (self.cache_hits / self.request_count * 100) if self.request_count > 0 else 0
        
        # Add performance headers
        response.headers["X-Cache-Hit-Rate"] = f"{hit_rate:.2f}%"
        response.headers["X-Cache-Stats"] = f"hits={self.cache_hits},misses={self.cache_misses}"
        
        # Log performance periodically
        if self.request_count % 100 == 0:
            logger.info(
                f"Cache performance: {hit_rate:.2f}% hit rate "
                f"({self.cache_hits} hits, {self.cache_misses} misses)"
            )
            
            # Get detailed stats from Redis
            if self.redis_cache._connected:
                stats = await self.redis_cache.get_stats()
                logger.info(f"Redis cache stats: {stats.to_dict()}")
        
        return response