"""Unit tests for tenant manager."""

from datetime import datetime, timedelta

import pytest


class TestTenantManager:
    """Test suite for tenant management."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self, mock_database):
        """Test tenant manager initialization."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)
        assert manager.db == mock_database
        assert manager.tenants_cache is not None

    @pytest.mark.asyncio
    async def test_tenant_creation(self, mock_database, tenant_config):
        """Test creating new tenant."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)
        tenant = await manager.create_tenant(tenant_config)

        assert tenant["tenant_id"] == tenant_config["tenant_id"]
        assert tenant["status"] == "active"
        mock_database.add.assert_called()
        mock_database.commit.assert_called()

    @pytest.mark.asyncio
    async def test_tenant_retrieval(self, mock_database, tenant_config):
        """Test retrieving tenant by ID."""
        from api.core.tenancy.tenant_manager import TenantManager

        mock_database.execute.return_value.scalar_one_or_none.return_value = tenant_config

        manager = TenantManager(db=mock_database)
        tenant = await manager.get_tenant(tenant_config["tenant_id"])

        assert tenant == tenant_config
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_tenant_update(self, mock_database, tenant_config):
        """Test updating tenant configuration."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        updates = {"tier": "premium", "status": "active"}
        updated = await manager.update_tenant(tenant_config["tenant_id"], updates)

        assert updated["tier"] == "premium"
        mock_database.commit.assert_called()

    @pytest.mark.asyncio
    async def test_tenant_deletion(self, mock_database):
        """Test tenant deletion."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)
        result = await manager.delete_tenant("tenant123")

        assert result is True
        mock_database.execute.assert_called()
        mock_database.commit.assert_called()

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, mock_database):
        """Test tenant data isolation."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        tenant1_data = await manager.get_tenant_data("tenant1", "chats")
        tenant2_data = await manager.get_tenant_data("tenant2", "chats")

        assert mock_database.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_tenant_quota_enforcement(self, mock_database, tenant_config):
        """Test tenant quota enforcement."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        quota_check = await manager.check_quota(
            tenant_config["tenant_id"], resource="tokens", requested=10000
        )

        assert quota_check["allowed"] is True
        assert quota_check["remaining"] > 0

    @pytest.mark.asyncio
    async def test_tenant_feature_flags(self, mock_database, tenant_config):
        """Test tenant feature flag management."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        has_feature = await manager.has_feature(tenant_config["tenant_id"], "semantic_cache")

        assert has_feature is True

    @pytest.mark.asyncio
    async def test_tenant_usage_tracking(self, mock_database):
        """Test tenant usage tracking."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        await manager.track_usage(tenant_id="tenant123", resource="api_calls", amount=1)

        mock_database.execute.assert_called()
        mock_database.commit.assert_called()

    @pytest.mark.asyncio
    async def test_tenant_billing_calculation(self, mock_database):
        """Test tenant billing calculation."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        billing = await manager.calculate_billing(
            tenant_id="tenant123",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        assert "total_cost" in billing
        assert "usage_breakdown" in billing

    @pytest.mark.asyncio
    async def test_tenant_migration(self, mock_database):
        """Test tenant migration between tiers."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        result = await manager.migrate_tenant(
            tenant_id="tenant123", from_tier="basic", to_tier="enterprise"
        )

        assert result["success"] is True
        mock_database.commit.assert_called()

    @pytest.mark.asyncio
    async def test_multi_tenant_query_filtering(self, mock_database):
        """Test multi-tenant query filtering."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        query = manager.apply_tenant_filter(base_query="SELECT * FROM chats", tenant_id="tenant123")

        assert "tenant_id" in query
        assert "tenant123" in query

    @pytest.mark.asyncio
    async def test_tenant_backup(self, mock_database):
        """Test tenant data backup."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        backup = await manager.backup_tenant_data("tenant123")

        assert backup["tenant_id"] == "tenant123"
        assert "timestamp" in backup
        assert "data" in backup

    @pytest.mark.asyncio
    async def test_tenant_restore(self, mock_database):
        """Test tenant data restoration."""
        from api.core.tenancy.tenant_manager import TenantManager

        manager = TenantManager(db=mock_database)

        backup_data = {
            "tenant_id": "tenant123",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"chats": [], "settings": {}},
        }

        result = await manager.restore_tenant_data(backup_data)

        assert result["success"] is True
        mock_database.commit.assert_called()
