from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.enums import Direction, Confidence, VehicleStatus

class AdminLiveOperationResponse(BaseModel):
    # Vehicle
    vehicle_id: str
    vehicle_number: str
    registration_number: Optional[str] = None
    vehicle_type: str
    vehicle_status: VehicleStatus

    # Service & Route
    service_id: Optional[str] = None
    service_name: Optional[str] = None
    route_id: Optional[str] = None
    route_name: Optional[str] = None
    direction: Optional[Direction] = None

    # Stop Context
    current_stop_id: Optional[str] = None
    current_stop_name: Optional[str] = None
    next_stop_id: Optional[str] = None
    next_stop_name: Optional[str] = None

    # Operational/State
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    route_progress: Optional[float] = None
    dwell_state: Optional[str] = None
    
    # ETA
    eta_seconds: Optional[int] = None
    eta_status: Optional[str] = None

    # Intelligence State
    state: str
    state_reason: Optional[str] = None
    confidence: Optional[Confidence] = None
    last_observed_at: Optional[datetime] = None
    
    # Schedule Context (Optional/derived)
    scheduled_status: Optional[str] = None
    planned_departure: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
