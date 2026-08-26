"""
Transit Platform — Operator Schemas.

BUILD 2: Duty assignment and manual trip tracking activation schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
