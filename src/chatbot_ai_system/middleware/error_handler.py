"""Global error handling middleware for comprehensive error management."""

import logging
import time
import traceback
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class GlobalErrorHandler:
    """
    Global error handler for consistent error responses and logging.

    Features:
    - Structured error responses
    - Request correlation tracking
    - Error classification and logging
    - Performance impact tracking
    - Security-aware error disclosure
    """

    @staticmethod
    async def handle_generic_error(request: Request, exc: Exception) -> JSONResponse:
        """Handle generic unhandled exceptions."""

        correlation_id = getattr(request.state, "correlation_id", "unknown")
        tenant_id = getattr(request.state, "tenant_id", "unknown")

        # Log the full error for debugging
        logger.error(
            f"Unhandled exception in request {correlation_id} (tenant: {tenant_id}): "
            f"{type(exc).__name__}: {str(exc)}",
            extra={
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "request_path": request.url.path,
                "request_method": request.method,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )

        # Determine if this is a production environment
        is_production = not getattr(request.app.state, "debug", True)

        # Create error response
        error_response = {
            "error": "Internal server error",
            "message": "An unexpected error occurred while processing your request.",
            "correlation_id": correlation_id,
            "timestamp": time.time(),
            "status_code": 500,
        }

        # Add debug information in non-production environments
        if not is_production:
            error_response.update(
                {
                    "debug": {
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "request_path": request.url.path,
                        "request_method": request.method,
                    }
                }
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response,
            headers={"x-correlation-id": correlation_id, "x-error-type": "internal_server_error"},
        )

    @staticmethod
    async def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        """Handle Pydantic validation errors."""

        correlation_id = getattr(request.state, "correlation_id", "unknown")
        tenant_id = getattr(request.state, "tenant_id", "unknown")

        logger.warning(
            f"Validation error in request {correlation_id} (tenant: {tenant_id}): {str(exc)}",
            extra={
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "request_path": request.url.path,
                "validation_errors": exc.errors(),
            },
        )

        # Format validation errors for user-friendly response
        formatted_errors = []
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error["loc"])
            formatted_errors.append(
                {
                    "field": field_path,
                    "message": error["msg"],
                    "type": error["type"],
                    "input": error.get("input"),
                }
            )

        error_response = {
            "error": "Validation error",
            "message": "The request data is invalid. Please check the required fields and formats.",
            "validation_errors": formatted_errors,
            "correlation_id": correlation_id,
            "timestamp": time.time(),
            "status_code": 422,
        }

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response,
            headers={"x-correlation-id": correlation_id, "x-error-type": "validation_error"},
        )

    @staticmethod
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""

        correlation_id = getattr(request.state, "correlation_id", "unknown")
        tenant_id = getattr(request.state, "tenant_id", "unknown")

        # Log based on severity
        if exc.status_code >= 500:
            logger.error(
                f"HTTP {exc.status_code} error in request {correlation_id}: {exc.detail}",
                extra={
                    "correlation_id": correlation_id,
                    "tenant_id": tenant_id,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
        elif exc.status_code >= 400:
            logger.warning(
                f"HTTP {exc.status_code} error in request {correlation_id}: {exc.detail}",
                extra={
                    "correlation_id": correlation_id,
                    "tenant_id": tenant_id,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )

        # Map status codes to error types
        error_type_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            422: "unprocessable_entity",
            429: "rate_limit_exceeded",
            500: "internal_server_error",
            502: "bad_gateway",
            503: "service_unavailable",
            504: "gateway_timeout",
        }

        error_type = error_type_map.get(exc.status_code, "http_error")

        error_response = {
            "error": error_type.replace("_", " ").title(),
            "message": exc.detail,
            "correlation_id": correlation_id,
            "timestamp": time.time(),
            "status_code": exc.status_code,
        }

        # Add specific handling for certain error types
        if exc.status_code == 429:  # Rate limit
            error_response["retry_after"] = exc.headers.get("retry-after", 60)

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response,
            headers={"x-correlation-id": correlation_id, "x-error-type": error_type, **exc.headers},
        )

    @staticmethod
    async def handle_provider_error(
        request: Request, provider_name: str, error_message: str, error_code: str | None = None
    ) -> JSONResponse:
        """Handle AI provider-specific errors."""

        correlation_id = getattr(request.state, "correlation_id", "unknown")
        tenant_id = getattr(request.state, "tenant_id", "unknown")

        logger.error(
            f"Provider error from {provider_name} in request {correlation_id}: {error_message}",
            extra={
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "provider": provider_name,
                "provider_error_code": error_code,
                "error_message": error_message,
            },
        )

        # Map common provider errors to HTTP status codes
        status_mapping = {
            "rate_limit": 429,
            "quota_exceeded": 429,
            "invalid_api_key": 401,
            "model_not_found": 404,
            "content_filter": 400,
            "token_limit": 400,
            "server_error": 502,
            "timeout": 504,
        }

        status_code = status_mapping.get(error_code, 500)

        error_response = {
            "error": "Provider error",
            "message": f"The AI service encountered an error: {error_message}",
            "provider": provider_name,
            "provider_error_code": error_code,
            "correlation_id": correlation_id,
            "timestamp": time.time(),
            "status_code": status_code,
        }

        # Add retry guidance for recoverable errors
        if error_code in ["rate_limit", "quota_exceeded", "server_error", "timeout"]:
            error_response["retryable"] = True
            error_response["retry_after"] = 30  # Recommend 30 second retry
        else:
            error_response["retryable"] = False

        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers={
                "x-correlation-id": correlation_id,
                "x-error-type": "provider_error",
                "x-provider": provider_name,
            },
        )

    @staticmethod
    def create_error_response(
        error_type: str,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        correlation_id: str = "unknown",
    ) -> JSONResponse:
        """Create a standardized error response."""

        error_response = {
            "error": error_type,
            "message": message,
            "correlation_id": correlation_id,
            "timestamp": time.time(),
            "status_code": status_code,
        }

        if details:
            error_response.update(details)

        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers={
                "x-correlation-id": correlation_id,
                "x-error-type": error_type.lower().replace(" ", "_"),
            },
        )
