"""
Transit Platform — Vehicle Model.

BUILD 1: Vehicle entity. NO permanent service_id — vehicles are assigned
to services through trips.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import VehicleStatus


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    vehicle_number: Mapped[str] = mapped_column(String(50), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus, name="vehiclestatus", create_constraint=False),
        nullable=False,
        default=VehicleStatus.ACTIVE,
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
    organization = relationship("Organization", back_populates="vehicles", lazy="select")
    trips = relationship(
        "Trip",
        back_populates="vehicle",
        lazy="select",
        primaryjoin="Vehicle.id == Trip.vehicle_id",
        foreign_keys="[Trip.vehicle_id]",
    )
    depot_schedules = relationship("DepotSchedule", back_populates="vehicle", lazy="select")
    service_memberships = relationship(
        "ServiceVehicle",
        back_populates="vehicle",
        lazy="select",
        primaryjoin="Vehicle.id == ServiceVehicle.vehicle_id",
        foreign_keys="[ServiceVehicle.vehicle_id]",
    )
    bus_current_state = relationship(
        "BusCurrentState", back_populates="vehicle", uselist=False, lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "vehicle_number", name="uq_vehicles_org_number"),
        # Composite key for trip org integrity: trips(organization_id, vehicle_id)
        UniqueConstraint("id", "organization_id", name="uq_vehicles_id_org"),
    )

    def __repr__(self) -> str:
        return f"<Vehicle {self.vehicle_number!r} type={self.vehicle_type}>"
