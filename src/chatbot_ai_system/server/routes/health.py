"""Health check endpoints."""

import time
from typing import Dict, Any

import structlog
from fastapi import APIRouter, status
from prometheus_client import Info

from ...config import settings

logger = structlog.get_logger()
router = APIRouter()

# Application info metric
APP_INFO = Info("app", "Application information")
APP_INFO.info({
    "version": settings.APP_VERSION,
    "environment": settings.APP_ENV,
})

START_TIME = time.time()


@router.get("/", status_code=status.HTTP_200_OK)
async def health() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "uptime": time.time() - START_TIME,
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness() -> Dict[str, Any]:
    """Readiness probe for Kubernetes."""
    # TODO: Check database connection
    # TODO: Check Redis connection
    # TODO: Check external service connections
    
    checks = {
        "database": True,  # Placeholder
        "redis": True,  # Placeholder
        "providers": True,  # Placeholder
    }
    
    all_ready = all(checks.values())
    
    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": time.time(),
    }


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness() -> Dict[str, str]:
    """Liveness probe for Kubernetes."""
    return {
        "status": "alive",
        "timestamp": str(time.time()),
    }


@router.get("/version", status_code=status.HTTP_200_OK)
async def version() -> Dict[str, str]:
    """Get application version information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "debug": settings.DEBUG,
    }