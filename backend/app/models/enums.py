"""
Transit Platform — Centralized Domain Enums.

BUILD 1: All domain enumerated types are defined here.
Do not scatter magic strings through model code.
"""

import enum


class UserRole(str, enum.Enum):
    """Authenticated operator/admin roles. PASSENGER is not an MVP role."""

    DRIVER = "DRIVER"
    CONDUCTOR = "CONDUCTOR"
    FLEET_ADMIN = "FLEET_ADMIN"
    DEPOT_ADMIN = "DEPOT_ADMIN"
    PASSENGER = "PASSENGER"


class OrganizationType(str, enum.Enum):
    GOVERNMENT = "GOVERNMENT"
    PRIVATE = "PRIVATE"
    MUNICIPAL = "MUNICIPAL"
    OTHER = "OTHER"


class OrganizationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class DeviceStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class ServiceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class RouteStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class StopStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    INACTIVE = "INACTIVE"


class VehicleStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    DECOMMISSIONED = "DECOMMISSIONED"
    INACTIVE = "INACTIVE"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class TrackingSessionStatus(str, enum.Enum):
    READY = "READY"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    SYNCING = "SYNCING"
    ENDING = "ENDING"
    ENDED = "ENDED"


class CrowdingState(str, enum.Enum):
    """Categorical crowding states."""

    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    FULL = "FULL"


class CrowdingSource(str, enum.Enum):
    """Source of the crowding evidence."""

    OPERATOR = "OPERATOR"
    PASSENGER = "PASSENGER"
    HISTORICAL = "HISTORICAL"


class TripStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    SUSPECTED_START = "SUSPECTED_START"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"


class AssignmentStatus(str, enum.Enum):
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"


class Direction(str, enum.Enum):
    """A_TO_B = ascending sequence_number; B_TO_A = descending."""

    A_TO_B = "A_TO_B"
    B_TO_A = "B_TO_A"


class ValidationStatus(str, enum.Enum):
    VALID = "VALID"
    SUSPICIOUS = "SUSPICIOUS"
    REJECTED = "REJECTED"


class Confidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlertScope(str, enum.Enum):
    SERVICE = "SERVICE"
    ROUTE = "ROUTE"
    STOP = "STOP"
    TRIP = "TRIP"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
