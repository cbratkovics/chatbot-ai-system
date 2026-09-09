"""Structured error envelope shared by every route.

Every error the API returns has the shape::

    {"error": {"code": "...", "message": "...", "provider": "...", "request_id": "..."}}

Why: the frontend can only show what the backend sends, and a bare 500 with no CORS
headers is invisible to a browser. One envelope, one place to build it.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..providers.base import (
    AuthenticationError,
    ContentFilterError,
    ModelNotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError,
)

logger = logging.getLogger(__name__)


def error_payload(
    code: str,
    message: str,
    provider: Optional[str] = None,
    request_id: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build the envelope body."""
    body: Dict[str, Any] = {
        "code": code,
        "message": message,
        "provider": provider,
        "request_id": request_id,
    }
    body.update({k: v for k, v in extra.items() if v is not None})
    return {"error": body, "request_id": request_id}


def error_response(
    status_code: int,
    code: str,
    message: str,
    provider: Optional[str] = None,
    request_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    **extra: Any,
) -> JSONResponse:
    """Build a JSONResponse carrying the envelope."""
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code, message, provider, request_id, **extra),
        headers=headers,
    )


def classify_provider_error(exc: ProviderError) -> tuple[int, str]:
    """Map a provider exception to (HTTP status, error code).

    Order matters: subclasses first.
    """
    if isinstance(exc, AuthenticationError):
        return 401, "provider_auth_error"
    if isinstance(exc, QuotaExceededError):
        return 402, "provider_quota_exhausted"
    if isinstance(exc, RateLimitError):
        return 429, "provider_rate_limited"
    if isinstance(exc, TimeoutError):
        return 504, "provider_timeout"
    if isinstance(exc, ModelNotFoundError):
        return 404, "model_not_found"
    if isinstance(exc, ContentFilterError):
        return 422, "content_filtered"
    # Anything else the upstream did wrong is a bad gateway, never a bare 500.
    status = exc.status_code
    if status is not None and 400 <= status < 500:
        return 502, "provider_error"
    if status is not None and status >= 500:
        return 502, "provider_error"
    return 503, "provider_unavailable"


def provider_error_response(
    exc: ProviderError, request_id: str, **extra: Any
) -> JSONResponse:
    """Turn a provider exception into the envelope with the right status."""
    status_code, code = classify_provider_error(exc)
    headers: Dict[str, str] = {}
    retry_after = getattr(exc, "retry_after", None)
    if status_code == 429:
        headers["Retry-After"] = str(retry_after or 30)
    return error_response(
        status_code,
        code,
        exc.message,
        provider=exc.provider,
        request_id=request_id,
        headers=headers or None,
        **extra,
    )


class ErrorEnvelopeMiddleware:
    """Catch anything unhandled *inside* the CORS boundary.

    FastAPI's ``Exception`` handler runs in ServerErrorMiddleware, outside CORSMiddleware,
    so its 500 has no CORS headers and the browser cannot read it. This middleware is
    registered inside CORS, so the browser always gets a readable envelope.

    Pure ASGI on purpose: with Starlette ``BaseHTTPMiddleware`` layers in the stack, a
    streaming response on a reused keep-alive connection is closed by uvicorn's 5 s
    keep-alive timer mid-stream (reproduced with uvicorn 0.24 / Starlette 0.27; see
    ``tests/unit/test_keepalive_streaming.py``). Every middleware in this app is plain ASGI.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_tracking(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking)
        except Exception as exc:  # noqa: BLE001 - this is the last line of defence
            request_id = scope.get("state", {}).get("request_id")
            logger.error(
                "Unhandled error: %s", exc, extra={"request_id": request_id}, exc_info=True
            )
            if started:
                raise  # headers are on the wire; nothing readable can replace them
            response = error_response(
                500, "internal_error", "Internal server error", request_id=request_id
            )
            await response(scope, receive, send)
