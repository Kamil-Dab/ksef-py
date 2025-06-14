"""Exception classes for ksef-py."""

from typing import Any, Optional


class KsefError(Exception):
    """Base exception for all KSeF-related errors."""

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = error_code

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class KsefAuthenticationError(KsefError):
    """Raised when authentication with KSeF API fails."""

    pass


class KsefValidationError(KsefError):
    """Raised when request validation fails."""

    pass


class KsefNetworkError(KsefError):
    """Raised when network-related errors occur."""

    pass


class KsefServerError(KsefError):
    """Raised when KSeF server returns an error."""

    pass


class KsefTimeoutError(KsefNetworkError):
    """Raised when requests timeout."""

    pass


class KsefRateLimitError(KsefError):
    """Raised when rate limits are exceeded."""

    pass
