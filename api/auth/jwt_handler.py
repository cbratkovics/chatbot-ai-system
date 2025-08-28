"""JWT token handling for authentication."""

import logging
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..app.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTHandler:
    """Handles JWT token creation and verification."""

    def __init__(
        self, secret_key: str = None, algorithm: str = None, access_token_expire_minutes: int = None
    ):
        self.secret_key = secret_key or settings.jwt_secret_key
        self.algorithm = algorithm or settings.jwt_algorithm
        self.access_token_expire_minutes = (
            access_token_expire_minutes or settings.jwt_access_token_expire_minutes
        )

    def create_access_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Create JWT access token."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)

        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        """Verify access token specifically."""
        payload = self.verify_token(token)

        if payload and payload.get("type") == "access":
            return payload

        return None

    def verify_refresh_token(self, token: str) -> dict[str, Any] | None:
        """Verify refresh token specifically."""
        payload = self.verify_token(token)

        if payload and payload.get("type") == "refresh":
            return payload

        return None

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storage."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)


# Global JWT handler instance
jwt_handler = JWTHandler()


def create_access_token(
    user_id: str, tenant_id: str, roles: list = None, permissions: list = None, **kwargs
) -> str:
    """Create access token with user data."""
    data = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or [],
        "permissions": permissions or [],
        **kwargs,
    }

    return jwt_handler.create_access_token(data)


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify token and return payload."""
    return jwt_handler.verify_access_token(token)
