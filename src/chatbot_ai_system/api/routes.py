"""API routes for chatbot system with versioning."""


from fastapi import APIRouter

# Import our new chat router
from chatbot_ai_system.api.chat import router as chat_router

# Create main API router with versioning
api_router = APIRouter(
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    }
)

# Include the chat router
api_router.include_router(chat_router, tags=["Chat"])


# Additional API-level endpoints


@api_router.get("/status")
async def status():
    """API status endpoint with connectivity checks."""
    from datetime import datetime

    from chatbot_ai_system.config.settings import get_settings

    settings = get_settings()

    status_info = {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {
            "api": "healthy",
            "cache": "unknown",
            "database": "unknown",
        },
        "providers": {
            "openai": "configured" if settings.has_openai_key else "not_configured",
            "anthropic": "configured" if settings.has_anthropic_key else "not_configured",
        },
    }

    # Check cache connectivity if available
    try:
        from chatbot_ai_system.cache import cache

        test_key = "health:check"
        await cache.set(test_key, "ok", ttl=10)
        if await cache.get(test_key) == "ok":
            status_info["services"]["cache"] = "healthy"
        else:
            status_info["services"]["cache"] = "unhealthy"
    except Exception:
        status_info["services"]["cache"] = "disconnected"

    # Check database connectivity if available
    try:
        from sqlalchemy import text

        from chatbot_ai_system.database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            status_info["services"]["database"] = "healthy"
    except Exception:
        status_info["services"]["database"] = "disconnected"

    # Determine overall status
    if all(s in ["healthy", "unknown"] for s in status_info["services"].values()):
        status_info["status"] = "operational"
    elif any(s == "healthy" for s in status_info["services"].values()):
        status_info["status"] = "operational"
    else:
        status_info["status"] = "unhealthy"

    return status_info
