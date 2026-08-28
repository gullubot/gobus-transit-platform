import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.core_models import CanonicalStateContext
from app.models.enums import Confidence
from app.models.state import BusCurrentState


def upsert_canonical_state(session: Session, context: CanonicalStateContext) -> None:
    """
    Safely upserts the canonical state into the bus_current_state table using a row lock.
    This guarantees that concurrent tracker updates don't cause high-water mark regressions.
    """
    vehicle_uuid = uuid.UUID(context.vehicle_id)

    # SELECT FOR UPDATE ensures exclusive row lock on this vehicle_id
    stmt = (
        select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_uuid).with_for_update()
    )
    row = session.execute(stmt).scalar_one_or_none()

    if row is None:
        row = BusCurrentState(vehicle_id=vehicle_uuid, updated_at=datetime.now(timezone.utc))
        session.add(row)

    # High-water mark protection at DB level:
    # If the DB row already has a newer canonical observation, we discard the stale update.
    row_time = row.last_observed_at
    ctx_time = context.last_observed_at

    if row_time and row_time.tzinfo is None:
        row_time = row_time.replace(tzinfo=timezone.utc)
    if ctx_time and ctx_time.tzinfo is None:
        ctx_time = ctx_time.replace(tzinfo=timezone.utc)

    if row_time and ctx_time and ctx_time < row_time:
        return

    # Update canonical fields
    row.trip_id = uuid.UUID(context.trip_id) if context.trip_id else None
    row.service_id = uuid.UUID(context.service_id) if context.service_id else None
    row.route_id = uuid.UUID(context.route_id) if context.route_id else None
    row.direction = context.direction

    row.latitude = context.lat
    row.longitude = context.lon
    row.speed = context.speed_mps
    row.heading = context.heading

    row.route_progress = context.route_progress_m
    row.current_stop_id = uuid.UUID(context.current_stop_id) if context.current_stop_id else None
    row.next_stop_id = uuid.UUID(context.next_stop_id) if context.next_stop_id else None
    row.dwell_state = context.dwell_state.value if context.dwell_state else None

    row.state = context.state.value if context.state else None
    # Assuming state_reason isn't populated currently by TrackerFusionEngine
    row.confidence = Confidence(context.confidence) if context.confidence else None
    row.canonical_source = context.canonical_source

    row.last_observed_at = context.last_observed_at
    row.last_received_at = context.last_received_at
    row.updated_at = datetime.now(timezone.utc)
