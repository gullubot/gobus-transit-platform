"""
Transit Platform — ServiceVehicle Model.

Authoritative association model establishing explicit membership
between a Vehicle and a Service within an Organization.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ServiceVehicle(Base):
    """
    Authoritative Service ↔ Vehicle membership entity.

    Separates permanent service fleet membership from transient operational
    records (DepotSchedule departures and Trip executions).
    """

    __tablename__ = "service_vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id"),
        nullable=False,
        index=True,
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )
    assigned_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    unassigned_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    organization = relationship("Organization", lazy="select", foreign_keys=[organization_id])
    service = relationship(
        "Service",
        back_populates="service_vehicles",
        lazy="select",
        foreign_keys=[service_id],
        primaryjoin="ServiceVehicle.service_id == Service.id",
    )
    vehicle = relationship(
        "Vehicle",
        back_populates="service_memberships",
        lazy="select",
        foreign_keys=[vehicle_id],
        primaryjoin="ServiceVehicle.vehicle_id == Vehicle.id",
    )

    __table_args__ = (
        # Prevent duplicate membership records for the same (service, vehicle) pair
        UniqueConstraint("service_id", "vehicle_id", name="uq_service_vehicles_service_vehicle"),
        # Composite FK: service must belong to the same organization
        ForeignKeyConstraint(
            ["organization_id", "service_id"],
            ["services.organization_id", "services.id"],
            name="fk_service_vehicles_org_service",
        ),
        # Composite FK: vehicle must belong to the same organization
        ForeignKeyConstraint(
            ["organization_id", "vehicle_id"],
            ["vehicles.organization_id", "vehicles.id"],
            name="fk_service_vehicles_org_vehicle",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ServiceVehicle service_id={self.service_id} "
            f"vehicle_id={self.vehicle_id} status={self.status!r}>"
        )
