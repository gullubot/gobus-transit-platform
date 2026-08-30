import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.intelligence.crowding_engine import CrowdingEngine
from app.models.state import BusCurrentState
from app.models.trip import Trip
from app.schemas.passenger import PassengerVehicleStateResponse

router = APIRouter(tags=["passenger"])


@router.get("/api/passenger/vehicles/{vehicle_id}", response_model=PassengerVehicleStateResponse)
def get_vehicle_state(
    vehicle_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PassengerVehicleStateResponse:
    """
    Returns the composed passenger-facing view of a vehicle's canonical state, ETA, and crowding.
    """
    row = db.execute(
        select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)
    ).scalar_one_or_none()

    if not row or not row.last_observed_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle state not found")

    crowding_response = None
    try:
        crowding_response = CrowdingEngine.aggregate_vehicle_crowding(db, vehicle_id)
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    row_last_observed_at = row.last_observed_at
    if row_last_observed_at.tzinfo is None:
        row_last_observed_at = row_last_observed_at.replace(tzinfo=timezone.utc)

    age_seconds = (now - row_last_observed_at).total_seconds()

    current_state = row.state if row.state else "UNKNOWN"
    if age_seconds > 600:
        current_state = "OFFLINE"

    trip_status = None
    if row.trip_id:
        trip = db.get(Trip, row.trip_id)
        if trip:
            trip_status = trip.status.value

    return PassengerVehicleStateResponse(
        vehicle_id=str(vehicle_id),
        route_id=str(row.route_id) if row.route_id else None,
        direction=row.direction.value if row.direction else None,
        current_stop_id=str(row.current_stop_id) if row.current_stop_id else None,
        next_stop_id=str(row.next_stop_id) if row.next_stop_id else None,
        state=current_state,
        trip_status=trip_status,
        eta_seconds=None,
        eta_status=None,
        crowding=crowding_response,
        last_updated_at=row.last_received_at or row.last_observed_at,
    )
