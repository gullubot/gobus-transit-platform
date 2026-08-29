import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKeyConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import CrowdingSource, CrowdingState


class CrowdingReport(Base):
    """
    Records crowding conditions within a vehicle.
    """

    __tablename__ = "crowding_reports"

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    crowding_state: Mapped[CrowdingState] = mapped_column(
        Enum(CrowdingState, name="crowdingstate", create_constraint=False),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    source_type: Mapped[CrowdingSource] = mapped_column(
        Enum(CrowdingSource, name="crowdingsource", create_constraint=False),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────
    vehicle = relationship(
        "Vehicle",
        lazy="select",
        foreign_keys=[vehicle_id],
        primaryjoin="CrowdingReport.vehicle_id == Vehicle.id",
    )
    trip = relationship(
        "Trip",
        lazy="select",
        foreign_keys=[trip_id],
        primaryjoin="CrowdingReport.trip_id == Trip.id",
    )

    __table_args__ = (
        # ── Structural Tenant Isolation ──
        ForeignKeyConstraint(
            ["organization_id", "vehicle_id"],
            ["vehicles.organization_id", "vehicles.id"],
            name="fk_crowding_org_vehicle",
        ),
        ForeignKeyConstraint(
            ["organization_id", "trip_id"],
            ["trips.organization_id", "trips.id"],
            name="fk_crowding_org_trip",
        ),
        # ── Fast Retrieval Indexes ──
        Index(
            "idx_crowding_org_vehicle_observed",
            "organization_id",
            "vehicle_id",
            "observed_at",
            postgresql_ops={"observed_at": "DESC"},
        ),
        Index(
            "idx_crowding_trip_observed",
            "trip_id",
            "observed_at",
            postgresql_ops={"observed_at": "DESC"},
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CrowdingReport {self.report_id} vehicle={self.vehicle_id} "
            f"state={self.crowding_state} source={self.source_type}>"
        )
