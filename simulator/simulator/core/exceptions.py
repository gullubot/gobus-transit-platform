"""
Transit Platform — Simulator Exceptions.

Hierarchical exception types for clean error handling across the simulator client.
"""

from typing import Any, Optional


class SimulatorError(Exception):
    """Base exception for all simulator errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class BackendUnavailableError(SimulatorError):
    """Raised when the GoBus backend cannot be reached or times out."""
    pass


class AuthenticationError(SimulatorError):
    """Raised on HTTP 401: Invalid credentials or missing token."""
    pass


class AccountForbiddenError(SimulatorError):
    """Raised on HTTP 403: Role not authorized, user inactive, or cross-tenant access."""
    pass


class AssignmentNotFoundError(SimulatorError):
    """Raised on HTTP 404: No active or upcoming trip duty assignment found."""
    pass


class TripSessionError(SimulatorError):
    """Raised on HTTP 400/403/404 during trip start or end operations."""
    pass


class TelemetryBatchError(SimulatorError):
    """Raised when telemetry upload fails or packets are rejected."""
    pass


class RateLimitExceededError(SimulatorError):
    """Raised on HTTP 429: API rate limit exceeded (e.g. crowding reports)."""
    pass


class InvalidPayloadError(SimulatorError):
    """Raised on HTTP 422: Unprocessable entity / validation error."""
    pass
