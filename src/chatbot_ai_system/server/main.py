"""FastAPI application factory and server entry point."""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request, status
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
    logger.info(f"Starting AI Chatbot System v{__version__}")

    # Initialize database
    try:
        from chatbot_ai_system.database import init_db

        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")

    # Initialize Redis cache for chat API
    try:
        from chatbot_ai_system.api.chat import initialize_cache

        await initialize_cache(settings)
        logger.info("Redis cache system initialized")
    except Exception as e:
        logger.warning(f"Redis cache initialization skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down AI Chatbot System")

    # Close database
    try:
        from chatbot_ai_system.database import close_db

        await close_db()
    except Exception:
        pass

    # Close Redis cache
    try:
        from chatbot_ai_system.api.chat import redis_cache

        if redis_cache:
            await redis_cache.disconnect()
            logger.info("Redis cache disconnected")
    except Exception as e:
        logger.warning(f"Error disconnecting Redis cache: {e}")

    # Shutdown WebSocket manager
    try:
        from chatbot_ai_system.websocket.ws_manager import WebSocketManager

        ws_manager = WebSocketManager()
        await ws_manager.shutdown()
        logger.info("WebSocket manager shut down")
    except Exception as e:
        logger.warning(f"Error shutting down WebSocket manager: {e}")


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

    # Add middleware (order matters - reverse order of execution)
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
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
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
            content={
                "error": "Validation error",
                "details": exc.errors(),
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
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
            content={
                "error": "Internal server error",
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
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
    from chatbot_ai_system.api.health import health_router
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
        """Health check endpoint."""
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "version": __version__,
                "service": "chatbot-ai-system",
                "timestamp": datetime.utcnow().isoformat(),
                "environment": settings.environment,
                "providers_configured": {
                    "openai": settings.has_openai_key,
                    "anthropic": settings.has_anthropic_key,
                },
            },
        )

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
