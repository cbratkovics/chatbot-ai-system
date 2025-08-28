"""Unit tests for authentication service."""

from datetime import datetime, timedelta

import jwt
import pytest


class TestAuthService:
    """Test suite for authentication service."""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test auth service initialization."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")
        assert service.secret_key == "test-secret"
        assert service.algorithm == "HS256"
        assert service.token_expiry_minutes == 60

    @pytest.mark.asyncio
    async def test_token_generation(self):
        """Test JWT token generation."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        payload = {"user_id": "user123", "tenant_id": "tenant456", "roles": ["user", "admin"]}

        token = service.generate_token(payload)
        assert token is not None
        assert isinstance(token, str)

        decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert decoded["user_id"] == "user123"
        assert decoded["tenant_id"] == "tenant456"

    @pytest.mark.asyncio
    async def test_token_validation(self):
        """Test JWT token validation."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        payload = {"user_id": "user123"}
        token = service.generate_token(payload)

        validated = service.validate_token(token)
        assert validated["valid"] is True
        assert validated["payload"]["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_expired_token_handling(self):
        """Test expired token handling."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        expired_payload = {"user_id": "user123", "exp": datetime.utcnow() - timedelta(hours=1)}

        expired_token = jwt.encode(expired_payload, "test-secret", algorithm="HS256")

        validated = service.validate_token(expired_token)
        assert validated["valid"] is False
        assert "expired" in validated["error"]

    @pytest.mark.asyncio
    async def test_invalid_token_handling(self):
        """Test invalid token handling."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        invalid_token = "invalid.token.here"

        validated = service.validate_token(invalid_token)
        assert validated["valid"] is False
        assert "invalid" in validated["error"].lower()

    @pytest.mark.asyncio
    async def test_api_key_generation(self):
        """Test API key generation."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        api_key = await service.generate_api_key(tenant_id="tenant123", name="Production API Key")

        assert api_key["key"] is not None
        assert len(api_key["key"]) >= 32
        assert api_key["tenant_id"] == "tenant123"

    @pytest.mark.asyncio
    async def test_api_key_validation(self, mock_database):
        """Test API key validation."""
        from api.core.auth.auth_service import AuthService

        mock_database.execute.return_value.scalar_one_or_none.return_value = {
            "key": "test-api-key",
            "tenant_id": "tenant123",
            "active": True,
        }

        service = AuthService(secret_key="test-secret", db=mock_database)

        valid = await service.validate_api_key("test-api-key")
        assert valid["valid"] is True
        assert valid["tenant_id"] == "tenant123"

    @pytest.mark.asyncio
    async def test_permission_checking(self):
        """Test permission checking."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        user_context = {
            "user_id": "user123",
            "roles": ["admin", "user"],
            "permissions": ["read", "write", "delete"],
        }

        assert service.has_permission(user_context, "read") is True
        assert service.has_permission(user_context, "execute") is False

    @pytest.mark.asyncio
    async def test_role_based_access(self):
        """Test role-based access control."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        user_context = {"user_id": "user123", "roles": ["admin"]}

        assert service.has_role(user_context, "admin") is True
        assert service.has_role(user_context, "superadmin") is False

    @pytest.mark.asyncio
    async def test_token_refresh(self):
        """Test token refresh mechanism."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        original_token = service.generate_token({"user_id": "user123"})

        refreshed = service.refresh_token(original_token)
        assert refreshed["success"] is True
        assert refreshed["token"] != original_token

        decoded = jwt.decode(refreshed["token"], "test-secret", algorithms=["HS256"])
        assert decoded["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_token_revocation(self, mock_redis):
        """Test token revocation."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret", redis_client=mock_redis)

        token = service.generate_token({"user_id": "user123"})

        await service.revoke_token(token)
        mock_redis.setex.assert_called()

        is_revoked = await service.is_token_revoked(token)
        assert is_revoked is True

    @pytest.mark.asyncio
    async def test_session_management(self, mock_redis):
        """Test session management."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret", redis_client=mock_redis)

        session_data = {"user_id": "user123", "tenant_id": "tenant456", "ip_address": "192.168.1.1"}

        session_id = await service.create_session(session_data)
        assert session_id is not None
        mock_redis.setex.assert_called()

        retrieved = await service.get_session(session_id)
        assert retrieved == session_data

    @pytest.mark.asyncio
    async def test_mfa_token_generation(self):
        """Test MFA token generation."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        mfa_token = service.generate_mfa_token(user_id="user123")
        assert len(mfa_token) == 6
        assert mfa_token.isdigit()

    @pytest.mark.asyncio
    async def test_mfa_verification(self, mock_redis):
        """Test MFA verification."""
        from api.core.auth.auth_service import AuthService

        mock_redis.get.return_value = "123456"

        service = AuthService(secret_key="test-secret", redis_client=mock_redis)

        verified = await service.verify_mfa_token(user_id="user123", token="123456")

        assert verified is True

    @pytest.mark.asyncio
    async def test_oauth_token_exchange(self):
        """Test OAuth token exchange."""
        from api.core.auth.auth_service import AuthService

        service = AuthService(secret_key="test-secret")

        oauth_token = "oauth-provider-token"

        exchanged = await service.exchange_oauth_token(provider="google", oauth_token=oauth_token)

        assert exchanged["success"] is True
        assert "access_token" in exchanged
        assert "refresh_token" in exchanged
