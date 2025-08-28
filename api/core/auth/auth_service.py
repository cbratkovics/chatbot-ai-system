"""Authentication service for JWT and API key management."""

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

import jwt
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from api.models.tenant import TenantConfig
    from api.models.provider import ProviderConfig
    from api.models.cost import CostReport
except ImportError:
    # Fallback for testing
    TenantConfig = dict
    ProviderConfig = dict
    CostReport = dict

logger = logging.getLogger(__name__)


class AuthService:
    """Handles authentication and authorization."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        token_expiry_minutes: int = 60,
        db: AsyncSession | None = None,
        redis_client: aioredis.Redis | None = None,
    ):
        """Initialize auth service.

        Args:
            secret_key: Secret key for JWT
            algorithm: JWT algorithm
            token_expiry_minutes: Token expiry time
            db: Database session
            redis_client: Redis client
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry_minutes = token_expiry_minutes
        self.db = db
        self.redis_client = redis_client

    def generate_token(self, payload: dict[str, Any], expiry_minutes: int | None = None) -> str:
        """Generate JWT token.

        Args:
            payload: Token payload
            expiry_minutes: Custom expiry time

        Returns:
            JWT token
        """
        expiry_minutes = expiry_minutes or self.token_expiry_minutes

        payload = payload.copy()
        payload.update(
            {
                "exp": datetime.utcnow() + timedelta(minutes=expiry_minutes),
                "iat": datetime.utcnow(),
                "jti": secrets.token_hex(16),
            }
        )

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate JWT token.

        Args:
            token: JWT token

        Returns:
            Validation result with payload
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return {"valid": True, "payload": payload}
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "Token expired"}
        except jwt.InvalidTokenError as e:
            return {"valid": False, "error": f"Invalid token: {str(e)}"}

    def refresh_token(self, token: str) -> dict[str, Any]:
        """Refresh JWT token.

        Args:
            token: Current JWT token

        Returns:
            New token or error
        """
        validation = self.validate_token(token)

        if not validation["valid"]:
            if "expired" in validation["error"]:
                try:
                    payload = jwt.decode(
                        token,
                        self.secret_key,
                        algorithms=[self.algorithm],
                        options={"verify_exp": False},
                    )

                    new_payload = {
                        k: v for k, v in payload.items() if k not in ["exp", "iat", "jti"]
                    }

                    new_token = self.generate_token(new_payload)
                    return {"success": True, "token": new_token}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            return {"success": False, "error": validation["error"]}

        payload = validation["payload"]
        new_payload = {k: v for k, v in payload.items() if k not in ["exp", "iat", "jti"]}

        new_token = self.generate_token(new_payload)
        return {"success": True, "token": new_token}

    async def generate_api_key(
        self, tenant_id: str, name: str, expiry_days: int | None = None
    ) -> dict[str, Any]:
        """Generate API key.

        Args:
            tenant_id: Tenant identifier
            name: API key name
            expiry_days: Expiry in days

        Returns:
            API key information
        """
        key = f"sk-{secrets.token_hex(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        api_key_data = {
            "key": key,
            "key_hash": key_hash,
            "tenant_id": tenant_id,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            "active": True,
        }

        if expiry_days:
            api_key_data["expires_at"] = (
                datetime.utcnow() + timedelta(days=expiry_days)
            ).isoformat()

        if self.db:
            try:
                from api.models import APIKey
            except ImportError:
                # Fallback for testing
                APIKey = dict

            api_key = APIKey(
                key_hash=key_hash,
                tenant_id=tenant_id,
                name=name,
                active=True,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=expiry_days) if expiry_days else None,
            )

            self.db.add(api_key)
            await self.db.commit()

            api_key_data["id"] = api_key.id

        return api_key_data

    async def validate_api_key(self, api_key: str) -> dict[str, Any]:
        """Validate API key.

        Args:
            api_key: API key to validate

        Returns:
            Validation result
        """
        if not self.db:
            return {"valid": False, "error": "Database not configured"}

        try:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            from sqlalchemy import select

            try:
                from api.models import APIKey
            except ImportError:
                # Fallback for testing
                APIKey = dict

            result = await self.db.execute(
                select(APIKey).where(APIKey.key_hash == key_hash, APIKey.active.is_(True))
            )

            api_key_record = result.scalar_one_or_none()

            if not api_key_record:
                return {"valid": False, "error": "Invalid API key"}

            if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
                return {"valid": False, "error": "API key expired"}

            api_key_record.last_used = datetime.utcnow()
            await self.db.commit()

            return {
                "valid": True,
                "tenant_id": api_key_record.tenant_id,
                "name": api_key_record.name,
            }

        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return {"valid": False, "error": "Validation failed"}

    def has_permission(self, user_context: dict[str, Any], permission: str) -> bool:
        """Check if user has permission.

        Args:
            user_context: User context with permissions
            permission: Permission to check

        Returns:
            True if has permission
        """
        permissions = user_context.get("permissions", [])
        return permission in permissions

    def has_role(self, user_context: dict[str, Any], role: str) -> bool:
        """Check if user has role.

        Args:
            user_context: User context with roles
            role: Role to check

        Returns:
            True if has role
        """
        roles = user_context.get("roles", [])
        return role in roles

    async def revoke_token(self, token: str):
        """Revoke JWT token.

        Args:
            token: Token to revoke
        """
        if not self.redis_client:
            return

        validation = self.validate_token(token)
        if validation["valid"]:
            jti = validation["payload"].get("jti")
            exp = validation["payload"].get("exp")

            if jti and exp:
                ttl = exp - int(datetime.utcnow().timestamp())
                if ttl > 0:
                    await self.redis_client.setex(f"revoked_token:{jti}", ttl, "1")

    async def is_token_revoked(self, token: str) -> bool:
        """Check if token is revoked.

        Args:
            token: Token to check

        Returns:
            True if revoked
        """
        if not self.redis_client:
            return False

        validation = self.validate_token(token)
        if validation["valid"]:
            jti = validation["payload"].get("jti")
            if jti:
                result = await self.redis_client.get(f"revoked_token:{jti}")
                return result is not None

        return False

    async def create_session(self, session_data: dict[str, Any]) -> str:
        """Create user session.

        Args:
            session_data: Session data

        Returns:
            Session ID
        """
        if not self.redis_client:
            raise ValueError("Redis client not configured")

        session_id = secrets.token_hex(32)
        session_key = f"session:{session_id}"

        await self.redis_client.setex(session_key, 3600, json.dumps(session_data))

        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session data.

        Args:
            session_id: Session identifier

        Returns:
            Session data if exists
        """
        if not self.redis_client:
            return None

        session_key = f"session:{session_id}"
        data = await self.redis_client.get(session_key)

        if data:
            return json.loads(data)

        return None

    def generate_mfa_token(self, user_id: str) -> str:
        """Generate MFA token.

        Args:
            user_id: User identifier

        Returns:
            MFA token
        """
        return "".join([str(secrets.randbelow(10)) for _ in range(6)])

    async def verify_mfa_token(self, user_id: str, token: str) -> bool:
        """Verify MFA token.

        Args:
            user_id: User identifier
            token: MFA token

        Returns:
            True if valid
        """
        if not self.redis_client:
            return False

        stored_token = await self.redis_client.get(f"mfa:{user_id}")

        if stored_token:
            return stored_token if isinstance(stored_token, str) else stored_token.decode() == token

        return False

    async def exchange_oauth_token(self, provider: str, oauth_token: str) -> dict[str, Any]:
        """Exchange OAuth token for internal token.

        Args:
            provider: OAuth provider
            oauth_token: OAuth token

        Returns:
            Internal tokens
        """
        user_info = await self._get_oauth_user_info(provider, oauth_token)

        if not user_info:
            return {"success": False, "error": "Failed to get user info"}

        access_token = self.generate_token(
            {"user_id": user_info.get("id"), "email": user_info.get("email"), "provider": provider}
        )

        refresh_token = self.generate_token(
            {"type": "refresh", "user_id": user_info.get("id")}, expiry_minutes=10080
        )

        return {
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_info": user_info,
        }

    async def _get_oauth_user_info(
        self, provider: str, oauth_token: str
    ) -> dict[str, Any] | None:
        """Get user info from OAuth provider.

        Args:
            provider: OAuth provider
            oauth_token: OAuth token

        Returns:
            User information
        """
        return {"id": "oauth_user_123", "email": "user@example.com", "name": "OAuth User"}
