"""
Transit Platform — Device Model.

BUILD 1: Device entity schema only. No pairing/authentication workflow.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import DeviceStatus


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="devicestatus", create_constraint=False),
        nullable=False,
        default=DeviceStatus.PENDING,
        index=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    gps_permission_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    network_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    battery_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    paired_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    organization = relationship("Organization", back_populates="devices", lazy="select")
    tracking_sessions = relationship("TrackingSession", back_populates="device", lazy="select")

    __table_args__ = (
        # Composite key for org-scoped composite FKs from trip_assignments
        UniqueConstraint("id", "organization_id", name="uq_devices_id_org"),
    )

    def __repr__(self) -> str:
        return f"<Device {self.device_name!r} platform={self.platform}>"
