"""Cache manager for coordinating semantic caching with providers."""

import logging
import time
from uuid import UUID

from chatbot_ai_system.cache.semantic_cache import SemanticCache
from chatbot_ai_system.providers.orchestrator import ProviderOrchestrator
from chatbot_ai_system.providers.base import CompletionRequest, CompletionResponse

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

    async def complete_with_cache(
        self, request: CompletionRequest
    ) -> CompletionResponse:
        """Complete request with caching support."""
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
                content=cached_response.response,
                model=cached_response.model,
                usage=None,  # Would need to store usage in cache
                cached=True,
                similarity_score=(
                    cached_response.embedding.vector[0]
                    if cached_response.embedding
                    else None
                ),
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
            "What can you help me with?",
            "How do I get started?",
            "What are your capabilities?",
            "Can you explain how this works?",
            "Help me understand this better",
            "What's the best way to approach this?",
            "Can you provide an example?",
            "How does this feature work?",
            "What are the main benefits?",
            "Can you summarize this for me?",
            "What should I know about this?",
            "How can I improve this?",
            "What are the key considerations?",
            "Thank you for your help",
        ]

        common_responses = [
            "Hello! I'm doing well, thank you for asking. How can I assist you today?",
            "I can help you with a wide variety of tasks including answering questions, providing explanations, helping with analysis, coding assistance, and much more!",
            "To get started, simply ask me any question or describe what you'd like help with. I'm here to assist!",
            "I can help with answering questions, providing information, assisting with analysis, creative tasks, problem-solving, coding, and much more!",
            "I'd be happy to explain! Could you please specify what particular aspect you'd like me to explain?",
            "I'll help you understand this better. Let me break it down into clear, manageable parts for you.",
            "The best approach depends on your specific context. Let me help you evaluate the options and find the most suitable solution.",
            "Certainly! Let me provide you with a clear, practical example to illustrate this concept.",
            "This feature is designed to streamline your workflow. Let me explain how it works and its key components.",
            "The main benefits include improved efficiency, better organization, enhanced reliability, and scalability for future growth.",
            "I'll provide you with a concise summary of the key points to help you understand the essential information.",
            "Here are the important things you should know about this topic, organized for clarity and quick reference.",
            "I can suggest several ways to improve this. Let me analyze the current state and provide actionable recommendations.",
            "The key considerations include performance requirements, scalability needs, security implications, and maintenance complexity.",
            "You're very welcome! I'm always here if you need any more assistance. Have a great day!",
        ]

        await self.semantic_cache.warmup(
            queries=common_queries, responses=common_responses, model="gpt-3.5-turbo"
        )

        logger.info("Cache warmed up with common queries")
