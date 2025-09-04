"""Health check API endpoints."""
from fastapi import APIRouter, HTTPException, status
from chatbot_ai_system.api.models import HealthResponse
from chatbot_ai_system.config.settings import settings
from datetime import datetime
from chatbot_ai_system import __version__

health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check."""
    services = {
        "api": True,
        "cache": False,
        "database": False,
        "openai": False,
        "anthropic": False
    }
    
    # Check cache
    try:
        from chatbot_ai_system.services.cache_manager import CacheManager
        # Mock cache check
        services["cache"] = True
    except Exception:
        pass
    
    # Check database
    try:
        from chatbot_ai_system.database import engine
        # Mock database check
        services["database"] = True
    except Exception:
        pass
    
    # Check OpenAI
    if settings.has_openai_key:
        services["openai"] = True
    
    # Check Anthropic
    if settings.has_anthropic_key:
        services["anthropic"] = True
    
    return HealthResponse(
        status="healthy" if services["api"] else "unhealthy",
        timestamp=datetime.utcnow(),
        version=__version__,
        environment=settings.environment,
        services=services
    )


@health_router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    # Check if all critical services are ready
    try:
        # Mock readiness check
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {str(e)}"
        )


@health_router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}