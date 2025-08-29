"""Structured logging configuration."""

import logging
import sys
from typing import Any, Dict, Optional

import orjson
import structlog
from structlog.processors import CallsiteParameter

from chatbot_ai_system.config import settings


def setup_logging(
    level: Optional[str] = None,
    format: str = "json",
) -> None:
    """Configure structured logging."""
    log_level = level or settings.LOG_LEVEL
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                CallsiteParameter.FILENAME,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
            ]
        ),
    ]
    
    if format == "json":
        processors.append(structlog.processors.JSONRenderer(serializer=orjson.dumps))
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding temporary logging context."""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger, **kwargs):
        """Initialize log context."""
        self.logger = logger
        self.context = kwargs
        self.bound_logger = None
    
    def __enter__(self):
        """Enter context."""
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        if exc_type is not None:
            self.bound_logger.error(
                "Exception in context",
                exc_type=exc_type.__name__,
                exc_val=str(exc_val),
            )
        return False