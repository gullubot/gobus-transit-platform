import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.crowding import CrowdingReport
from app.models.trip import Trip


def get_active_trip_for_vehicle(
    session: Session, organization_id: uuid.UUID, vehicle_id: uuid.UUID, observed_at: datetime
) -> Optional[uuid.UUID]:
    """
    Finds the authoritative trip for the given vehicle at the exact time of observation.
    Uses TrackingSession temporal bounds to avoid resolving to the wrong trip
    if reports are delayed.
    """
    from sqlalchemy import or_

    from app.models.tracking import TrackingSession

    stmt = (
        select(Trip.id)
        .join(TrackingSession, TrackingSession.trip_id == Trip.id)
        .where(
            Trip.organization_id == organization_id,
            Trip.vehicle_id == vehicle_id,
            TrackingSession.started_at <= observed_at,
            or_(TrackingSession.ended_at.is_(None), TrackingSession.ended_at >= observed_at),
        )
    )
    results = session.execute(stmt).scalars().all()
    # Distinct trips only
    unique_trips = list(set(results))

    # CASE A: exactly one valid trip -> bind trip_id
    if len(unique_trips) == 1:
        return unique_trips[0]

    # CASE B: zero valid trips -> return None (UNRESOLVED)
    # CASE C: multiple plausible trips -> return None (UNRESOLVED, never guess)
    return None


def save_crowding_report(session: Session, report: CrowdingReport) -> None:
    """
    Idempotent insert of a crowding report using ON CONFLICT DO NOTHING.
    Duplicate report_ids yield a success implicitly.
    """
    stmt = insert(CrowdingReport).values(
        report_id=report.report_id,
        organization_id=report.organization_id,
        vehicle_id=report.vehicle_id,
        trip_id=report.trip_id,
        crowding_state=report.crowding_state,
        confidence=report.confidence,
        observed_at=report.observed_at,
        received_at=report.received_at,
        source_type=report.source_type,
    )

    # Idempotent insert: if duplicate report_id, do nothing.
    stmt = stmt.on_conflict_do_nothing(index_elements=["report_id"])

    session.execute(stmt)
    # The session.commit() will be called by the engine or the router.
