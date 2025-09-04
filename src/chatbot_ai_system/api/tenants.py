"""Tenant management API endpoints."""
from fastapi import APIRouter, HTTPException, status
from chatbot_ai_system.api.models import TenantInfo
from typing import List
from datetime import datetime

tenant_router = APIRouter()


@tenant_router.get("/", response_model=List[TenantInfo])
async def list_tenants():
    """List all tenants."""
    # Mock tenant list
    return [
        TenantInfo(
            id="tenant-1",
            name="Default Tenant",
            created_at=datetime.utcnow(),
            rate_limit=100,
            rate_period=60
        ),
        TenantInfo(
            id="tenant-2",
            name="Premium Tenant",
            created_at=datetime.utcnow(),
            rate_limit=1000,
            rate_period=60
        )
    ]


@tenant_router.get("/{tenant_id}", response_model=TenantInfo)
async def get_tenant(tenant_id: str):
    """Get tenant by ID."""
    if tenant_id == "tenant-1":
        return TenantInfo(
            id="tenant-1",
            name="Default Tenant",
            created_at=datetime.utcnow(),
            rate_limit=100,
            rate_period=60
        )
    elif tenant_id == "tenant-2":
        return TenantInfo(
            id="tenant-2",
            name="Premium Tenant",
            created_at=datetime.utcnow(),
            rate_limit=1000,
            rate_period=60
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )


@tenant_router.post("/", response_model=TenantInfo, status_code=status.HTTP_201_CREATED)
async def create_tenant(name: str, rate_limit: int = 100, rate_period: int = 60):
    """Create a new tenant."""
    import uuid
    return TenantInfo(
        id=f"tenant-{uuid.uuid4().hex[:8]}",
        name=name,
        created_at=datetime.utcnow(),
        rate_limit=rate_limit,
        rate_period=rate_period
    )


@tenant_router.put("/{tenant_id}", response_model=TenantInfo)
async def update_tenant(tenant_id: str, name: str = None, rate_limit: int = None, rate_period: int = None):
    """Update tenant."""
    if tenant_id not in ["tenant-1", "tenant-2"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )
    
    # Mock update
    return TenantInfo(
        id=tenant_id,
        name=name or "Updated Tenant",
        created_at=datetime.utcnow(),
        rate_limit=rate_limit or 100,
        rate_period=rate_period or 60
    )


@tenant_router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: str):
    """Delete tenant."""
    if tenant_id not in ["tenant-1", "tenant-2"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )
    return