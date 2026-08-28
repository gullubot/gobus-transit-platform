"""
Transit Platform — Historical ETA Data Models.

BUILD 3 Phase 6: Historical Segment and Route travel time baselines.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class HistoricalSegmentTravel(Base):
    __tablename__ = "historical_segment_travel"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False
    )
    from_stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stops.id"), nullable=False
    )
    to_stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stops.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    time_of_day_bucket: Mapped[str] = mapped_column(String(10), nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    median_travel_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    median_destination_stop_dwell_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "route_id",
            "direction",
            "from_stop_id",
            "to_stop_id",
            "time_of_day_bucket",
            "day_of_week",
            name="uq_hist_segment_org_route_dir_stops_time_day",
        ),
        Index(
            "ix_hist_seg_org_route_stops",
            "organization_id",
            "route_id",
            "from_stop_id",
            "to_stop_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<HistoricalSegmentTravel {self.route_id} {self.direction} {self.time_of_day_bucket}>"
        )


class HistoricalRouteTravel(Base):
    __tablename__ = "historical_route_travel"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    time_of_day_bucket: Mapped[str] = mapped_column(String(10), nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    median_travel_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "route_id",
            "direction",
            "time_of_day_bucket",
            "day_of_week",
            name="uq_hist_route_org_route_dir_time_day",
        ),
        Index("ix_hist_route_org_route", "organization_id", "route_id"),
    )

    def __repr__(self) -> str:
        return f"<HistoricalRouteTravel {self.route_id} {self.direction} {self.time_of_day_bucket}>"
