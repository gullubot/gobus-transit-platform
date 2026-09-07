"""
Transit Platform — Fare Models.

Admin-configured distance-slab fare models.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class FareConfiguration(Base):
    __tablename__ = "fare_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
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
    organization = relationship("Organization", lazy="select")
    slabs = relationship(
        "FareSlab", 
        back_populates="fare_configuration", 
        lazy="select",
        cascade="all, delete-orphan",
        order_by="FareSlab.min_distance_km"
    )

    def __repr__(self) -> str:
        return f"<FareConfiguration {self.name} (Org: {self.organization_id})>"


class FareSlab(Base):
    __tablename__ = "fare_slabs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fare_configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fare_configurations.id"),
        nullable=False,
        index=True,
    )
    min_distance_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    fare_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    fare_configuration = relationship("FareConfiguration", back_populates="slabs", lazy="select")

    def __repr__(self) -> str:
        return f"<FareSlab {self.min_distance_km}-{self.max_distance_km}km = {self.fare_amount}>"
