"""
Transit Platform — ServiceAlert Model.

BUILD 1: Alert schema with scope/target integrity.
No notification delivery system.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import AlertScope


class ServiceAlert(Base):
    """
    Service alerts with scope-aware target references.

    Scope/target rule (enforced at application level, documented at schema):
      SERVICE scope → service_id REQUIRED
      ROUTE scope   → route_id REQUIRED
      STOP scope    → stop_id REQUIRED
      TRIP scope    → trip_id REQUIRED
    """

    __tablename__ = "service_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id"),
        nullable=True,
        index=True,
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id"),
        nullable=True,
        index=True,
    )
    stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stops.id"),
        nullable=True,
        index=True,
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id"),
        nullable=True,
        index=True,
    )
    scope: Mapped[AlertScope] = mapped_column(
        Enum(AlertScope, name="alertscope", create_constraint=False),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(nullable=True)
    effective_until: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
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
    organization = relationship("Organization", back_populates="service_alerts", lazy="select")
    service = relationship("Service", foreign_keys=[service_id], lazy="select")
    route = relationship("Route", foreign_keys=[route_id], lazy="select")
    stop = relationship("Stop", foreign_keys=[stop_id], lazy="select")
    trip = relationship("Trip", foreign_keys=[trip_id], lazy="select")
    created_by_user = relationship("User", foreign_keys=[created_by], lazy="select")

    # NOTE: Scope/target CHECK constraints are added in the migration
    # because SQLAlchemy CHECK expressions referencing enum columns
    # are cleaner expressed in raw SQL.

    def __repr__(self) -> str:
        return f"<ServiceAlert {self.title!r} scope={self.scope.value}>"
