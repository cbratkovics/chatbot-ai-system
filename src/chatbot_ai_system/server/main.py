"""FastAPI application factory and server entry point."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from chatbot_ai_system import __version__
from chatbot_ai_system.config import settings
from chatbot_ai_system.api.routes import api_router
# Middleware will be added inline since we're using simpler versions


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle."""
    # Startup
    print(f"🚀 Starting AI Chatbot System v{__version__}")
    
    # Initialize database
    try:
        from chatbot_ai_system.database import init_db
        await init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"⚠️  Database initialization skipped: {e}")
    
    # Initialize cache
    try:
        from chatbot_ai_system.cache import cache
        await cache.connect()
        print("✅ Cache connected")
    except Exception as e:
        print(f"⚠️  Cache connection skipped: {e}")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AI Chatbot System")
    
    # Close database
    try:
        from chatbot_ai_system.database import close_db
        await close_db()
    except Exception:
        pass
    
    # Close cache
    try:
        from chatbot_ai_system.cache import cache
        await cache.disconnect()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Chatbot System",
        description="Production-ready multi-provider AI chatbot platform",
        version=__version__,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
    )
    
    # Add middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add routes
    app.include_router(api_router, prefix="/api/v1")
    
    # Health check
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "version": __version__,
                "service": "ai-chatbot-system",
            }
        )
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "AI Chatbot System API",
            "version": __version__,
            "docs": "/docs" if settings.environment != "production" else None,
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
    )


if __name__ == "__main__":
    start_server()