"""Tenant manager for multi-tenant isolation and management."""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TenantManager:
    """Manages tenant isolation and operations."""

    def __init__(self, db: AsyncSession, cache_client: Any | None = None):
        """Initialize tenant manager.

        Args:
            db: Database session
            cache_client: Cache client for tenant data
        """
        self.db = db
        self.cache_client = cache_client
        self.tenants_cache = {}

    async def create_tenant(self, tenant_config: dict[str, Any]) -> dict[str, Any]:
        """Create new tenant.

        Args:
            tenant_config: Tenant configuration

        Returns:
            Created tenant data
        """
        try:
            from api.database.models import Tenant

            tenant = Tenant(
                id=tenant_config.get("tenant_id"),
                name=tenant_config["name"],
                tier=tenant_config.get("tier", "basic"),
                status="active",
                created_at=datetime.utcnow(),
                settings=json.dumps(tenant_config.get("settings", {})),
            )

            self.db.add(tenant)
            await self.db.commit()

            tenant_data = {
                "tenant_id": tenant.id,
                "name": tenant.name,
                "tier": tenant.tier,
                "status": tenant.status,
                "created_at": tenant.created_at.isoformat(),
            }

            self.tenants_cache[tenant.id] = tenant_data

            logger.info(f"Created tenant: {tenant.id}")
            return tenant_data

        except Exception as e:
            logger.error(f"Failed to create tenant: {e}")
            await self.db.rollback()
            raise

    async def get_tenant(self, tenant_id: str) -> dict[str, Any] | None:
        """Get tenant by ID.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant data if found
        """
        if tenant_id in self.tenants_cache:
            return self.tenants_cache[tenant_id]

        try:
            from sqlalchemy import select

            from api.database.models import Tenant

            result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()

            if tenant:
                tenant_data = {
                    "tenant_id": tenant.id,
                    "name": tenant.name,
                    "tier": tenant.tier,
                    "status": tenant.status,
                    "settings": json.loads(tenant.settings) if tenant.settings else {},
                    "created_at": tenant.created_at.isoformat(),
                }

                self.tenants_cache[tenant_id] = tenant_data
                return tenant_data

            return None

        except Exception as e:
            logger.error(f"Failed to get tenant: {e}")
            return None

    async def update_tenant(self, tenant_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update tenant configuration.

        Args:
            tenant_id: Tenant identifier
            updates: Updates to apply

        Returns:
            Updated tenant data
        """
        try:
            from sqlalchemy import update

            from api.database.models import Tenant

            await self.db.execute(update(Tenant).where(Tenant.id == tenant_id).values(**updates))
            await self.db.commit()

            if tenant_id in self.tenants_cache:
                self.tenants_cache[tenant_id].update(updates)

            return await self.get_tenant(tenant_id)

        except Exception as e:
            logger.error(f"Failed to update tenant: {e}")
            await self.db.rollback()
            raise

    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Success status
        """
        try:
            from sqlalchemy import delete

            from api.database.models import Tenant

            await self.db.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await self.db.commit()

            self.tenants_cache.pop(tenant_id, None)

            logger.info(f"Deleted tenant: {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete tenant: {e}")
            await self.db.rollback()
            return False

    async def get_tenant_data(self, tenant_id: str, resource: str) -> Any:
        """Get tenant-specific data.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type

        Returns:
            Tenant data
        """
        try:
            from sqlalchemy import select

            if resource == "chats":
                from api.models import Chat

                result = await self.db.execute(select(Chat).where(Chat.tenant_id == tenant_id))
            elif resource == "users":
                from api.models import User

                result = await self.db.execute(select(User).where(User.tenant_id == tenant_id))
            else:
                return None

            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get tenant data: {e}")
            return None

    async def check_quota(self, tenant_id: str, resource: str, requested: int) -> dict[str, Any]:
        """Check tenant quota.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type
            requested: Requested amount

        Returns:
            Quota check result
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return {"allowed": False, "reason": "Tenant not found"}

        settings = tenant.get("settings", {})
        limits = settings.get("rate_limits", {})

        if resource == "tokens":
            daily_limit = limits.get("tokens_per_day", 100000)
            used_today = await self._get_usage_today(tenant_id, "tokens")
            remaining = daily_limit - used_today

            return {
                "allowed": requested <= remaining,
                "remaining": max(0, remaining),
                "limit": daily_limit,
            }

        return {"allowed": True, "remaining": -1}

    async def has_feature(self, tenant_id: str, feature: str) -> bool:
        """Check if tenant has feature.

        Args:
            tenant_id: Tenant identifier
            feature: Feature name

        Returns:
            True if feature is enabled
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False

        settings = tenant.get("settings", {})
        features = settings.get("features", {})

        return features.get(feature, False)

    async def track_usage(self, tenant_id: str, resource: str, amount: int):
        """Track resource usage.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type
            amount: Usage amount
        """
        try:
            from api.models import Usage

            usage = Usage(
                tenant_id=tenant_id, resource=resource, amount=amount, timestamp=datetime.utcnow()
            )

            self.db.add(usage)
            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to track usage: {e}")
            await self.db.rollback()

    async def calculate_billing(
        self, tenant_id: str, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Calculate tenant billing.

        Args:
            tenant_id: Tenant identifier
            start_date: Billing period start
            end_date: Billing period end

        Returns:
            Billing information
        """
        try:
            from sqlalchemy import func, select

            from api.models import Usage

            result = await self.db.execute(
                select(Usage.resource, func.sum(Usage.amount).label("total"))
                .where(
                    Usage.tenant_id == tenant_id,
                    Usage.timestamp >= start_date,
                    Usage.timestamp <= end_date,
                )
                .group_by(Usage.resource)
            )

            usage_data = {row.resource: row.total for row in result}

            tenant = await self.get_tenant(tenant_id)
            tier_pricing = self._get_tier_pricing(tenant.get("tier", "basic"))

            total_cost = 0
            breakdown = {}

            for resource, amount in usage_data.items():
                unit_price = tier_pricing.get(resource, 0)
                cost = amount * unit_price
                total_cost += cost
                breakdown[resource] = {"amount": amount, "unit_price": unit_price, "cost": cost}

            return {
                "tenant_id": tenant_id,
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "total_cost": total_cost,
                "usage_breakdown": breakdown,
            }

        except Exception as e:
            logger.error(f"Failed to calculate billing: {e}")
            return {}

    async def migrate_tenant(self, tenant_id: str, from_tier: str, to_tier: str) -> dict[str, Any]:
        """Migrate tenant between tiers.

        Args:
            tenant_id: Tenant identifier
            from_tier: Current tier
            to_tier: Target tier

        Returns:
            Migration result
        """
        try:
            updates = {"tier": to_tier, "migrated_at": datetime.utcnow()}

            await self.update_tenant(tenant_id, updates)

            logger.info(f"Migrated tenant {tenant_id} from {from_tier} to {to_tier}")

            return {
                "success": True,
                "tenant_id": tenant_id,
                "from_tier": from_tier,
                "to_tier": to_tier,
            }

        except Exception as e:
            logger.error(f"Failed to migrate tenant: {e}")
            return {"success": False, "error": str(e)}

    def apply_tenant_filter(self, base_query: str, tenant_id: str) -> str:
        """Apply tenant filter to query.

        Args:
            base_query: Base SQL query
            tenant_id: Tenant identifier

        Returns:
            Filtered query
        """
        return f"{base_query} WHERE tenant_id = '{tenant_id}'"

    async def backup_tenant_data(self, tenant_id: str) -> dict[str, Any]:
        """Backup tenant data.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Backup data
        """
        backup = {"tenant_id": tenant_id, "timestamp": datetime.utcnow().isoformat(), "data": {}}

        resources = ["chats", "users", "settings"]

        for resource in resources:
            data = await self.get_tenant_data(tenant_id, resource)
            backup["data"][resource] = data

        return backup

    async def restore_tenant_data(self, backup_data: dict[str, Any]) -> dict[str, Any]:
        """Restore tenant data from backup.

        Args:
            backup_data: Backup data to restore

        Returns:
            Restore result
        """
        try:
            tenant_id = backup_data["tenant_id"]
            data = backup_data["data"]

            for _resource, items in data.items():
                for item in items:
                    self.db.add(item)

            await self.db.commit()

            return {"success": True, "tenant_id": tenant_id}

        except Exception as e:
            logger.error(f"Failed to restore tenant data: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _get_usage_today(self, tenant_id: str, resource: str) -> int:
        """Get today's usage for resource.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type

        Returns:
            Usage amount
        """
        try:
            from sqlalchemy import func, select

            from api.models import Usage

            today = datetime.utcnow().date()

            result = await self.db.execute(
                select(func.sum(Usage.amount)).where(
                    Usage.tenant_id == tenant_id,
                    Usage.resource == resource,
                    func.date(Usage.timestamp) == today,
                )
            )

            return result.scalar() or 0

        except Exception as e:
            logger.error(f"Failed to get usage: {e}")
            return 0

    def _get_tier_pricing(self, tier: str) -> dict[str, float]:
        """Get pricing for tier.

        Args:
            tier: Tier name

        Returns:
            Pricing configuration
        """
        pricing = {
            "basic": {"api_calls": 0.001, "tokens": 0.00001, "storage_mb": 0.01},
            "professional": {"api_calls": 0.0008, "tokens": 0.000008, "storage_mb": 0.008},
            "enterprise": {"api_calls": 0.0005, "tokens": 0.000005, "storage_mb": 0.005},
        }

        return pricing.get(tier, pricing["basic"])
