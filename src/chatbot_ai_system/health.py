"""Health check endpoints for monitoring and readiness probes."""
from fastapi import APIRouter, status, Depends
from typing import Dict, Any, Optional
from datetime import datetime
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError

router = APIRouter(tags=["health"])


async def check_redis(redis_url: str = "redis://localhost:6379/0") -> bool:
    """Check Redis connectivity."""
    try:
        client = await aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        await client.close()
        return True
    except (ConnectionError, Exception):
        return False


async def check_providers() -> Dict[str, bool]:
    """Check provider availability."""
    # In production, would actually test provider endpoints
    return {"openai": True, "anthropic": True}


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "chatbot-ai-system",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> Dict[str, Any]:
    """Readiness check for Kubernetes."""
    checks = {"redis": await check_redis(), "providers": await check_providers()}

    # System is ready if Redis is available and at least one provider is available
    providers_check = checks["providers"]
    if isinstance(providers_check, dict):
        all_ready = checks["redis"] and any(providers_check.values())
    else:
        all_ready = checks["redis"] and bool(providers_check)

    return {"ready": all_ready, "checks": checks, "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check() -> Dict[str, str]:
    """Liveness probe for Kubernetes."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
