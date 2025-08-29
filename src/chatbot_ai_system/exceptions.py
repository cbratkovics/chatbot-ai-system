"""Custom exceptions for AI Chatbot System."""

from typing import Optional, Dict, Any


class ChatbotException(Exception):
    """Base exception for AI Chatbot System."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "INTERNAL_ERROR"
        self.status_code = status_code
        self.details = details or {}


class ProviderException(ChatbotException):
    """Provider-related exception."""
    
    def __init__(self, message: str, provider: str, **kwargs):
        super().__init__(message, error_code="PROVIDER_ERROR", status_code=503, **kwargs)
        self.provider = provider
        self.details["provider"] = provider


class RateLimitException(ChatbotException):
    """Rate limit exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", status_code=429, **kwargs)


class AuthenticationException(ChatbotException):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(message, error_code="AUTHENTICATION_REQUIRED", status_code=401, **kwargs)


class ValidationException(ChatbotException):
    """Validation error."""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="VALIDATION_ERROR", status_code=400, **kwargs)
        if field:
            self.details["field"] = field


__all__ = [
    "ChatbotException",
    "ProviderException",
    "RateLimitException",
    "AuthenticationException",
    "ValidationException",
]