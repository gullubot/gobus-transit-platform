from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.crowding import PassengerCrowdingResponse


class PassengerVehicleStateResponse(BaseModel):
    vehicle_id: str
    route_id: Optional[str]
    direction: Optional[str]
    current_stop_id: Optional[str]
    next_stop_id: Optional[str]

    # State
    state: str
    trip_status: Optional[str]

    # ETA
    eta_seconds: Optional[int]
    eta_status: Optional[str]

    # Crowding (Composed)
    crowding: Optional[PassengerCrowdingResponse]

    last_updated_at: Optional[datetime]
