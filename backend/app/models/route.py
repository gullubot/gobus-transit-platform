"""
Transit Platform — Route, Stop, and RouteStop Models.

BUILD 1: Network topology schema with PostGIS spatial columns.
No route matching logic.
"""

import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import RouteStatus, StopStatus


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    route_code: Mapped[str] = mapped_column(String(50), nullable=False)
    route_name: Mapped[str] = mapped_column(String(255), nullable=False)
    geometry = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[RouteStatus] = mapped_column(
        Enum(RouteStatus, name="routestatus", create_constraint=False),
        nullable=False,
        default=RouteStatus.ACTIVE,
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
    organization = relationship("Organization", back_populates="routes", lazy="select")
    route_stops = relationship("RouteStop", back_populates="route", lazy="select")
    services = relationship(
        "Service",
        back_populates="route",
        lazy="select",
        primaryjoin="Route.id == Service.route_id",
        foreign_keys="[Service.route_id]",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "route_code", name="uq_routes_org_code"),
        # Composite key: allows services to composite-FK (organization_id, route_id)
        UniqueConstraint("id", "organization_id", name="uq_routes_id_org"),
    )

    def __repr__(self) -> str:
        return f"<Route {self.route_code!r} ({self.route_name})>"


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    stop_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    status: Mapped[StopStatus] = mapped_column(
        Enum(StopStatus, name="stopstatus", create_constraint=False),
        nullable=False,
        default=StopStatus.ACTIVE,
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
    organization = relationship("Organization", back_populates="stops", lazy="select")
    route_stops = relationship("RouteStop", back_populates="stop", lazy="select")

    __table_args__ = (UniqueConstraint("organization_id", "stop_code", name="uq_stops_org_code"),)

    def __repr__(self) -> str:
        return f"<Stop {self.stop_code!r} ({self.name})>"


class RouteStop(Base):
    """
    Junction table linking routes to stops with canonical sequence.
    A_TO_B = ascending sequence_number; B_TO_A = descending.
    Do NOT duplicate rows for both directions.
    """

    __tablename__ = "route_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False
    )
    stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stops.id"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_from_start: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    nominal_travel_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    route = relationship("Route", back_populates="route_stops", lazy="select")
    stop = relationship("Stop", back_populates="route_stops", lazy="select")

    __table_args__ = (
        UniqueConstraint("route_id", "sequence_number", name="uq_route_stops_route_seq"),
        UniqueConstraint("route_id", "stop_id", name="uq_route_stops_route_stop"),
        CheckConstraint("sequence_number > 0", name="ck_route_stops_seq_positive"),
        Index("ix_route_stops_route_seq", "route_id", "sequence_number"),
    )

    def __repr__(self) -> str:
        return f"<RouteStop route={self.route_id} seq={self.sequence_number}>"
