"""
Transit Platform — Service, ServiceSchedule, and DepotSchedule Models.

BUILD 1: Service is the core operational entity binding to one primary route.
services.route_id is NOT NULL for MVP.
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import Direction, ServiceStatus


class Service(Base):
    """
    Service entity — each service has exactly one primary route (MVP rule).

    Organization integrity: composite FK enforces that the service's route
    belongs to the same organization as the service itself.
    """

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_code: Mapped[str] = mapped_column(String(50), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ServiceStatus] = mapped_column(
        Enum(ServiceStatus, name="servicestatus", create_constraint=False),
        nullable=False,
        default=ServiceStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    fare_configuration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fare_configurations.id"), nullable=True, index=True
    )

    # ── Relationships ────────────────────────────────────────────────
    organization = relationship("Organization", back_populates="services", lazy="select")
    fare_configuration = relationship("FareConfiguration", lazy="select")
    route = relationship(
        "Route",
        back_populates="services",
        lazy="select",
        foreign_keys=[route_id],
        primaryjoin="Service.route_id == Route.id",
    )
    service_schedules = relationship("ServiceSchedule", back_populates="service", lazy="select")
    depot_schedules = relationship("DepotSchedule", back_populates="service", lazy="select")
    service_vehicles = relationship(
        "ServiceVehicle",
        back_populates="service",
        lazy="select",
        primaryjoin="Service.id == ServiceVehicle.service_id",
        foreign_keys="[ServiceVehicle.service_id]",
    )
    trips = relationship(
        "Trip",
        back_populates="service",
        lazy="select",
        primaryjoin="Service.id == Trip.service_id",
        foreign_keys="[Trip.service_id]",
    )

    __table_args__ = (
        # Organization-scoped service code uniqueness
        UniqueConstraint("organization_id", "service_code", name="uq_services_org_code"),
        # Composite key for trip composite FK: trips(service_id, route_id)
        UniqueConstraint("id", "route_id", name="uq_services_id_route"),
        # Composite key for trip org integrity: trips(organization_id, service_id)
        UniqueConstraint("id", "organization_id", name="uq_services_id_org"),
        # ── CRITICAL: service ↔ route organization integrity ──
        # Enforces that service.route_id references a route in the SAME org.
        ForeignKeyConstraint(
            ["organization_id", "route_id"],
            ["routes.organization_id", "routes.id"],
            name="fk_services_org_route",
        ),
    )

    def __repr__(self) -> str:
        return f"<Service {self.service_code!r} ({self.service_name})>"


class ServiceSchedule(Base):
    """
    Passenger-facing service availability/frequency information.
    Not individual vehicle departures.
    """

    __tablename__ = "service_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False, index=True
    )
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, name="direction", create_constraint=False),
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    typical_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    days_of_week: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    service = relationship("Service", back_populates="service_schedules", lazy="select")
    updated_by_user = relationship("User", foreign_keys=[updated_by], lazy="select")

    __table_args__ = (
        CheckConstraint(
            "typical_interval_minutes > 0",
            name="ck_service_schedules_interval_positive",
        ),
    )

    def __repr__(self) -> str:
        return f"<ServiceSchedule svc={self.service_id} dir={self.direction}>"


class DepotSchedule(Base):
    """
    Operational/depot scheduling for vehicle departures.
    operating_date is required for MVP.
    """

    __tablename__ = "depot_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False, index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False, index=True
    )
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, name="direction", create_constraint=False),
        nullable=False,
    )
    operating_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_departure: Mapped[datetime] = mapped_column(nullable=False)
    planned_arrival: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PLANNED")
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    vehicle = relationship("Vehicle", back_populates="depot_schedules", lazy="select")
    service = relationship("Service", back_populates="depot_schedules", lazy="select")

    def __repr__(self) -> str:
        return f"<DepotSchedule vehicle={self.vehicle_id} date={self.operating_date}>"
