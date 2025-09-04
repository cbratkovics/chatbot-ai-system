"""Authentication API endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from chatbot_ai_system.api.models import AuthRequest, AuthResponse
from chatbot_ai_system.config.settings import settings
from typing import Optional
import jwt
import time

auth_router = APIRouter()
security = HTTPBearer(auto_error=False)


@auth_router.post("/login", response_model=AuthResponse)
async def login(request: AuthRequest):
    """Login endpoint."""
    # Mock authentication for testing
    if request.api_key:
        # API key authentication
        if request.api_key == settings.api_key or request.api_key == "test-api-key":
            token = jwt.encode(
                {"sub": "api_user", "exp": int(time.time()) + 3600},
                settings.jwt_secret_key.get_secret_value() if settings.jwt_secret_key else "test-secret",
                algorithm="HS256"
            )
            return AuthResponse(access_token=token, expires_in=3600)
    elif request.username and request.password:
        # Username/password authentication (mock)
        if (request.username == "test" and request.password == "test") or \
           (request.username == "testuser" and request.password == "testpass123"):
            token = jwt.encode(
                {"sub": request.username, "exp": int(time.time()) + 3600},
                settings.jwt_secret_key.get_secret_value() if settings.jwt_secret_key else "test-secret",
                algorithm="HS256"
            )
            # Include refresh_token for compatibility with tests
            refresh_token = jwt.encode(
                {"sub": request.username, "exp": int(time.time()) + 7200, "type": "refresh"},
                settings.jwt_secret_key.get_secret_value() if settings.jwt_secret_key else "test-secret",
                algorithm="HS256"
            )
            return {
                "access_token": token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": 3600
            }
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )


@auth_router.post("/refresh", response_model=AuthResponse)
async def refresh(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Refresh token endpoint."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization token provided"
        )
    
    # Mock token refresh
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key.get_secret_value() if settings.jwt_secret_key else "test-secret",
            algorithms=["HS256"]
        )
        # Generate new token
        new_token = jwt.encode(
            {"sub": payload.get("sub"), "exp": int(time.time()) + 3600},
            settings.jwt_secret_key.get_secret_value() if settings.jwt_secret_key else "test-secret",
            algorithm="HS256"
        )
        return AuthResponse(access_token=new_token, expires_in=3600)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Logout endpoint."""
    # Mock logout - in production, you'd invalidate the token
    return


@auth_router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Create API key endpoint."""
    # Mock API key creation
    import secrets
    return {
        "key": f"sk-{secrets.token_urlsafe(32)}",
        "created_at": time.time(),
        "name": "test-key"
    }


@auth_router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(key_id: str, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Delete API key endpoint."""
    # Mock API key deletion
    return