"""
Transit Platform — BusCurrentState & ETAPrediction Models.

BUILD 1: Schema only. No state engine or ETA algorithm.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import Confidence, Direction


class BusCurrentState(Base):
    """
    Persisted current interpreted state — one row per vehicle.
    vehicle_id is the PRIMARY KEY enforcing single-state uniqueness.
    BUILD 1 creates schema only. No state engine populates this.
    """

    __tablename__ = "bus_current_state"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id"),
        primary_key=True,
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=True, index=True
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=True
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=True
    )
    direction: Mapped[Direction | None] = mapped_column(
        Enum(Direction, name="direction", create_constraint=False),
        nullable=True,
    )

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)

    route_progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stops.id"), nullable=True
    )
    next_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stops.id"), nullable=True
    )
    dwell_state: Mapped[str | None] = mapped_column(String(30), nullable=True)

    state: Mapped[str] = mapped_column(String(30), nullable=False)
    state_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[Confidence | None] = mapped_column(
        Enum(Confidence, name="confidence", create_constraint=False),
        nullable=True,
    )

    canonical_source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    last_observed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_received_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    vehicle = relationship("Vehicle", back_populates="bus_current_state", lazy="select")
    trip = relationship("Trip", foreign_keys=[trip_id], lazy="select")
    service = relationship("Service", foreign_keys=[service_id], lazy="select")
    route = relationship("Route", foreign_keys=[route_id], lazy="select")
    current_stop = relationship("Stop", foreign_keys=[current_stop_id], lazy="select")
    next_stop = relationship("Stop", foreign_keys=[next_stop_id], lazy="select")

    def __repr__(self) -> str:
        return f"<BusCurrentState vehicle={self.vehicle_id} state={self.state}>"


class ETAPrediction(Base):
    """
    Historical ETA predictions. Multiple per trip+stop allowed.
    No ETA engine in BUILD 1.
    """

    __tablename__ = "eta_predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False
    )
    stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stops.id"), nullable=False
    )
    predicted_arrival_at: Mapped[datetime] = mapped_column(nullable=False)
    predicted_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Confidence] = mapped_column(
        Enum(Confidence, name="confidence", create_constraint=False),
        nullable=False,
    )
    computed_at: Mapped[datetime] = mapped_column(nullable=False)
    based_on_observed_at: Mapped[datetime] = mapped_column(nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # ── Relationships ────────────────────────────────────────────────
    trip = relationship("Trip", back_populates="eta_predictions", lazy="select")
    stop = relationship("Stop", foreign_keys=[stop_id], lazy="select")

    __table_args__ = (
        Index(
            "ix_eta_predictions_trip_stop_computed",
            "trip_id",
            "stop_id",
            "computed_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ETAPrediction trip={self.trip_id} stop={self.stop_id} "
            f"minutes={self.predicted_minutes}>"
        )
