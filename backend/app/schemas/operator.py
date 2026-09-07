"""
Transit Platform — Operator Schemas.

BUILD 2: Duty assignment and manual trip tracking activation schemas.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertScope, AlertStatus, AlertSeverity


class AssignmentResponse(BaseModel):
    """Current or upcoming operator trip duty assignment."""

    assignment_id: uuid.UUID
    trip_id: uuid.UUID
    service_id: uuid.UUID
    service_code: str
    service_name: str
    route_id: uuid.UUID
    route_code: str
    route_name: str
    direction: str
    vehicle_id: uuid.UUID
    vehicle_number: str
    planned_start_at: datetime
    trip_status: str
    operator_role: str
    assignment_status: str
    assigned_device_id: uuid.UUID | None = None
    assigned_device_status: str | None = None
    active_tracking_session_id: uuid.UUID | None = None
    tracking_session_status: str | None = None

    # Enriched operational fields for Operator Mobile UI
    vehicle_registration: str | None = None
    vehicle_type: str | None = None
    origin_stop_name: str | None = None
    destination_stop_name: str | None = None
    route_distance_km: float | None = None

    model_config = ConfigDict(from_attributes=True)


class TripStartResponse(BaseModel):
    """Result of activating a tracking session for an assigned trip."""

    tracking_session_id: uuid.UUID
    trip_id: uuid.UUID
    device_id: uuid.UUID
    status: str
    started_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TripEndResponse(BaseModel):
    """Result of ending a tracking session for an assigned trip."""

    tracking_session_id: uuid.UUID
    trip_id: uuid.UUID
    status: str
    ended_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperatorTripResponse(BaseModel):
    """Operator duty trip representation for Today's Trips."""

    trip_id: uuid.UUID
    assignment_id: uuid.UUID
    service_code: str
    service_name: str
    route_code: str
    route_name: str
    direction: str
    vehicle_number: str
    vehicle_registration: str | None = None
    vehicle_type: str | None = None
    planned_start_at: datetime
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    trip_status: str
    assignment_status: str
    operator_role: str
    origin_stop_name: str | None = None
    destination_stop_name: str | None = None
    route_distance_km: float | None = None
    is_next: bool = False

    model_config = ConfigDict(from_attributes=True)


class OperatorIssueReportRequest(BaseModel):
    """Client payload for an operator reporting an issue on an assigned trip."""

    issue_type: str = Field(..., description="Type of issue e.g. BREAKDOWN, TRAFFIC_DELAY, ACCIDENT, MEDICAL_EMERGENCY, PASSENGER_INCIDENT, MECHANICAL_ISSUE, OTHER")
    message: str = Field(..., description="Concise operator description of the incident")
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING, description="Severity: INFO, WARNING, CRITICAL")


class OperatorIssueReportResponse(BaseModel):
    """Response returned upon reporting an issue."""

    alert_id: uuid.UUID
    trip_id: uuid.UUID
    service_id: Optional[uuid.UUID] = None
    route_id: Optional[uuid.UUID] = None
    scope: AlertScope
    status: AlertStatus
    type: str
    severity: AlertSeverity
    title: str
    message: str
    created_at: datetime
    created_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)

