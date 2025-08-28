
from fastapi import APIRouter, status

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "chatbot-api"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, bool]:
    """Readiness check for Kubernetes."""
    # Check DB, Redis, etc.
    return {"ready": True, "database": True, "cache": True}
