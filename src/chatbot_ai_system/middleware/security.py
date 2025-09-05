"""
Security middleware for request validation, sanitization, and protection.
"""

import hashlib
import hmac
import logging
import re
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import bleach
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Security constants
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_URL_LENGTH = 2048
MAX_HEADER_SIZE = 8192
ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "text/plain",
}

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # seconds
DEFAULT_RATE_LIMIT = 100  # requests per window
BURST_RATE_LIMIT = 20  # burst allowance

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    r"(\bUNION\b.*\bSELECT\b)",
    r"(\bDROP\b.*\bTABLE\b)",
    r"(\bINSERT\b.*\bINTO\b)",
    r"(\bDELETE\b.*\bFROM\b)",
    r"(\bUPDATE\b.*\bSET\b)",
    r"(--|\#|\/\*|\*\/)",
    r"(\bOR\b.*=.*)",
    r"(\bAND\b.*=.*)",
    r"(\'|\"|;|\\x00|\\n|\\r|\\x1a)",
]

# XSS patterns
XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
    r"<embed[^>]*>",
    r"<object[^>]*>",
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.",
    r"%2e%2e/",
    r"%252e%252e/",
]


class RateLimiter:
    """Token bucket rate limiter with per-IP tracking."""

    def __init__(self, requests_per_minute: int = 60, burst_size: int = 20):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.buckets: Dict[str, Dict[str, Any]] = defaultdict(self._create_bucket)
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = datetime.now()

    def _create_bucket(self) -> Dict[str, Any]:
        """Create a new token bucket."""
        return {"tokens": self.burst_size, "last_refill": datetime.now(), "request_count": 0}

    def _refill_bucket(self, bucket: Dict[str, Any]) -> None:
        """Refill tokens based on time elapsed."""
        now = datetime.now()
        time_passed = (now - bucket["last_refill"]).total_seconds()
        tokens_to_add = (time_passed / 60) * self.requests_per_minute

        bucket["tokens"] = min(bucket["tokens"] + tokens_to_add, self.burst_size)
        bucket["last_refill"] = now

    def _cleanup_old_buckets(self) -> None:
        """Remove old buckets to prevent memory leaks."""
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() < self.cleanup_interval:
            return

        cutoff = now - timedelta(hours=1)
        to_remove = [key for key, bucket in self.buckets.items() if bucket["last_refill"] < cutoff]

        for key in to_remove:
            del self.buckets[key]

        self.last_cleanup = now

    def check_rate_limit(self, identifier: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.

        Returns:
            Tuple of (allowed, info_dict)
        """
        self._cleanup_old_buckets()

        bucket = self.buckets[identifier]
        self._refill_bucket(bucket)

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            bucket["request_count"] += 1
            return True, {
                "limit": self.requests_per_minute,
                "remaining": int(bucket["tokens"]),
                "reset": bucket["last_refill"] + timedelta(minutes=1),
            }

        return False, {
            "limit": self.requests_per_minute,
            "remaining": 0,
            "reset": bucket["last_refill"] + timedelta(minutes=1),
            "retry_after": 60 - (datetime.now() - bucket["last_refill"]).total_seconds(),
        }


class InputSanitizer:
    """Sanitize and validate input to prevent injection attacks."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize a string value."""
        if not value:
            return value

        # Truncate to max length
        value = value[:max_length]

        # Remove null bytes
        value = value.replace("\x00", "")

        # Strip control characters except newlines and tabs
        value = "".join(
            char
            for char in value
            if char == "\n" or char == "\t" or not char.isspace() or char == " "
        )

        # HTML entity encoding for special characters
        value = bleach.clean(value, tags=[], strip=True)

        return value

    @staticmethod
    def check_sql_injection(value: str) -> bool:
        """Check for potential SQL injection patterns."""
        if not value:
            return False

        value_lower = value.lower()
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def check_xss(value: str) -> bool:
        """Check for potential XSS patterns."""
        if not value:
            return False

        for pattern in XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def check_path_traversal(value: str) -> bool:
        """Check for path traversal attempts."""
        if not value:
            return False

        for pattern in PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def sanitize_dict(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """Recursively sanitize dictionary values."""
        if max_depth <= 0:
            raise ValueError("Maximum recursion depth exceeded")

        sanitized: Dict[str, Any] = {}
        for key, value in data.items():
            # Sanitize key
            if not isinstance(key, str) or len(key) > 100:
                continue

            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[key] = InputSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = InputSanitizer.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                sanitized[key] = [
                    InputSanitizer.sanitize_string(item) if isinstance(item, str) else item
                    for item in value[:100]  # Limit list size
                ]
            elif isinstance(value, (int, float, bool, type(None))):
                sanitized[key] = value

        return sanitized


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware."""

    def __init__(
        self,
        app,
        rate_limiter: Optional[RateLimiter] = None,
        enable_cors: bool = True,
        enable_csrf: bool = False,
        trusted_hosts: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.enable_cors = enable_cors
        self.enable_csrf = enable_csrf
        self.trusted_hosts = set(trusted_hosts) if trusted_hosts else None
        self.sanitizer = InputSanitizer()

    async def dispatch(self, request: Request, call_next):
        """Process request through security checks."""
        try:
            # 1. Check request size
            if request.headers.get("content-length"):
                if int(request.headers["content-length"]) > MAX_REQUEST_SIZE:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"error": "Request too large"},
                    )

            # 2. Validate host header
            if self.trusted_hosts and request.headers.get("host"):
                if request.headers["host"] not in self.trusted_hosts:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"error": "Invalid host header"},
                    )

            # 3. Check URL length
            if len(str(request.url)) > MAX_URL_LENGTH:
                return JSONResponse(
                    status_code=status.HTTP_414_REQUEST_URI_TOO_LONG,
                    content={"error": "URL too long"},
                )

            # 4. Rate limiting
            client_ip = request.client.host if request.client else "unknown"
            allowed, rate_info = self.rate_limiter.check_rate_limit(client_ip)

            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"error": "Rate limit exceeded", **rate_info},
                    headers={
                        "X-RateLimit-Limit": str(rate_info["limit"]),
                        "X-RateLimit-Remaining": str(rate_info["remaining"]),
                        "X-RateLimit-Reset": rate_info["reset"].isoformat(),
                        "Retry-After": str(int(rate_info.get("retry_after", 60))),
                    },
                )

            # 5. Check for common attack patterns in URL
            url_path = str(request.url.path)
            if self.sanitizer.check_path_traversal(url_path):
                logger.warning(f"Path traversal attempt from {client_ip}: {url_path}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Invalid request path"},
                )

            # 6. Validate content type
            content_type = request.headers.get("content-type", "").split(";")[0].strip()
            if request.method in ["POST", "PUT", "PATCH"]:
                if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                    return JSONResponse(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        content={"error": f"Unsupported content type: {content_type}"},
                    )

            # 7. Add security headers to request for processing
            request.state.client_ip = client_ip
            request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

            # Process request
            response = await call_next(request)

            # 8. Add security headers to response
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' ws: wss:;"
            )

            # Add HSTS for HTTPS connections
            if request.url.scheme == "https":
                response.headers[
                    "Strict-Transport-Security"
                ] = "max-age=63072000; includeSubDomains; preload"

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
            response.headers["X-RateLimit-Reset"] = rate_info["reset"].isoformat()

            # Add request ID for tracing
            response.headers["X-Request-ID"] = request.state.request_id

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal server error"},
            )


class APIKeyValidator:
    """API key validation for authentication."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.api_keys: Dict[str, Dict[str, Any]] = {}

    def generate_api_key(self, user_id: str, scopes: List[str] | None = None) -> str:
        """Generate a new API key for a user."""
        # Generate random key
        key_id = secrets.token_urlsafe(24)
        key_secret = secrets.token_urlsafe(32)

        # Create signature
        signature = hmac.new(
            self.secret_key.encode(), f"{key_id}.{key_secret}".encode(), hashlib.sha256
        ).hexdigest()

        # Store key metadata
        self.api_keys[key_id] = {
            "user_id": user_id,
            "secret_hash": hashlib.sha256(key_secret.encode()).hexdigest(),
            "scopes": scopes or [],
            "created_at": datetime.now(),
            "last_used": None,
            "request_count": 0,
        }

        # Return formatted key
        return f"sk-{key_id}.{key_secret}.{signature[:8]}"

    def validate_api_key(self, api_key: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Validate an API key."""
        if not api_key or not api_key.startswith("sk-"):
            return False, None

        try:
            # Parse key
            parts = api_key[3:].split(".")
            if len(parts) != 3:
                return False, None

            key_id, key_secret, signature = parts

            # Check if key exists
            if key_id not in self.api_keys:
                return False, None

            # Verify secret
            key_data = self.api_keys[key_id]
            secret_hash = hashlib.sha256(key_secret.encode()).hexdigest()
            if secret_hash != key_data["secret_hash"]:
                return False, None

            # Update usage stats
            key_data["last_used"] = datetime.now()
            key_data["request_count"] += 1

            return True, key_data

        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return False, None

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id in self.api_keys:
            del self.api_keys[key_id]
            return True
        return False


# Create global instances
rate_limiter = RateLimiter()
input_sanitizer = InputSanitizer()
