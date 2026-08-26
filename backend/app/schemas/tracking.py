"""
Transit Platform — Tracking Ingestion Schemas.

BUILD 2: Batch telemetry ingestion, packet-level ACK contract, and device heartbeat.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrackingPacketIn(BaseModel):
    """Single telemetry observation packet from mobile tracking device."""

    packet_id: uuid.UUID
    latitude: float = Field(..., description="Latitude in degrees")
    longitude: float = Field(..., description="Longitude in degrees")
    accuracy_m: float | None = Field(default=None, description="Accuracy in meters")
    speed_mps: float | None = Field(default=None, description="Speed in meters per second")
    heading: float | None = Field(default=None, description="Heading in degrees")
    observed_at: datetime = Field(..., description="Device timestamp when GPS was observed")
    device_sequence: int = Field(..., description="Monotonic sequence number within session")
    battery_level: float | None = Field(default=None, description="Battery percentage")
    network_type: str | None = Field(default=None, max_length=20)
    gps_status: str | None = Field(default=None, max_length=20)


class TrackingBatchRequest(BaseModel):
    """Batch of telemetry observation packets."""

    session_id: uuid.UUID | None = Field(
        default=None, description="Explicit tracking session ID if known"
    )
    packets: list[TrackingPacketIn] = Field(..., min_length=1, max_length=500)


class RejectedPacketDetail(BaseModel):
    """Detail for an unprocessable/invalid packet."""

    packet_id: uuid.UUID
    reason: str


class TrackingBatchResponse(BaseModel):
    """
    Packet-level acknowledgement contract.
    Client behavior:
    - accepted: remove from local Room queue
    - duplicates: remove from local Room queue (already processed)
    - retryable: retain in Room queue and retry later
    - rejected: retain diagnostic state or drop per policy
    """

    accepted: list[uuid.UUID] = Field(default_factory=list)
    duplicates: list[uuid.UUID] = Field(default_factory=list)
    retryable: list[uuid.UUID] = Field(default_factory=list)
    rejected: list[RejectedPacketDetail] = Field(default_factory=list)


class HeartbeatRequest(BaseModel):
    """Device and session health heartbeat."""

    session_id: uuid.UUID | None = None
    battery_level: float | None = Field(default=None, ge=0.0, le=100.0)
    network_type: str | None = Field(default=None, max_length=20)
    gps_status: str | None = Field(default=None, max_length=20)
    app_version: str | None = Field(default=None, max_length=50)
    timestamp: datetime | None = None


class HeartbeatResponse(BaseModel):
    """Heartbeat acknowledgement."""

    status: str = "ok"
    received_at: datetime
    device_status: str
    session_status: str | None = None

    model_config = ConfigDict(from_attributes=True)
