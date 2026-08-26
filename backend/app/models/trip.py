"""
Transit Platform — Trip, TripAssignment, and TripStateHistory Models.

BUILD 1: Operational snapshot schema.
Trip records: SERVICE + VEHICLE + ROUTE + DIRECTION + OPERATING_DATE.

CRITICAL INTEGRITY RULES:
  1. trip.route_id must match service.route_id (composite FK enforced).
  2. trip.organization_id ensures vehicle/service belong to same org.
  3. expected_end_at does NOT auto-terminate an active trip.

organization_id is added to trips to enforce cross-org integrity via
composite FKs (per spec section 31: "If enforcing a relationship requires
composite organization-scoped keys, implement them cleanly and document
the reason").
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import AssignmentStatus, Direction, TripStatus


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # organization_id — denormalized for cross-org composite FK enforcement.
    # Must match the organization of service, vehicle, and route.
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, name="direction", create_constraint=False),
        nullable=False,
    )
    operating_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    planned_start_at: Mapped[datetime] = mapped_column(nullable=False)
    actual_start_at: Mapped[datetime | None] = mapped_column(nullable=True)
    actual_end_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expected_end_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus, name="tripstatus", create_constraint=False),
        nullable=False,
        default=TripStatus.PLANNED,
        index=True,
    )
    start_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    end_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    service = relationship(
        "Service",
        back_populates="trips",
        lazy="select",
        foreign_keys=[service_id],
        primaryjoin="Trip.service_id == Service.id",
    )
    vehicle = relationship(
        "Vehicle",
        back_populates="trips",
        lazy="select",
        foreign_keys=[vehicle_id],
        primaryjoin="Trip.vehicle_id == Vehicle.id",
    )
    route = relationship(
        "Route",
        lazy="select",
        foreign_keys=[route_id],
        primaryjoin="Trip.route_id == Route.id",
    )
    trip_assignments = relationship("TripAssignment", back_populates="trip", lazy="select")
    tracking_sessions = relationship("TrackingSession", back_populates="trip", lazy="select")
    state_history = relationship("TripStateHistory", back_populates="trip", lazy="select")
    eta_predictions = relationship("ETAPrediction", back_populates="trip", lazy="select")

    __table_args__ = (
        # ── CRITICAL: trip.route_id must match service.route_id ──
        # Composite FK: (service_id, route_id) -> services(id, route_id)
        ForeignKeyConstraint(
            ["service_id", "route_id"],
            ["services.id", "services.route_id"],
            name="fk_trips_service_route",
        ),
        # ── Organization integrity: vehicle in same org ──
        ForeignKeyConstraint(
            ["organization_id", "vehicle_id"],
            ["vehicles.organization_id", "vehicles.id"],
            name="fk_trips_org_vehicle",
        ),
        # ── Organization integrity: service in same org ──
        ForeignKeyConstraint(
            ["organization_id", "service_id"],
            ["services.organization_id", "services.id"],
            name="fk_trips_org_service",
        ),
        Index("ix_trips_operating_date", "operating_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Trip {self.id} service={self.service_id} "
            f"vehicle={self.vehicle_id} date={self.operating_date}>"
        )


class TripAssignment(Base):
    """
    Trip-level operator participation. NOT permanent vehicle staffing.
    """

    __tablename__ = "trip_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignmentstatus", create_constraint=False),
        nullable=False,
        default=AssignmentStatus.ASSIGNED,
    )

    # ── Relationships ────────────────────────────────────────────────
    trip = relationship("Trip", back_populates="trip_assignments", lazy="select")
    user = relationship("User", back_populates="trip_assignments", lazy="select")
    device = relationship("Device", foreign_keys=[device_id], lazy="select")

    def __repr__(self) -> str:
        return f"<TripAssignment trip={self.trip_id} user={self.user_id} role={self.role}>"


class TripStateHistory(Base):
    """Preserves trip operational state transitions. No inference logic."""

    __tablename__ = "trip_state_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False, index=True
    )
    previous_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_state: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ── Relationships ────────────────────────────────────────────────
    trip = relationship("Trip", back_populates="state_history", lazy="select")

    def __repr__(self) -> str:
        return f"<TripStateHistory trip={self.trip_id} {self.previous_state}->{self.new_state}>"
