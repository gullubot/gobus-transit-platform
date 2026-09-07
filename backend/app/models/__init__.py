"""
Transit Platform — SQLAlchemy Domain Models.

BUILD 1: All domain models and centralized enums.
Import all models here so that Alembic and other consumers
can discover them through a single import.
"""

# ── Enums ────────────────────────────────────────────────────────────
from app.models.alert import ServiceAlert  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.crowding import CrowdingReport  # noqa: F401
from app.models.device import Device  # noqa: F401
from app.models.enums import (  # noqa: F401
    AlertScope,
    AssignmentStatus,
    Confidence,
    DeviceStatus,
    Direction,
    OrganizationStatus,
    OrganizationType,
    RouteStatus,
    ServiceStatus,
    StopStatus,
    TrackingSessionStatus,
    TripStatus,
    UserRole,
    ValidationStatus,
    VehicleStatus,
    VerificationStatus,
)

# ── Models ───────────────────────────────────────────────────────────
from app.models.historical import HistoricalRouteTravel, HistoricalSegmentTravel  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.route import Route, RouteStop, Stop  # noqa: F401
from app.models.service import DepotSchedule, Service, ServiceSchedule  # noqa: F401
from app.models.state import BusCurrentState, ETAPrediction  # noqa: F401
from app.models.tracking import TrackingEvent, TrackingSession  # noqa: F401
from app.models.trip import Trip, TripAssignment, TripStateHistory  # noqa: F401
from app.models.user import OperatorProfile, User  # noqa: F401
from app.models.vehicle import Vehicle  # noqa: F401
from app.models.fare import FareConfiguration, FareSlab  # noqa: F401
from app.models.service_vehicle import ServiceVehicle  # noqa: F401
