"""Data isolation manager for multi-tenant architecture."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query

logger = logging.getLogger(__name__)


class IsolationManager:
    """Manages data isolation between tenants."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    def apply_tenant_filter(self, query: Query, tenant_id: str, model_class: Any) -> Query:
        """Apply tenant filter to database query.

        Args:
            query: Base SQLAlchemy query
            tenant_id: Tenant identifier
            model_class: Model class being queried

        Returns:
            Filtered query
        """
        if hasattr(model_class, "tenant_id"):
            return query.filter(model_class.tenant_id == tenant_id)
        return query

    async def validate_tenant_access(
        self, tenant_id: str, resource_id: str, resource_type: str
    ) -> bool:
        """Validate tenant has access to resource.

        Args:
            tenant_id: Tenant identifier
            resource_id: Resource identifier
            resource_type: Type of resource

        Returns:
            True if access is allowed
        """
        try:
            # Map resource types to models
            resource_models = {
                "chat": "Chat",
                "message": "Message",
                "user": "User",
                "document": "Document",
            }

            model_name = resource_models.get(resource_type)
            if not model_name:
                logger.warning(f"Unknown resource type: {resource_type}")
                return False

            # Dynamic model import
            from api import models

            model_class = getattr(models, model_name)

            # Check if resource belongs to tenant
            result = await self.db.execute(
                select(model_class).where(
                    and_(model_class.id == resource_id, model_class.tenant_id == tenant_id)
                )
            )

            resource = result.scalar_one_or_none()
            return resource is not None

        except Exception as e:
            logger.error(f"Failed to validate tenant access: {e}")
            return False

    async def create_tenant_namespace(
        self, tenant_id: str, namespace_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Create isolated namespace for tenant.

        Args:
            tenant_id: Tenant identifier
            namespace_config: Namespace configuration

        Returns:
            Created namespace details
        """
        try:
            # Create tenant-specific schema or partition
            namespace = {
                "tenant_id": tenant_id,
                "namespace": f"tenant_{tenant_id}",
                "created_at": datetime.utcnow().isoformat(),
                "config": namespace_config,
            }

            # In production, this would create actual database schemas
            # For now, we'll track in metadata
            from api.models import TenantNamespace

            ns = TenantNamespace(
                tenant_id=tenant_id,
                namespace=namespace["namespace"],
                config=namespace_config,
                created_at=datetime.utcnow(),
            )

            self.db.add(ns)
            await self.db.commit()

            logger.info(f"Created namespace for tenant: {tenant_id}")
            return namespace

        except Exception as e:
            logger.error(f"Failed to create tenant namespace: {e}")
            await self.db.rollback()
            raise

    async def enforce_row_level_security(
        self, tenant_id: str, operation: str, table: str, data: dict[str, Any]
    ) -> bool:
        """Enforce row-level security policies.

        Args:
            tenant_id: Tenant identifier
            operation: Operation type (read, write, delete)
            table: Table name
            data: Data being accessed

        Returns:
            True if operation is allowed
        """
        # Define RLS policies
        policies = {"read": ["owner", "shared"], "write": ["owner"], "delete": ["owner"]}

        allowed_policies = policies.get(operation, [])

        # Check ownership
        if "owner" in allowed_policies:
            if data.get("tenant_id") == tenant_id:
                return True

        # Check sharing permissions
        if "shared" in allowed_policies:
            shared_with = data.get("shared_with", [])
            if tenant_id in shared_with:
                return True

        logger.warning(
            f"RLS violation - Tenant: {tenant_id}, Operation: {operation}, Table: {table}"
        )
        return False

    async def get_tenant_boundaries(self, tenant_id: str) -> dict[str, Any]:
        """Get data boundaries for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Boundary configuration
        """
        try:
            from api.models import Tenant

            result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()

            if not tenant:
                return {}

            # Define boundaries based on tier
            tier_boundaries = {
                "basic": {
                    "max_chats": 100,
                    "max_messages_per_chat": 1000,
                    "max_storage_mb": 100,
                    "max_users": 5,
                    "data_retention_days": 30,
                },
                "professional": {
                    "max_chats": 1000,
                    "max_messages_per_chat": 10000,
                    "max_storage_mb": 1000,
                    "max_users": 50,
                    "data_retention_days": 90,
                },
                "enterprise": {
                    "max_chats": -1,  # Unlimited
                    "max_messages_per_chat": -1,
                    "max_storage_mb": 10000,
                    "max_users": -1,
                    "data_retention_days": 365,
                },
            }

            boundaries = tier_boundaries.get(tenant.tier, tier_boundaries["basic"])
            boundaries["tenant_id"] = tenant_id
            boundaries["tier"] = tenant.tier

            return boundaries

        except Exception as e:
            logger.error(f"Failed to get tenant boundaries: {e}")
            return {}

    async def check_boundary_limits(
        self, tenant_id: str, resource_type: str, current_count: int = 0, requested: int = 1
    ) -> dict[str, Any]:
        """Check if operation exceeds tenant boundaries.

        Args:
            tenant_id: Tenant identifier
            resource_type: Type of resource
            current_count: Current resource count
            requested: Requested additional resources

        Returns:
            Boundary check result
        """
        boundaries = await self.get_tenant_boundaries(tenant_id)

        if not boundaries:
            return {"allowed": False, "reason": "Tenant not found"}

        # Map resource types to boundary keys
        boundary_map = {
            "chats": "max_chats",
            "messages": "max_messages_per_chat",
            "storage": "max_storage_mb",
            "users": "max_users",
        }

        boundary_key = boundary_map.get(resource_type)
        if not boundary_key:
            return {"allowed": True, "reason": "No boundary defined"}

        limit = boundaries.get(boundary_key, -1)

        # -1 means unlimited
        if limit == -1:
            return {"allowed": True, "remaining": -1}

        # Check if request exceeds limit
        new_total = current_count + requested
        if new_total > limit:
            return {
                "allowed": False,
                "reason": f"Exceeds {boundary_key} limit",
                "limit": limit,
                "current": current_count,
                "requested": requested,
            }

        return {"allowed": True, "remaining": limit - new_total, "limit": limit}

    async def audit_tenant_access(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource: str,
        result: str,
        metadata: dict | None = None,
    ):
        """Audit tenant data access for compliance.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            action: Action performed
            resource: Resource accessed
            result: Result of action
            metadata: Additional metadata
        """
        try:
            from api.models import AuditLog

            audit = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource=resource,
                result=result,
                metadata=metadata or {},
                timestamp=datetime.utcnow(),
                ip_address=metadata.get("ip_address") if metadata else None,
            )

            self.db.add(audit)
            await self.db.commit()

            # Log for SIEM integration
            logger.info(
                f"AUDIT - Tenant: {tenant_id}, User: {user_id}, "
                f"Action: {action}, Resource: {resource}, Result: {result}"
            )

        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")

    async def migrate_tenant_data(
        self, tenant_id: str, source_namespace: str, target_namespace: str
    ) -> dict[str, Any]:
        """Migrate tenant data between namespaces.

        Args:
            tenant_id: Tenant identifier
            source_namespace: Source namespace
            target_namespace: Target namespace

        Returns:
            Migration result
        """
        try:
            # In production, this would handle actual data migration
            # For now, we'll simulate the process

            migration_result = {
                "tenant_id": tenant_id,
                "source": source_namespace,
                "target": target_namespace,
                "status": "completed",
                "migrated_at": datetime.utcnow().isoformat(),
                "records_migrated": 0,
            }

            # Track migration in database
            from api.models import DataMigration

            migration = DataMigration(
                tenant_id=tenant_id,
                source_namespace=source_namespace,
                target_namespace=target_namespace,
                status="completed",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )

            self.db.add(migration)
            await self.db.commit()

            logger.info(f"Completed data migration for tenant: {tenant_id}")
            return migration_result

        except Exception as e:
            logger.error(f"Failed to migrate tenant data: {e}")
            await self.db.rollback()
            raise


class CrossTenantValidator:
    """Validates cross-tenant operations and sharing."""

    @staticmethod
    async def validate_sharing(
        source_tenant: str, target_tenant: str, resource_type: str, permissions: list[str]
    ) -> bool:
        """Validate cross-tenant sharing request.

        Args:
            source_tenant: Source tenant ID
            target_tenant: Target tenant ID
            resource_type: Type of resource
            permissions: Requested permissions

        Returns:
            True if sharing is allowed
        """
        # Define allowed sharing scenarios
        allowed_sharing = {"document": ["read", "comment"], "chat": ["read"], "dashboard": ["read"]}

        if resource_type not in allowed_sharing:
            return False

        allowed_perms = allowed_sharing[resource_type]
        for perm in permissions:
            if perm not in allowed_perms:
                return False

        # Additional validation could check tenant relationships
        # For now, allow all valid permission combinations
        return True

    @staticmethod
    async def create_sharing_link(
        tenant_id: str,
        resource_id: str,
        resource_type: str,
        permissions: list[str],
        expires_at: datetime | None = None,
    ) -> str:
        """Create secure sharing link for cross-tenant access.

        Args:
            tenant_id: Owner tenant ID
            resource_id: Resource to share
            resource_type: Type of resource
            permissions: Granted permissions
            expires_at: Link expiration

        Returns:
            Secure sharing token
        """
        import secrets

        from jose import jwt

        # Generate sharing token
        token_data = {
            "tenant_id": tenant_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "permissions": permissions,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "token_id": secrets.token_urlsafe(16),
        }

        # In production, use proper secret key
        secret_key = "your-secret-key"

        token = jwt.encode(token_data, secret_key, algorithm="HS256")

        return token
