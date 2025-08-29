"""Structured logging configuration with correlation IDs and PII redaction."""

import logging
import re
import sys
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

import orjson
import structlog
from structlog.processors import CallsiteParameter

from chatbot_ai_system.config import settings

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


class PIIRedactor:
    """Redact PII from log messages."""

    # Patterns for common PII
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
    API_KEY_PATTERN = re.compile(r"\b(sk-|pk-|api[_-]?key[\s=:]+)[\w-]{20,}\b", re.IGNORECASE)
    JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b")

    @classmethod
    def redact(cls, value: Any) -> Any:
        """Redact PII from value."""
        if not isinstance(value, str):
            return value

        # Redact patterns
        value = cls.EMAIL_PATTERN.sub("[EMAIL_REDACTED]", value)
        value = cls.PHONE_PATTERN.sub("[PHONE_REDACTED]", value)
        value = cls.SSN_PATTERN.sub("[SSN_REDACTED]", value)
        value = cls.CREDIT_CARD_PATTERN.sub("[CC_REDACTED]", value)
        value = cls.API_KEY_PATTERN.sub("[API_KEY_REDACTED]", value)
        value = cls.JWT_PATTERN.sub("[JWT_REDACTED]", value)

        return value


def add_context_vars(logger, method_name, event_dict):
    """Add context variables to log events."""
    if request_id := request_id_var.get():
        event_dict["request_id"] = request_id
    if tenant_id := tenant_id_var.get():
        event_dict["tenant_id"] = tenant_id
    if user_id := user_id_var.get():
        event_dict["user_id"] = user_id
    return event_dict


def redact_sensitive_data(logger, method_name, event_dict):
    """Redact sensitive data from logs."""
    # Redact event message
    if "event" in event_dict:
        event_dict["event"] = PIIRedactor.redact(event_dict["event"])

    # Redact other string values
    for key, value in event_dict.items():
        if key not in ["timestamp", "level", "logger", "request_id"]:
            if isinstance(value, str):
                event_dict[key] = PIIRedactor.redact(value)
            elif isinstance(value, dict):
                event_dict[key] = {k: PIIRedactor.redact(v) for k, v in value.items()}

    return event_dict


def setup_logging(
    level: str | None = None,
    format: str = "json",
    redact_pii: bool = True,
) -> None:
    """Configure structured logging with security features."""
    log_level = level or settings.LOG_LEVEL

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_context_vars,  # Add correlation IDs
    ]

    # Add PII redaction in production
    if redact_pii and settings.ENVIRONMENT == "production":
        processors.append(redact_sensitive_data)

    processors.extend(
        [
            structlog.processors.StackInfoRenderer(),
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                ]
            ),
            structlog.processors.ExceptionRenderer(),
        ]
    )

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

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


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


class RequestContext:
    """Context manager for request-scoped logging."""

    def __init__(
        self,
        request_id: str | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ):
        """Initialize request context."""
        self.request_id = request_id or str(uuid4())
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.tokens = []

    def __enter__(self):
        """Enter context."""
        self.tokens.append(request_id_var.set(self.request_id))
        if self.tenant_id:
            self.tokens.append(tenant_id_var.set(self.tenant_id))
        if self.user_id:
            self.tokens.append(user_id_var.set(self.user_id))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        for token in self.tokens:
            request_id_var.reset(token)
        return False


def audit_log(
    action: str,
    resource: str,
    result: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Create an audit log entry."""
    logger = get_logger("audit")
    logger.info(
        "audit_event",
        action=action,
        resource=resource,
        result=result,
        metadata=metadata or {},
        audit=True,  # Mark as audit log
    )
