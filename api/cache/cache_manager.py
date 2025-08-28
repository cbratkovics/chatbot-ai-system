"""Cache manager for coordinating semantic caching with providers."""

import logging
import time
from uuid import UUID

from ..providers import CompletionRequest, CompletionResponse, ProviderOrchestrator
from .semantic_cache import SemanticCache

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching for provider responses."""

    def __init__(
        self,
        semantic_cache: SemanticCache,
        provider_orchestrator: ProviderOrchestrator,
        cache_enabled: bool = True,
    ):
        self.semantic_cache = semantic_cache
        self.provider_orchestrator = provider_orchestrator
        self.cache_enabled = cache_enabled

        logger.info(f"Cache manager initialized (enabled: {cache_enabled})")

    async def complete_with_cache(self, request: CompletionRequest) -> CompletionResponse:
        """Complete request with caching support."""
        start_time = time.time()

        # Extract query from messages
        query = self._extract_query(request)

        # Check cache if enabled
        cached_response = None
        if self.cache_enabled and not request.stream:
            cached_response = await self.semantic_cache.get(
                query=query,
                model=request.model,
                temperature=request.temperature,
                tenant_id=str(request.tenant_id) if request.tenant_id else None,
            )

        if cached_response:
            # Return cached response
            logger.debug(f"Cache hit for query: {query[:50]}...")

            # Create response from cache
            response = CompletionResponse(
                id=UUID(cached_response.id),
                content=cached_response.response,
                model=cached_response.model,
                usage=None,  # Would need to store usage in cache
                provider="cache",
                latency_ms=(time.time() - start_time) * 1000,
                cached=True,
                metadata={
                    "cache_hit": True,
                    "cache_entry_id": cached_response.id,
                    "similarity_score": cached_response.embedding.vector[0]
                    if cached_response.embedding
                    else 0,
                },
            )

            return response

        # Get response from provider
        logger.debug(f"Cache miss for query: {query[:50]}...")
        response = await self.provider_orchestrator.complete(request)

        # Cache the response if enabled
        if self.cache_enabled and not request.stream:
            try:
                await self.semantic_cache.put(
                    query=query,
                    response=response.content,
                    model=request.model,
                    temperature=request.temperature,
                    tenant_id=str(request.tenant_id) if request.tenant_id else None,
                )
            except Exception as e:
                logger.error(f"Failed to cache response: {e}")

        return response

    def _extract_query(self, request: CompletionRequest) -> str:
        """Extract query string from request messages."""
        # Get the last user message as the query
        for message in reversed(request.messages):
            if message.role == "user":
                return message.content

        # Fallback to concatenating all messages
        return " ".join([msg.content for msg in request.messages])

    async def invalidate_cache(self, tenant_id: UUID | None = None):
        """Invalidate cache entries."""
        await self.semantic_cache.clear(tenant_id=str(tenant_id) if tenant_id else None)
        logger.info(f"Cache invalidated for tenant: {tenant_id or 'all'}")

    async def get_cache_stats(self):
        """Get cache statistics."""
        stats = await self.semantic_cache.get_stats()

        return {
            "enabled": self.cache_enabled,
            "statistics": stats.to_dict(),
            "similarity_threshold": self.semantic_cache.similarity_threshold,
            "max_entries": self.semantic_cache.max_entries,
            "default_ttl": self.semantic_cache.default_ttl,
        }

    async def warmup_cache(self):
        """Warmup cache with common queries."""
        common_queries = [
            "Hello, how are you?",
            "What's the weather like?",
            "Tell me a joke",
            "What can you help me with?",
            "How do I get started?",
            "What are your capabilities?",
            "Can you explain how this works?",
            "What's new today?",
            "Help me with a problem",
            "Thank you for your help",
        ]

        common_responses = [
            "Hello! I'm doing well, thank you for asking. How can I assist you today?",
            "I don't have access to real-time weather data, but I'd be happy to help you with other questions!",
            "Why don't scientists trust atoms? Because they make up everything!",
            "I can help you with a wide variety of tasks including answering questions, providing explanations, helping with analysis, and much more!",
            "To get started, simply ask me any question or describe what you'd like help with. I'm here to assist!",
            "I can help with answering questions, providing information, assisting with analysis, creative tasks, problem-solving, and much more!",
            "I'd be happy to explain! Could you please specify what particular aspect you'd like me to explain?",
            "I'm ready to help you with whatever you need today! What would you like to know or discuss?",
            "I'd be glad to help you solve a problem. Please describe the issue you're facing, and I'll do my best to assist!",
            "You're very welcome! I'm always here if you need any more assistance. Have a great day!",
        ]

        await self.semantic_cache.warmup(
            queries=common_queries, responses=common_responses, model="model-3.5-turbo"
        )

        logger.info("Cache warmed up with common queries")
