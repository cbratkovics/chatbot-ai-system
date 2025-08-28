"""Authentication middleware and decorators."""

import logging
from functools import wraps

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .jwt_handler import jwt_handler
from .permissions import Permission, check_permission, expand_roles_to_permissions

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


class AuthMiddleware:
    """Authentication middleware for FastAPI."""

    def __init__(self, exclude_paths: list[str] = None):
        self.exclude_paths = exclude_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/ws/test",
        ]

    async def __call__(self, request: Request, call_next):
        """Process request through authentication."""
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            # No authentication provided
            request.state.user = None
            return await call_next(request)

        token = auth_header.replace("Bearer ", "")

        # Verify token
        payload = jwt_handler.verify_access_token(token)

        if not payload:
            # Invalid token
            request.state.user = None
        else:
            # Set user context
            request.state.user = {
                "user_id": payload.get("sub"),
                "tenant_id": payload.get("tenant_id"),
                "roles": payload.get("roles", []),
                "permissions": list(expand_roles_to_permissions(payload.get("roles", []))),
            }

            # Add explicit permissions if any
            if "permissions" in payload:
                request.state.user["permissions"].extend(payload["permissions"])

            logger.debug(f"Authenticated user: {request.state.user['user_id']}")

        response = await call_next(request)
        return response


def require_auth(permissions: list[Permission] | None = None, any_permission: bool = False):
    """Decorator to require authentication and optionally check permissions."""

    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Check if user is authenticated
            if not hasattr(request.state, "user") or not request.state.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check permissions if specified
            if permissions:
                user_permissions = request.state.user.get("permissions", [])

                if any_permission:
                    # User needs at least one of the permissions
                    has_permission = any(
                        check_permission(user_permissions, perm) for perm in permissions
                    )
                else:
                    # User needs all permissions
                    has_permission = all(
                        check_permission(user_permissions, perm) for perm in permissions
                    )

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
                    )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


async def get_current_user(credentials: HTTPAuthorizationCredentials = security):
    """Get current user from JWT token."""
    token = credentials.credentials
    payload = jwt_handler.verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": payload.get("sub"),
        "tenant_id": payload.get("tenant_id"),
        "roles": payload.get("roles", []),
        "permissions": list(expand_roles_to_permissions(payload.get("roles", []))),
    }


def require_permission(permission: Permission):
    """Dependency to require specific permission."""

    async def permission_checker(current_user: dict = get_current_user):
        user_permissions = current_user.get("permissions", [])

        if not check_permission(user_permissions, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required",
            )

        return current_user

    return permission_checker
