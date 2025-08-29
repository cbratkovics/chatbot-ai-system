"""Main FastAPI application entry point."""

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from ..config import Settings
from ..telemetry import setup_logging, setup_metrics, setup_tracing
from .middleware import (
    ErrorHandlerMiddleware,
    MetricsMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    TenantMiddleware,
)
from .routes import health_router, v1_router, v2_router, websocket_router

logger = structlog.get_logger()
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting chatbot-ai-system server", version=settings.APP_VERSION)
    
    # Setup telemetry
    setup_logging()
    setup_metrics()
    if settings.ENABLE_TRACING:
        setup_tracing()
    
    # Initialize connection pools and resources
    logger.info("Initializing connection pools")
    # TODO: Initialize Redis, database, etc.
    
    yield
    
    # Cleanup
    logger.info("Shutting down chatbot-ai-system server")
    # TODO: Close connections, cleanup resources


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production-ready AI chatbot system with multi-provider support",
        docs_url="/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/redoc" if settings.ENABLE_DOCS else None,
        openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware (order matters - reverse order of execution)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(RequestIdMiddleware)
    
    # Mount Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    # Include routers
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(v1_router, prefix="/api/v1", tags=["v1"])
    app.include_router(v2_router, prefix="/api/v2", tags=["v2"])
    app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
    
    return app


app = create_app()


def handle_shutdown(signum: int, frame: Any) -> None:
    """Handle graceful shutdown."""
    logger.info("Received shutdown signal", signal=signum)
    asyncio.create_task(shutdown())


async def shutdown() -> None:
    """Perform graceful shutdown."""
    logger.info("Initiating graceful shutdown")
    # TODO: Complete in-flight requests, close connections
    await asyncio.sleep(0.5)  # Allow time for cleanup


def start_server() -> None:
    """Start the Uvicorn server."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    uvicorn.run(
        "chatbot_ai_system.server.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.ACCESS_LOG,
        loop="uvloop" if not settings.DEBUG else "asyncio",
    )


if __name__ == "__main__":
    start_server()