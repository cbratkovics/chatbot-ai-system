"""FastAPI application factory and server entry point."""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from chatbot_ai_system import __version__
from chatbot_ai_system.api.errors import ErrorEnvelopeMiddleware, error_payload
from chatbot_ai_system.api.routes import api_router
from chatbot_ai_system.config.settings import settings

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Create rate limiter
limiter = Limiter(
    key_func=get_remote_address, default_limits=[f"{settings.rate_limit_requests}/minute"]
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests."""

    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # Add headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        # Log request
        logger.info(
            "Request processed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": process_time,
            },
        )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle."""
    # Startup
    app.state.start_time = time.time()
    logger.info(f"Starting AI Chatbot System v{__version__}")

    # Initialize database
    try:
        from chatbot_ai_system.database import init_db

        await init_db()
        logger.info("Database initialized")
    except ValueError as e:
        # DATABASE_URL not configured - this is expected for Pinecone-only deployments
        logger.info("Database not configured, skipping initialization (Pinecone-only mode)")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")

    # Initialize the response cache: Redis if reachable, else in-process memory.
    try:
        from chatbot_ai_system.api.chat import cache_backend_name, initialize_cache

        await initialize_cache(settings)
        logger.info("Response cache backend: %s", cache_backend_name())
    except Exception as e:
        logger.warning(f"Cache initialization failed, continuing without cache: {e}")

    from chatbot_ai_system.providers.catalog import provider_for, resolve_model

    if provider_for(resolve_model(settings.default_model)) is None:
        logger.warning(
            "DEFAULT_MODEL=%r is not in the model catalogue; requests for 'default' will 404",
            settings.default_model,
        )
    elif resolve_model(settings.default_model) != settings.default_model:
        logger.warning(
            "DEFAULT_MODEL=%r is a legacy id; serving %r instead. Update the env var.",
            settings.default_model,
            resolve_model(settings.default_model),
        )
    logger.info(
        "Providers configured: %s (default model %s, fallbacks %s)",
        ", ".join(settings.configured_providers) or "none",
        settings.default_model,
        settings.fallback_chain or "none",
    )

    yield

    # Shutdown
    logger.info("Shutting down AI Chatbot System")

    # Close database
    try:
        from chatbot_ai_system.database import close_db

        await close_db()
    except Exception:
        pass

    # Close cache
    try:
        from chatbot_ai_system.api import chat as chat_api

        if chat_api.cache:
            await chat_api.cache.disconnect()
            chat_api.cache = None  # next get_cache() rebuilds instead of reusing a closed one
            logger.info("Cache disconnected")
    except Exception as e:
        logger.warning(f"Error disconnecting cache: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Chatbot System",
        description="Production-ready multi-provider AI chatbot platform with OpenAI and Anthropic support",
        version=__version__,
        docs_url="/docs" if settings.environment != "production" else "/docs",
        redoc_url="/redoc" if settings.environment != "production" else None,
        openapi_url="/openapi.json" if settings.environment != "production" else "/openapi.json",
        lifespan=lifespan,
    )

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware. Starlette wraps in reverse order: the first add_middleware call is the
    # innermost. ErrorEnvelopeMiddleware goes first so it sits *inside* CORS and its
    # 500s still carry CORS headers.
    app.add_middleware(ErrorEnvelopeMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SlowAPIMiddleware)

    # Add exception handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            f"HTTP exception: {exc.detail}",
            extra={
                "request_id": request_id,
                "status_code": exc.status_code,
                "path": request.url.path,
            },
        )
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code", "http_error"))
            message = str(detail.get("message", detail))
        else:
            code = "http_error"
            message = str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, message, request_id=request_id),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            f"Validation error: {exc.errors()}",
            extra={"request_id": request_id, "path": request.url.path},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(
                "validation_error",
                "Request validation failed",
                request_id=request_id,
                details=jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            f"Unexpected error: {str(exc)}",
            extra={"request_id": request_id, "path": request.url.path},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_payload("internal_error", "Internal server error", request_id=request_id),
        )

    # Add routes
    app.include_router(api_router, prefix="/api/v1")

    # Add authentication endpoints
    from chatbot_ai_system.api.auth import auth_router

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    # Add tenant endpoints
    from chatbot_ai_system.api.tenants import tenant_router

    app.include_router(tenant_router, prefix="/api/v1/tenants", tags=["tenants"])

    # Add cache endpoints
    from chatbot_ai_system.api.cache import cache_router

    app.include_router(cache_router, prefix="/api/v1/cache", tags=["cache"])

    # Add health endpoints
    from chatbot_ai_system.v1.routes.health import router as health_router

    app.include_router(health_router, prefix="/api/v1", tags=["health"])

    # Add WebSocket routes
    from chatbot_ai_system.api.websocket import ws_router

    app.include_router(ws_router)

    # Add a direct /ws endpoint for compatibility
    from fastapi import WebSocket

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Direct WebSocket endpoint for compatibility."""
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
        except Exception:
            pass
        finally:
            await websocket.close()

    # Health check endpoint
    @app.get("/health")
    async def health():
        """Enhanced health check endpoint for production monitoring."""
        health_status = {
            "status": "healthy",
            "version": __version__,
            "service": "chatbot-ai-system",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.environment,
            "checks": {},
        }

        # Cache backend: redis, memory, or disabled. Memory is a healthy state for the
        # demo; only an enabled-but-broken cache degrades.
        try:
            from chatbot_ai_system.api.chat import get_cache

            backend = await get_cache(settings)
            if backend is None:
                health_status["checks"]["cache"] = "disabled"
            else:
                cache_health = await backend.health_check()
                health_status["checks"]["cache"] = backend.backend
                if not cache_health.get("connected", True):
                    health_status["checks"]["cache"] = f"{backend.backend}: unhealthy"
                    health_status["status"] = "degraded"
        except Exception as e:
            health_status["checks"]["cache"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"

        # AI providers: at least one key must be present to serve completions.
        providers = settings.configured_providers
        if providers:
            health_status["checks"]["ai_providers"] = f"configured: {', '.join(providers)}"
        else:
            health_status["checks"]["ai_providers"] = "no API keys configured"
            health_status["status"] = "unhealthy"
        health_status["checks"]["default_model"] = settings.default_model
        health_status["checks"]["fallback_chain"] = [
            f"{p}:{m}" for p, m in settings.fallback_chain
        ]

        return JSONResponse(
            status_code=200 if health_status["status"] == "healthy" else 503,
            content=health_status,
        )

    @app.get("/metrics")
    async def metrics():
        """Basic metrics endpoint for monitoring."""
        uptime = time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0
        return {
            "uptime_seconds": uptime,
            "environment": settings.environment,
            "version": __version__,
        }

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "AI Chatbot System API",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
            "api": "/api/v1",
        }

    return app


app = create_app()


def start_server():
    """Start the server programmatically."""
    uvicorn.run(
        "chatbot_ai_system.server.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.reload if settings.is_development else False,
        workers=settings.workers if not settings.reload else 1,
        access_log=settings.is_development,
    )


if __name__ == "__main__":
    start_server()
