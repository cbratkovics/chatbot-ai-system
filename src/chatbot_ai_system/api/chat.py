"""Chat API: provider failover chain, optional cache, demo guardrails, SSE streaming.

Request path: guardrails -> cache lookup -> provider chain -> cache store -> response.
Every step is reported in ``telemetry`` (provider, model, cache HIT/MISS, latency, tokens,
estimated cost, per-provider attempts) so the UI can show what actually happened.

Cache lookup is exact-key first. With ``SEMANTIC_CACHE_ENABLED`` an exact miss is followed by
an embedding comparison against prompts this worker has answered (ADR 0007); a semantic HIT
reports its real similarity, the embedding it paid for, and the provider cost it avoided.

Streaming uses Server-Sent Events over the same POST endpoint (``"stream": true``):

    event: meta   -> {request_id, model, provider, cache}
    event: delta  -> {content}
    event: done   -> telemetry
    event: error  -> {error: {...}}

SSE was chosen over the WebSocket path for the demo because it is a plain HTTP response:
it survives Render's free-tier proxy without long-lived-connection issues, needs no
reconnection protocol, and is trivially curl-able.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..cache.cache_key_generator import CacheKeyGenerator
from ..cache.memory_cache import MemoryCache
from ..cache.redis_cache import RedisCache
from ..cache.semantic_match import (
    Embedder,
    OpenAIEmbedder,
    SemanticIndex,
    namespace_for,
    normalise,
    split_context,
)
from ..config import Settings, get_settings
from ..providers.anthropic_provider import AnthropicProvider
from ..providers.base import (
    AuthenticationError,
    BaseProvider,
    ChatMessage,
    ModelNotFoundError,
    ProviderError,
    StreamChunk,
)
from ..providers.catalog import (
    MODEL_CATALOG,
    PROVIDERS,
    estimate_cost_usd,
    estimate_embedding_cost_usd,
    models_for,
    provider_for,
    resolve_model,
)
from ..providers.chain import (
    SIMULATED_OUTAGE,
    Attempt,
    ChainExhaustedError,
    ProviderChain,
    StreamStart,
)
from ..providers.groq_provider import GroqProvider
from ..providers.openai_provider import OpenAIProvider
from .errors import classify_provider_error, error_payload, error_response, provider_error_response
from .guardrails import DemoGuard, GuardrailConfig, GuardrailError, client_ip_from_headers
from .metrics import record_cache_outcome

logger = logging.getLogger(__name__)

CacheBackend = Union[RedisCache, MemoryCache]

# Process-wide singletons, built lazily so tests and lifespan both work.
cache: Optional[CacheBackend] = None
cache_key_generator: Optional[CacheKeyGenerator] = None
demo_guard: Optional[DemoGuard] = None
semantic_index: Optional[SemanticIndex] = None
embedder: Optional[Embedder] = None

SIMULATE_FAILURE_HEADER = "x-demo-simulate-failure"
TENANT_HEADER = "x-tenant-id"
PUBLIC_TENANT = "public"

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={
        402: {"description": "Provider quota exhausted"},
        404: {"description": "Model not found"},
        429: {"description": "Rate limit or demo budget exceeded"},
        502: {"description": "Upstream provider error"},
    },
)


# --------------------------------------------------------------------------- models
class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""

    messages: List[Dict[str, str]] = Field(..., description="List of messages in the conversation")
    model: str = Field("default", description="Model identifier, or 'default'")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, le=8192, description="Maximum tokens in response")
    system_prompt: Optional[str] = Field(None, description="System prompt for context")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None, description="Previous messages in the conversation"
    )
    stream: bool = Field(False, description="Stream the answer as Server-Sent Events")

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v):
        """Validate and sanitize messages."""
        if not v:
            raise ValueError("Messages cannot be empty")
        for msg in v:
            if not msg.get("role") or not msg.get("content"):
                raise ValueError("Each message must have 'role' and 'content' fields")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "messages": [{"role": "user", "content": "What is the capital of France?"}],
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 150,
                "stream": False,
            }
        }
    )


class ChatCompletionResponse(BaseModel):
    """Chat completion response (OpenAI-shaped plus telemetry)."""

    id: str = Field(..., description="Unique request identifier")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model that produced the answer")
    provider: str = Field(..., description="Provider that produced the answer")
    choices: List[Dict[str, Any]] = Field(..., description="Response choices")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")
    cached: bool = Field(False, description="Whether response was served from cache")
    cache_key: Optional[str] = Field(None, description="Cache key used")
    similarity_score: Optional[float] = Field(None, description="1.0 for an exact-match hit")
    cache: Dict[str, Any] = Field(default_factory=dict, description="Cache status/backend")
    attempts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Per-provider attempt log for this request"
    )
    latency_ms: float = Field(0.0, description="Server-side wall time")
    telemetry: Dict[str, Any] = Field(
        default_factory=dict, description="What answered, from where, at what cost"
    )


# --------------------------------------------------------------------------- wiring
def make_provider(provider_name: str, settings: Settings) -> BaseProvider:
    """Build a provider client or raise AuthenticationError when its key is missing."""
    timeout = settings.request_timeout
    retries = settings.max_retries
    if provider_name == "openai":
        if not settings.openai_api_key:
            raise AuthenticationError(
                "OpenAI API key not configured (OPENAI_API_KEY)", provider="openai", status_code=401
            )
        return OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=timeout,
            max_retries=retries,
        )
    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise AuthenticationError(
                "Anthropic API key not configured (ANTHROPIC_API_KEY)",
                provider="anthropic",
                status_code=401,
            )
        return AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=timeout,
            max_retries=retries,
        )
    if provider_name == "groq":
        if not settings.groq_api_key:
            raise AuthenticationError(
                "Groq API key not configured (GROQ_API_KEY)", provider="groq", status_code=401
            )
        return GroqProvider(
            api_key=settings.groq_api_key.get_secret_value(),
            timeout=timeout,
            max_retries=retries,
            base_url=settings.groq_base_url,
        )
    raise ModelNotFoundError(f"Unknown provider '{provider_name}'", provider=None, status_code=404)


class ProviderFactory:
    """Thin compatibility facade over the catalogue."""

    MODEL_PROVIDER_MAP = MODEL_CATALOG

    @classmethod
    def create_provider(cls, model: str, settings: Settings) -> BaseProvider:
        if model == "default":
            model = settings.default_model
        model = resolve_model(model)
        provider_name = provider_for(model)
        if not provider_name:
            raise ModelNotFoundError(
                f"Model '{model}' is not supported. Supported models: {list(MODEL_CATALOG)}",
                provider=None,
                status_code=404,
            )
        return make_provider(provider_name, settings)

    @classmethod
    def get_supported_models(cls) -> List[str]:
        return list(MODEL_CATALOG)

    @classmethod
    def get_provider_for_model(cls, model: str) -> Optional[str]:
        return provider_for(model)


def build_chain(settings: Settings, simulate_primary_failure: bool = False) -> ProviderChain:
    return ProviderChain(
        make_provider=lambda name: make_provider(name, settings),
        fallbacks=settings.fallback_chain if settings.enable_fallback else [],
        simulate_primary_failure=simulate_primary_failure,
    )


def get_guard(settings: Settings) -> DemoGuard:
    global demo_guard
    if demo_guard is None:
        demo_guard = DemoGuard(
            GuardrailConfig(
                enabled=settings.demo_guardrails_enabled,
                per_minute=settings.demo_rate_limit_per_minute,
                per_day=settings.demo_rate_limit_per_day,
                max_tokens=settings.demo_max_tokens,
                max_history_messages=settings.demo_max_history_messages,
                daily_token_budget=settings.demo_daily_token_budget,
            )
        )
    return demo_guard


async def build_cache(settings: Settings) -> Optional[CacheBackend]:
    """Redis when configured and reachable within the connect timeout, else memory."""
    if not settings.cache_enabled:
        return None
    if settings.redis_url:
        redis_cache = RedisCache(
            redis_url=settings.redis_url,
            max_connections=settings.redis_max_connections,
            ttl_seconds=settings.cache_ttl_seconds,
            compression_threshold=settings.cache_compression_threshold,
            enable_compression=settings.cache_compression_enabled,
            enable_circuit_breaker=settings.cache_circuit_breaker_enabled,
            connect_timeout_seconds=settings.cache_connect_timeout_seconds,
        )
        try:
            await redis_cache.connect()
            return redis_cache
        except Exception as exc:  # noqa: BLE001 - any connect failure means "use memory"
            logger.warning(
                "Redis unavailable (%s); falling back to in-process memory cache", exc
            )
    else:
        logger.warning("REDIS_URL not set; using in-process memory cache")
    return MemoryCache(
        ttl_seconds=settings.cache_ttl_seconds, max_entries=settings.memory_cache_max_entries
    )


async def get_cache(settings: Settings) -> Optional[CacheBackend]:
    """Return the process cache, building it on first use."""
    global cache, cache_key_generator
    if cache is None and settings.cache_enabled:
        cache = await build_cache(settings)
    if cache_key_generator is None:
        # Exact keys only. Paraphrase matching is the embedding index below (ADR 0007), not the
        # TF-IDF path in CacheKeyGenerator, which would put scikit-learn on the boot path.
        cache_key_generator = CacheKeyGenerator(semantic_cache_enabled=False)
    return cache


def get_semantic(settings: Settings) -> Tuple[Optional[SemanticIndex], Optional[Embedder]]:
    """Semantic index and embedder when the flag is on and an OpenAI key exists, else (None, None)."""
    global semantic_index, embedder
    if not settings.semantic_cache_enabled or not settings.cache_enabled:
        return None, None
    if semantic_index is None:
        semantic_index = SemanticIndex(max_entries=settings.semantic_cache_max_entries)
    if embedder is None and settings.openai_api_key:
        embedder = OpenAIEmbedder(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.semantic_cache_embedding_model,
            timeout_seconds=settings.semantic_cache_embedding_timeout_seconds,
        )
    return semantic_index, embedder


def semantic_status(settings: Settings) -> Dict[str, Any]:
    """What /chat/health reports about paraphrase matching."""
    index, emb = get_semantic(settings)
    return {
        "enabled": settings.semantic_cache_enabled,
        "backend": "openai-embeddings" if emb is not None else None,
        "embedding_model": getattr(emb, "model", None),
        "threshold": settings.semantic_cache_threshold if settings.semantic_cache_enabled else None,
        "index_entries": len(index) if index is not None else 0,
        "max_entries": index.max_entries if index is not None else settings.semantic_cache_max_entries,
    }


async def initialize_cache(settings: Settings) -> Optional[CacheBackend]:
    """Startup hook: build the cache and report which backend won."""
    return await get_cache(settings)


def cache_backend_name() -> str:
    return getattr(cache, "backend", "disabled") if cache else "disabled"


# --------------------------------------------------------------------------- token estimate
_encoder: Any = None
_encoder_failed = False


def estimate_tokens(text: str) -> int:
    """Token count via tiktoken (cl100k) when available, else a 4-chars-per-token estimate.

    Providers that do not report usage on streams (Groq) get this estimate; the telemetry
    marks it ``source: "estimated"`` so nobody mistakes it for a bill.
    """
    global _encoder, _encoder_failed
    if not text:
        return 0
    if _encoder is None and not _encoder_failed:
        try:
            import tiktoken

            _encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:  # noqa: BLE001 - offline or missing cache: fall back
            _encoder_failed = True
    if _encoder is not None:
        try:
            return len(_encoder.encode(text))
        except Exception:  # noqa: BLE001
            pass
    return max(1, len(text) // 4)


def estimate_usage(messages: List[ChatMessage], output: str) -> Dict[str, int]:
    prompt = estimate_tokens("\n".join(f"{m.role}: {m.content}" for m in messages))
    completion = estimate_tokens(output)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}


# --------------------------------------------------------------------------- request context
@dataclass
class PreparedRequest:
    request_id: str
    started: float
    guard: DemoGuard
    model_name: str
    messages: List[ChatMessage]
    temperature: float
    max_tokens: int
    backend: Optional[CacheBackend]
    cache_key: str
    bypass_cache: bool
    simulate_failure: bool
    tenant: str = PUBLIC_TENANT
    lookup: Optional["Lookup"] = None


def _simulate_requested(http_request: Request, settings: Settings) -> bool:
    """True when the demo failure toggle is enabled and this request (or the env) asks for it."""
    if not settings.demo_failure_toggle_enabled:
        return False
    if settings.demo_simulate_primary_failure:
        return True
    value = (http_request.headers.get(SIMULATE_FAILURE_HEADER) or "").strip().lower()
    return value in ("1", "true", "yes", "on")


async def _prepare(
    request: ChatCompletionRequest,
    http_request: Request,
    settings: Settings,
    cache_control: Optional[str],
) -> Union[PreparedRequest, JSONResponse]:
    """Guardrails, model resolution, message assembly, cache key. Errors come back as JSON."""
    request_id = getattr(http_request.state, "request_id", None) or str(uuid.uuid4())
    started = time.perf_counter()

    guard = get_guard(settings)
    client_ip = client_ip_from_headers(
        http_request.headers.get("x-forwarded-for"),
        http_request.client.host if http_request.client else None,
    )
    try:
        guard.check(client_ip)
    except GuardrailError as exc:
        return error_response(
            exc.status_code,
            exc.code,
            exc.message,
            request_id=request_id,
            headers={"Retry-After": str(exc.retry_after)},
        )

    requested_model = settings.default_model if request.model in ("", "default") else request.model
    model_name = resolve_model(requested_model)
    if model_name != requested_model:
        logger.warning("Legacy model id %r mapped to %r", requested_model, model_name)
    if provider_for(model_name) is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "model_not_found",
            f"Model '{model_name}' is not supported. Supported models: {list(MODEL_CATALOG)}",
            request_id=request_id,
        )

    messages: List[ChatMessage] = []
    if request.system_prompt:
        messages.append(ChatMessage(role="system", content=request.system_prompt))
    for msg in request.conversation_history or []:
        messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
    for msg in request.messages:
        messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
    messages = guard.trim_history(messages)
    max_tokens = guard.clamp_max_tokens(request.max_tokens)
    temperature = request.temperature if request.temperature is not None else 0.7

    backend = await get_cache(settings)
    assert cache_key_generator is not None
    # Cache keys are scoped by tenant when a client identifies one; the public demo has none.
    tenant = (http_request.headers.get(TENANT_HEADER) or "").strip() or PUBLIC_TENANT
    cache_key = cache_key_generator.generate_key(
        [{"role": m.role, "content": m.content} for m in messages],
        model_name,
        temperature,
        user_id=None if tenant == PUBLIC_TENANT else tenant,
    )
    bypass = (cache_control or "").lower() in ("no-cache", "no-store")

    return PreparedRequest(
        request_id=request_id,
        started=started,
        guard=guard,
        model_name=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        backend=backend,
        cache_key=cache_key,
        bypass_cache=bypass,
        simulate_failure=_simulate_requested(http_request, settings),
        tenant=tenant,
    )


# --------------------------------------------------------------------------- cache lookup
@dataclass
class Lookup:
    """Outcome of the exact-then-semantic cache lookup for one request."""

    status: str  # hit | miss | bypass
    hit: Optional[Dict[str, Any]] = None
    match: Optional[str] = None  # exact | semantic (only on a hit)
    # 1.0 on an exact hit; cosine on a semantic hit; nearest candidate's score on a miss
    similarity: Optional[float] = None
    semantic: str = "disabled"  # disabled | not_needed | hit | miss | unavailable
    matched_key: Optional[str] = None
    nearest_key: Optional[str] = None  # closest indexed prompt, hit or miss (evals use it)
    threshold: Optional[float] = None
    namespace: Optional[str] = None
    prompt: Optional[str] = None
    vector: Any = None  # embedding of ``prompt``; reused when the answer is stored
    embedding_model: Optional[str] = None
    embedding_tokens: int = 0
    embedding_ms: Optional[float] = None
    embedding_cost_usd: float = 0.0

    def cache_block(self, backend_name: str) -> Dict[str, Any]:
        block: Dict[str, Any] = {
            "status": self.status,
            "backend": backend_name,
            "match": self.match,
            "similarity": self.similarity,
            "semantic": self.semantic,
            "matched_key": self.matched_key,
            "nearest_key": self.nearest_key,
            "threshold": self.threshold,
        }
        if self.hit and self.hit.get("cached_at"):
            block["age_seconds"] = round(time.time() - float(self.hit["cached_at"]), 1)
        return block


async def _lookup(ctx: PreparedRequest, settings: Settings) -> Lookup:
    """Exact key first (free). On an exact miss, embed the final user turn and search the index."""
    if ctx.backend is None or ctx.bypass_cache:
        return Lookup(status="bypass", semantic="not_needed")

    threshold = settings.semantic_cache_threshold if settings.semantic_cache_enabled else None
    exact = await ctx.backend.get_cached_response(ctx.cache_key)
    if exact:
        return Lookup(
            status="hit",
            hit=exact,
            match="exact",
            similarity=1.0,
            semantic="not_needed" if settings.semantic_cache_enabled else "disabled",
            matched_key=ctx.cache_key,
            threshold=threshold,
        )

    index, emb = get_semantic(settings)
    if index is None:
        return Lookup(status="miss", semantic="disabled")

    context, prompt = split_context(ctx.messages)
    lookup = Lookup(
        status="miss",
        semantic="unavailable",
        threshold=settings.semantic_cache_threshold,
        namespace=namespace_for(ctx.tenant, ctx.model_name, ctx.temperature, context),
        prompt=normalise(prompt or ""),
    )
    if emb is None or not lookup.prompt:
        return lookup  # no key configured, or nothing to embed: exact-match behaviour

    try:
        result = await emb.embed(lookup.prompt)
    except Exception as exc:  # noqa: BLE001 - any embedding failure degrades to exact-match
        logger.warning("Semantic cache unavailable (%s); exact-match only", exc)
        return lookup

    lookup.vector = result.vector
    lookup.embedding_model = result.model
    lookup.embedding_tokens = result.tokens
    lookup.embedding_ms = result.latency_ms
    lookup.embedding_cost_usd = estimate_embedding_cost_usd(result.model, result.tokens) or 0.0
    lookup.semantic = "miss"

    nearest = index.nearest(lookup.namespace or "", result.vector)
    if nearest is None:
        return lookup
    lookup.similarity = nearest.similarity
    lookup.nearest_key = nearest.cache_key
    if nearest.similarity < settings.semantic_cache_threshold:
        return lookup
    entry = await ctx.backend.get_cached_response(nearest.cache_key)
    if not entry:
        index.remove(nearest.cache_key)  # expired or evicted underneath the index
        return lookup
    lookup.status, lookup.hit, lookup.match = "hit", entry, "semantic"
    lookup.semantic, lookup.matched_key = "hit", nearest.cache_key
    return lookup


def _telemetry(
    ctx: PreparedRequest,
    *,
    provider: str,
    model: str,
    cache_status: str,
    usage: Optional[Dict[str, int]],
    usage_source: str,
    attempts: List[Attempt],
    streamed: bool,
    ttfb_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """The per-message chip. Every field here is something the UI can show honestly."""
    latency_ms = round((time.perf_counter() - ctx.started) * 1000, 1)
    lookup = ctx.lookup or Lookup(status=cache_status, semantic="disabled")
    prompt_tokens = (usage or {}).get("prompt_tokens", 0)
    completion_tokens = (usage or {}).get("completion_tokens", 0)
    list_price = estimate_cost_usd(model, prompt_tokens, completion_tokens)
    # A hit pays only for its embedding lookup (0 on an exact hit); a miss pays provider + embedding.
    provider_cost = 0.0 if cache_status == "hit" else list_price
    cost = None if provider_cost is None else round(provider_cost + lookup.embedding_cost_usd, 10)
    return {
        "request_id": ctx.request_id,
        "provider": provider,
        "model": model,
        "cache": lookup.cache_block(cache_backend_name()),
        "latency_ms": latency_ms,
        "ttfb_ms": ttfb_ms,
        "usage": {**(usage or {}), "source": usage_source if usage else "none"},
        "cost_usd": cost,
        "cost_avoided_usd": (list_price or 0.0) if cache_status == "hit" else 0.0,
        "embedding": {
            "model": lookup.embedding_model,
            "tokens": lookup.embedding_tokens,
            "latency_ms": lookup.embedding_ms,
            "cost_usd": lookup.embedding_cost_usd,
        },
        "attempts": [a.to_dict() for a in attempts],
        "failover": any(a.outcome == "failed" for a in attempts) and attempts[-1].outcome == "ok",
        "simulated_failure": any(a.error_code == SIMULATED_OUTAGE for a in attempts),
        "streamed": streamed,
    }


async def _store(
    ctx: PreparedRequest,
    content: str,
    model: str,
    provider: str,
    usage: Any,
    usage_source: str = "provider",
) -> None:
    """Cache the answer under its exact key and, when embedded, index the prompt for paraphrases."""
    if ctx.backend is None or ctx.bypass_cache or not content:
        return
    await ctx.backend.cache_response(
        ctx.cache_key,
        {
            "content": content,
            "model": model,
            "provider": provider,
            "usage": usage,
            "usage_source": usage_source,
            "cached_at": time.time(),
        },
    )
    lookup = ctx.lookup
    if lookup is not None and lookup.vector is not None and semantic_index is not None:
        semantic_index.add(
            lookup.namespace or "", ctx.cache_key, lookup.prompt or "", lookup.vector
        )


def _json_response(
    ctx: PreparedRequest,
    *,
    content: str,
    model: str,
    provider: str,
    usage: Optional[Dict[str, int]],
    finish_reason: str,
    cached: bool,
    telemetry: Dict[str, Any],
) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id=ctx.request_id,
        created=int(datetime.utcnow().timestamp()),
        model=model,
        provider=provider,
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        usage=usage,
        cached=cached,
        cache_key=ctx.cache_key,
        similarity_score=telemetry["cache"].get("similarity") if cached else None,
        cache=telemetry["cache"] | {"key": ctx.cache_key},
        attempts=telemetry["attempts"],
        latency_ms=telemetry["latency_ms"],
        telemetry=telemetry,
    )


# --------------------------------------------------------------------------- routes
@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    http_request: Request,
    settings: Settings = Depends(get_settings),
    cache_control: Optional[str] = Header(None),
) -> Any:
    """Generate a chat completion (JSON, or SSE when ``stream`` is true)."""
    prepared = await _prepare(request, http_request, settings, cache_control)
    if isinstance(prepared, JSONResponse):
        return prepared
    ctx = prepared

    # Cache lookup (exact key, then semantic when enabled) is shared by both paths.
    ctx.lookup = await _lookup(ctx, settings)
    record_cache_outcome(ctx.lookup.status, ctx.lookup.match or "", ctx.lookup.semantic)
    hit = ctx.lookup.hit

    if request.stream:
        # Content-Encoding: identity opts this response out of GZipMiddleware. Browsers send
        # Accept-Encoding: gzip, and Starlette's streaming gzip only flushes when zlib's buffer
        # fills, so every token would otherwise arrive in one burst at the end of the answer.
        return StreamingResponse(
            _sse(ctx, settings, hit),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Content-Encoding": "identity",
            },
        )

    if hit:
        logger.info("Cache hit", extra={"request_id": ctx.request_id, "key": ctx.cache_key[:40]})
        telemetry = _telemetry(
            ctx,
            provider=hit.get("provider", "cache"),
            model=hit.get("model", ctx.model_name),
            cache_status="hit",
            usage=hit.get("usage"),
            usage_source=hit.get("usage_source", "provider"),
            attempts=[],
            streamed=False,
        )
        return _json_response(
            ctx,
            content=hit.get("content", ""),
            model=hit.get("model", ctx.model_name),
            provider=hit.get("provider", "cache"),
            usage=hit.get("usage"),
            finish_reason=hit.get("finish_reason", "stop"),
            cached=True,
            telemetry=telemetry,
        )

    chain = build_chain(settings, simulate_primary_failure=ctx.simulate_failure)
    try:
        response, attempts = await chain.complete(
            messages=ctx.messages,
            model=ctx.model_name,
            temperature=ctx.temperature,
            max_tokens=ctx.max_tokens,
        )
    except ChainExhaustedError as exc:
        logger.error("All providers failed: %s", exc.message, extra={"request_id": ctx.request_id})
        return provider_error_response(
            exc.primary_error, ctx.request_id, attempts=[a.to_dict() for a in exc.attempts]
        )
    except ProviderError as exc:
        logger.error("Provider error: %s", exc.message, extra={"request_id": ctx.request_id})
        return provider_error_response(exc, ctx.request_id)

    # Report the chain slot that answered ("openai", "groq"), not the client object's own
    # label, so JSON and SSE telemetry agree and tests with fake providers stay honest.
    provider_name = attempts[-1].provider if attempts else response.provider
    usage = response.usage
    usage_source = "provider"
    if not usage:
        usage = estimate_usage(ctx.messages, response.content)
        usage_source = "estimated"
    ctx.guard.record_usage(usage.get("total_tokens", 0))
    await _store(ctx, response.content, response.model, provider_name, usage, usage_source)

    telemetry = _telemetry(
        ctx,
        provider=provider_name,
        model=response.model,
        cache_status="bypass" if ctx.bypass_cache or ctx.backend is None else "miss",
        usage=usage,
        usage_source=usage_source,
        attempts=attempts,
        streamed=False,
    )
    logger.info("Chat completion successful", extra={"request_id": ctx.request_id, **telemetry})
    return _json_response(
        ctx,
        content=response.content,
        model=response.model,
        provider=provider_name,
        usage=usage,
        finish_reason=response.finish_reason or "stop",
        cached=False,
        telemetry=telemetry,
    )


def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _sse(
    ctx: PreparedRequest, settings: Settings, hit: Optional[Dict[str, Any]]
) -> AsyncIterator[str]:
    """Server-Sent Events body: meta, delta*, done | error."""
    cache_status = "bypass" if ctx.bypass_cache or ctx.backend is None else "miss"

    if hit:
        model = hit.get("model", ctx.model_name)
        provider = hit.get("provider", "cache")
        lookup = ctx.lookup or Lookup(status="hit", hit=hit, match="exact", similarity=1.0)
        yield _sse_event(
            "meta",
            {
                "request_id": ctx.request_id,
                "model": model,
                "provider": provider,
                "cache": lookup.cache_block(cache_backend_name()) | {"key": ctx.cache_key},
            },
        )
        yield _sse_event("delta", {"content": hit.get("content", "")})
        yield _sse_event(
            "done",
            _telemetry(
                ctx,
                provider=provider,
                model=model,
                cache_status="hit",
                usage=hit.get("usage"),
                usage_source=hit.get("usage_source", "provider"),
                attempts=[],
                streamed=True,
                ttfb_ms=round((time.perf_counter() - ctx.started) * 1000, 1),
            ),
        )
        return

    chain = build_chain(settings, simulate_primary_failure=ctx.simulate_failure)
    attempts: List[Attempt] = []
    parts: List[str] = []
    provider_name = "unknown"
    model = ctx.model_name
    usage: Optional[Dict[str, int]] = None
    ttfb_ms: Optional[float] = None
    try:
        async for item in chain.stream(
            ctx.messages,
            ctx.model_name,
            attempts,
            temperature=ctx.temperature,
            max_tokens=ctx.max_tokens,
        ):
            if isinstance(item, StreamStart):
                provider_name, model = item.provider, item.model
                yield _sse_event(
                    "meta",
                    {
                        "request_id": ctx.request_id,
                        "model": model,
                        "provider": provider_name,
                        "cache": (ctx.lookup or Lookup(status=cache_status)).cache_block(
                            cache_backend_name()
                        )
                        | {"key": ctx.cache_key},
                        "attempts": [a.to_dict() for a in attempts],
                    },
                )
                continue
            chunk: StreamChunk = item
            if chunk.content:
                if ttfb_ms is None:
                    ttfb_ms = round((time.perf_counter() - ctx.started) * 1000, 1)
                parts.append(chunk.content)
                yield _sse_event("delta", {"content": chunk.content})
            if chunk.is_final and chunk.usage:
                usage = chunk.usage.model_dump(exclude={"total_cost"})
    except ChainExhaustedError as exc:
        status_code, code = classify_provider_error(exc.primary_error)
        yield _sse_event(
            "error",
            error_payload(
                code,
                exc.primary_error.message,
                provider=exc.primary_error.provider,
                request_id=ctx.request_id,
                status_code=status_code,
                attempts=[a.to_dict() for a in exc.attempts],
            ),
        )
        return
    except ProviderError as exc:
        status_code, code = classify_provider_error(exc)
        yield _sse_event(
            "error",
            error_payload(
                code,
                exc.message,
                provider=exc.provider,
                request_id=ctx.request_id,
                status_code=status_code,
                attempts=[a.to_dict() for a in attempts],
                partial_content="".join(parts) or None,
            ),
        )
        return

    content = "".join(parts)
    usage_source = "provider"
    if not usage:
        usage = estimate_usage(ctx.messages, content)
        usage_source = "estimated"
    ctx.guard.record_usage(usage.get("total_tokens", 0))
    await _store(ctx, content, model, provider_name, usage, usage_source)
    telemetry = _telemetry(
        ctx,
        provider=provider_name,
        model=model,
        cache_status=cache_status,
        usage=usage,
        usage_source=usage_source,
        attempts=attempts,
        streamed=True,
        ttfb_ms=ttfb_ms,
    )
    logger.info("Chat stream complete", extra={"request_id": ctx.request_id, **telemetry})
    yield _sse_event("done", telemetry)


@router.get("/models")
async def get_supported_models(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Models the demo can actually serve, default first, plus the full catalogue."""
    configured = settings.configured_providers
    available = [
        {"id": m, "provider": p, "configured": p in configured} for m, p in MODEL_CATALOG.items()
    ]
    serving = [m for m in available if m["configured"]] or available
    default_model = resolve_model(settings.default_model)
    serving.sort(key=lambda m: 0 if m["id"] == default_model else 1)
    return {
        "default_model": default_model,
        "models": serving,
        "models_by_provider": {p: models_for(p) for p in PROVIDERS},
        "configured_providers": configured,
        "fallback_chain": [f"{p}:{m}" for p, m in settings.fallback_chain],
        "total_models": len(MODEL_CATALOG),
    }


@router.get("/health")
async def health_check(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Chat-service health: providers, cache backend, guardrail budget, demo switches."""
    backend = await get_cache(settings)
    return {
        "status": "healthy" if settings.configured_providers else "degraded",
        "service": "chat",
        "timestamp": datetime.utcnow().isoformat(),
        "providers_configured": {p: p in settings.configured_providers for p in PROVIDERS},
        "default_model": resolve_model(settings.default_model),
        "fallback_chain": [f"{p}:{m}" for p, m in settings.fallback_chain],
        "cache": getattr(backend, "backend", "disabled") if backend else "disabled",
        "semantic_cache": semantic_status(settings),
        "streaming": "sse",
        "guardrails": get_guard(settings).snapshot(),
        "rate_limit": {
            "enabled": settings.rate_limit_enabled,
            "requests": settings.rate_limit_requests,
            "period_seconds": settings.rate_limit_period,
        },
        "demo": {
            "failure_toggle_enabled": settings.demo_failure_toggle_enabled,
            "simulate_primary_failure": settings.demo_simulate_primary_failure,
            "simulate_header": SIMULATE_FAILURE_HEADER,
        },
    }


# --------------------------------------------------------------------------- cache admin
def _require_cache() -> CacheBackend:
    if cache is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache is not enabled or not available",
        )
    return cache


@router.post("/cache/warm")
async def warm_cache(
    common_queries: List[Dict[str, Any]], settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """Warm the cache with common query/response pairs."""
    await get_cache(settings)
    backend = _require_cache()
    count = await backend.warm_cache(common_queries)
    return {"status": "success", "warmed_items": count, "timestamp": datetime.utcnow().isoformat()}


@router.get("/cache/stats")
async def get_cache_stats(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Cache statistics and health."""
    backend = await get_cache(settings)
    if backend is None:
        return {"cache_enabled": False, "message": "Cache is not enabled or not available"}
    stats = await backend.get_stats()
    return {
        "cache_enabled": True,
        "backend": backend.backend,
        "stats": stats.to_dict(),
        "health": await backend.health_check(),
        "configuration": {
            "ttl_seconds": settings.cache_ttl_seconds,
            "semantic_cache_enabled": settings.semantic_cache_enabled,
            "semantic_threshold": settings.semantic_cache_threshold,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.delete("/cache")
async def clear_cache(
    pattern: Optional[str] = None,
    model: Optional[str] = None,
    user_id: Optional[str] = None,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Clear cached items, optionally by glob pattern or model/user."""
    await get_cache(settings)
    backend = _require_cache()
    if (model or user_id) and cache_key_generator:
        pattern = cache_key_generator.generate_pattern(model, user_id)
    if pattern:
        count = await backend.invalidate_cache(pattern=pattern)
    else:
        count = -1 if await backend.clear_all() else 0
    if semantic_index is not None:
        semantic_index.clear()
    return {
        "status": "success",
        "cleared_items": count,
        "pattern": pattern,
        "timestamp": datetime.utcnow().isoformat(),
    }


__all__ = [
    "router",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ProviderFactory",
    "make_provider",
    "build_chain",
    "build_cache",
    "get_cache",
    "get_semantic",
    "initialize_cache",
    "cache_backend_name",
    "estimate_tokens",
    "SIMULATE_FAILURE_HEADER",
    "Tuple",
]
