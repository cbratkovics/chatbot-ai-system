"""API v1 routes."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...providers.orchestrator import ProviderOrchestrator
from ...schemas.chat import ChatRequest

logger = structlog.get_logger()
router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""

    messages: list[ChatMessage] = Field(..., description="List of messages")
    model: str | None = Field(None, description="Model to use")
    temperature: float | None = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int | None = Field(None, ge=1, description="Maximum tokens to generate")
    stream: bool | None = Field(False, description="Stream response")
    provider: str | None = Field(None, description="Provider to use")


class ChatCompletionResponse(BaseModel):
    """Chat completion response model."""

    id: str = Field(..., description="Response ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    usage: dict[str, int] = Field(..., description="Token usage")
    choices: list[dict[str, Any]] = Field(..., description="Response choices")


async def get_orchestrator(request: Request) -> ProviderOrchestrator:
    """Get provider orchestrator with tenant context."""
    # TODO: Initialize with tenant-specific configuration and providers
    # For now, return an empty orchestrator - providers should be configured elsewhere
    return ProviderOrchestrator(providers=[])


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    req: Request,
    orchestrator: ProviderOrchestrator = Depends(get_orchestrator),  # noqa: B008
) -> ChatCompletionResponse:
    """Create a chat completion."""
    try:
        logger.info(
            "Processing chat completion",
            tenant_id=getattr(req.state, "tenant_id", None),
            model=request.model,
            provider=request.provider,
            stream=request.stream,
        )

        # Get tenant_id from request state
        tenant_id = getattr(req.state, "tenant_id", None)
        
        # Convert to internal chat request format
        chat_request = ChatRequest(
            messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            stop=None,
            stream=request.stream,
            provider=request.provider,
            tools=None,
            tool_choice=None,
            response_format=None,
            seed=None,
            user=None,
            tenant_id=tenant_id,
            metadata={},
        )

        # Process request through orchestrator
        response = await orchestrator.process_request(chat_request)

        # Format response
        import time
        import uuid
        
        # Convert TokenUsage to dict format
        usage_dict: dict[str, int] = {}
        if response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        # Create choices from response content
        choices = [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response.content,
            },
            "finish_reason": response.finish_reason or "stop",
        }]
        
        return ChatCompletionResponse(
            id=getattr(response, 'id', str(uuid.uuid4())),
            created=getattr(response, 'created', int(time.time())),
            model=response.model,
            usage=usage_dict,
            choices=choices,
        )

    except Exception as e:
        logger.error(
            "Chat completion failed",
            error=str(e),
            tenant_id=getattr(req.state, "tenant_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat completion failed: {str(e)}",
        ) from e


@router.get("/models")
async def list_models(
    req: Request,
    orchestrator: ProviderOrchestrator = Depends(get_orchestrator),  # noqa: B008
) -> dict[str, Any]:
    """List available models."""
    try:
        models = await orchestrator.list_available_models()
        return {
            "object": "list",
            "data": models,
        }
    except Exception as e:
        logger.error(
            "Failed to list models",
            error=str(e),
            tenant_id=getattr(req.state, "tenant_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        ) from e


@router.get("/providers")
async def list_providers(
    req: Request,
    orchestrator: ProviderOrchestrator = Depends(get_orchestrator),  # noqa: B008
) -> dict[str, Any]:
    """List available providers and their status."""
    try:
        providers = await orchestrator.get_provider_status()
        return {
            "providers": providers,
            "timestamp": req.state.request_id,
        }
    except Exception as e:
        logger.error(
            "Failed to list providers",
            error=str(e),
            tenant_id=getattr(req.state, "tenant_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list providers: {str(e)}",
        ) from e
