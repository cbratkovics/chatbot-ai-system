"""API routes for chatbot system."""

import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer

from chatbot_ai_system.middleware.rate_limit import RateLimiter
from chatbot_ai_system.providers import ProviderRouter
from chatbot_ai_system.schemas import ChatRequest, ChatResponse, StreamResponse

api_router = APIRouter()
security = HTTPBearer()
rate_limiter = RateLimiter()


@api_router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    req: Request,
):
    """Handle chat completion requests with multi-provider support."""

    # Apply rate limiting
    await rate_limiter.check(req)

    # Get provider router
    router = ProviderRouter()

    # Generate request ID
    request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

    if request.stream:
        # Return streaming response
        return StreamingResponse(
            stream_response(request, router, request_id),
            media_type="text/event-stream",
        )
    else:
        # Check cache first
        from chatbot_ai_system.cache import cache

        cached_response = await cache.get_cached_chat_response(
            request.messages,
            request.provider,
            request.model,
        )

        if cached_response:
            # Return cached response
            return ChatResponse(
                id=request_id,
                created=int(time.time()),
                model=request.model,
                provider=request.provider,
                choices=[
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": cached_response,
                        },
                        "finish_reason": "stop",
                    }
                ],
                usage={
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cached": True,
                },
            )

        # Get new response
        response = await router.route(request)

        # Cache the response
        await cache.cache_chat_response(
            request.messages,
            request.provider,
            request.model,
            response["content"],
        )

        return ChatResponse(
            id=request_id,
            created=int(time.time()),
            model=request.model,
            provider=request.provider,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response["content"],
                    },
                    "finish_reason": "stop",
                }
            ],
            usage=response.get("usage"),
        )


async def stream_response(
    request: ChatRequest,
    router: ProviderRouter,
    request_id: str,
) -> AsyncIterator[str]:
    """Stream response from provider."""
    async for chunk in router.stream(request):
        response = StreamResponse(
            id=request_id,
            created=int(time.time()),
            model=request.model,
            provider=request.provider,
            choices=[
                {
                    "index": 0,
                    "delta": {"content": chunk},
                    "finish_reason": None,
                }
            ],
        )
        yield f"data: {response.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"


@api_router.get("/models")
async def list_models():
    """List available models from all providers."""
    router = ProviderRouter()
    models = []

    for provider_name, _provider in router.providers.items():
        if provider_name == "mock":
            models.append(
                {
                    "id": "mock-model",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "mock",
                }
            )
        elif provider_name == "openai":
            models.extend(
                [
                    {"id": "gpt-4", "object": "model", "owned_by": "openai"},
                    {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"},
                ]
            )
        elif provider_name == "anthropic":
            models.extend(
                [
                    {"id": "claude-3-opus", "object": "model", "owned_by": "anthropic"},
                    {"id": "claude-3-sonnet", "object": "model", "owned_by": "anthropic"},
                ]
            )

    return {"data": models, "object": "list"}


@api_router.get("/providers")
async def list_providers():
    """List available providers and their status."""
    router = ProviderRouter()
    providers_status = {}

    for name, provider in router.providers.items():
        providers_status[name] = {
            "available": True,
            "healthy": await provider.health_check(),
        }

    return providers_status


@api_router.get("/status")
async def status():
    """API status endpoint with connectivity checks."""
    from chatbot_ai_system.cache import cache

    status = {
        "status": "operational",
        "services": {
            "api": "healthy",
            "cache": "unknown",
            "database": "unknown",
        },
    }

    # Check cache
    try:
        test_key = "health:check"
        await cache.set(test_key, "ok", ttl=10)
        if await cache.get(test_key) == "ok":
            status["services"]["cache"] = "healthy"
        else:
            status["services"]["cache"] = "unhealthy"
    except Exception:
        status["services"]["cache"] = "disconnected"

    # Check database
    try:
        from sqlalchemy import text

        from chatbot_ai_system.database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            status["services"]["database"] = "healthy"
    except Exception:
        status["services"]["database"] = "disconnected"

    # Overall status
    if all(s in ["healthy", "unknown"] for s in status["services"].values()):
        status["status"] = "operational"
    elif any(s == "healthy" for s in status["services"].values()):
        status["status"] = "degraded"
    else:
        status["status"] = "unhealthy"

    return status
