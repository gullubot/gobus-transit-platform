"""
Transit Platform — Organization Model.

BUILD 1: Root domain entity. All org-scoped resources reference this.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import OrganizationStatus, OrganizationType


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Kolkata", index=True)
    type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType, name="organizationtype", create_constraint=False),
        nullable=False,
        default=OrganizationType.OTHER,
    )
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, name="organizationstatus", create_constraint=False),
        nullable=False,
        default=OrganizationStatus.ACTIVE,
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
    users = relationship("User", back_populates="organization", lazy="select")
    devices = relationship("Device", back_populates="organization", lazy="select")
    services = relationship("Service", back_populates="organization", lazy="select")
    routes = relationship("Route", back_populates="organization", lazy="select")
    stops = relationship("Stop", back_populates="organization", lazy="select")
    vehicles = relationship("Vehicle", back_populates="organization", lazy="select")
    service_alerts = relationship("ServiceAlert", back_populates="organization", lazy="select")
    audit_logs = relationship("AuditLog", back_populates="organization", lazy="select")

    __table_args__ = (
        # Global name uniqueness for MVP
        UniqueConstraint("name", name="uq_organizations_name"),
        # Composite key for org-scoped composite FKs from child tables
        UniqueConstraint("id", "id", name="uq_organizations_id"),
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name!r}>"
