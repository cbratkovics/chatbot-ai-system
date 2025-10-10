"""Error handling middleware."""

import time
import traceback
from collections.abc import Callable

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle exceptions globally."""
        try:
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response

        except ValidationError as exc:
            logger.error(
                "Validation error",
                path=request.url.path,
                errors=exc.errors(),
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": "Validation Error",
                    "details": exc.errors(),
                    "request_id": getattr(request.state, "request_id", None),
                },
            )

        except ValueError as exc:
            logger.error(
                "Value error",
                path=request.url.path,
                error=str(exc),
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Bad Request",
                    "message": str(exc),
                    "request_id": getattr(request.state, "request_id", None),
                },
            )

        except Exception as exc:
            logger.exception(
                "Unhandled exception",
                path=request.url.path,
                error=str(exc),
                traceback=traceback.format_exc(),
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "request_id": getattr(request.state, "request_id", None),
                },
            )
