"""
Transit Platform — TrackingSession & TrackingEvent Models.

BUILD 1: Immutable observation schema.
- packet_id is UUID and UNIQUE.
- device_sequence uniqueness scoped by (device_id, tracking_session_id).
- observed_at = device observation time; received_at = server receipt time.
- No tracking ingestion or session authentication logic.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import TrackingSessionStatus, ValidationStatus


class TrackingSession(Base):
    __tablename__ = "tracking_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True
    )
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[TrackingSessionStatus] = mapped_column(
        Enum(
            TrackingSessionStatus,
            name="trackingsessionstatus",
            create_constraint=False,
        ),
        nullable=False,
        default=TrackingSessionStatus.READY,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    device = relationship("Device", back_populates="tracking_sessions", lazy="select")
    operator = relationship("User", foreign_keys=[operator_id], lazy="select")
    trip = relationship("Trip", back_populates="tracking_sessions", lazy="select")
    tracking_events = relationship(
        "TrackingEvent", back_populates="tracking_session", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<TrackingSession {self.id} device={self.device_id} status={self.status}>"


class TrackingEvent(Base):
    """
    Immutable telemetry observation.

    Telemetry fields (lat, lon, observed_at, etc.) must NOT be updated
    after creation. validation_status may be updated by future intelligence.
    """

    __tablename__ = "tracking_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # packet_id is UUID and globally unique
    packet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    tracking_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracking_sessions.id"),
        nullable=False,
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=True, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True
    )
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # ── Telemetry (immutable after creation) ─────────────────────────
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)

    observed_at: Mapped[datetime] = mapped_column(nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False)

    device_sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Device context ───────────────────────────────────────────────
    battery_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    network_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gps_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(
            ValidationStatus,
            name="validationstatus",
            create_constraint=False,
        ),
        nullable=False,
        default=ValidationStatus.VALID,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ────────────────────────────────────────────────
    tracking_session = relationship(
        "TrackingSession", back_populates="tracking_events", lazy="select"
    )
    trip = relationship("Trip", foreign_keys=[trip_id], lazy="select")
    device = relationship("Device", foreign_keys=[device_id], lazy="select")
    operator = relationship("User", foreign_keys=[operator_id], lazy="select")

    __table_args__ = (
        # Device sequence uniqueness scoped by device + session
        UniqueConstraint(
            "device_id",
            "tracking_session_id",
            "device_sequence",
            name="uq_tracking_events_device_session_seq",
        ),
        Index("ix_tracking_events_observed_at", "observed_at"),
        Index("ix_tracking_events_trip_observed", "trip_id", "observed_at"),
        Index(
            "ix_tracking_events_session",
            "tracking_session_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TrackingEvent packet={self.packet_id} "
            f"device={self.device_id} seq={self.device_sequence}>"
        )
