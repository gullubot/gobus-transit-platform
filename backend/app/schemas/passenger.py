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


class PassengerCityResponse(BaseModel):
    id: str
    name: str


class PassengerOrganizationResponse(BaseModel):
    id: str
    name: str


class PassengerStopResponse(BaseModel):
    id: str
    organization_id: str
    stop_code: str
    name: str
    latitude: Optional[float]
    longitude: Optional[float]
    aliases: list[str] = []


class PassengerServiceSummaryResponse(BaseModel):
    id: str
    organization_id: str
    service_code: str
    service_name: str
    route_id: str


class RouteStopDetail(BaseModel):
    stop_id: str
    stop_name: str
    sequence_number: int
    latitude: Optional[float]
    longitude: Optional[float]
    distance_from_start: Optional[float]
    nominal_travel_time_seconds: Optional[int]


class ServiceScheduleDetail(BaseModel):
    direction: str
    start_time: str
    end_time: str
    typical_interval_minutes: int
    days_of_week: Optional[list[int]]


class PassengerServiceDetailResponse(BaseModel):
    id: str
    organization_id: str
    service_code: str
    service_name: str
    route_id: str
    route_code: str
    route_name: str
    route_geometry: Optional[dict] = None
    stops: list[RouteStopDetail]
    schedules: list[ServiceScheduleDetail]


class PassengerLiveBusResponse(BaseModel):
    vehicle_id: str
    latitude: Optional[float]
    longitude: Optional[float]
    direction: Optional[str]
    current_stop_id: Optional[str]
    next_stop_id: Optional[str]
    eta_seconds: Optional[int]
    eta_status: Optional[str]
    crowd_level: str
    state: str
    last_updated_at: Optional[datetime]


class PassengerServiceSearchNearestBus(BaseModel):
    vehicle_id: str
    eta_seconds: Optional[int]
    eta_status: Optional[str]
    crowd_level: str


class PassengerServiceSearchResponse(BaseModel):
    service_id: str
    service_name: str
    service_code: Optional[str] = None
    route_id: Optional[str] = None
    direction: str
    availability_mode: str = "SCHEDULED"  # LIVE | SCHEDULED | UNAVAILABLE
    departure_mode: str = "SCHEDULED_DEPARTURE"  # LIVE_DEPARTURE | SCHEDULED_DEPARTURE
    arrival_mode: str = "SCHEDULED_ARRIVAL"  # LIVE_ETA | SCHEDULED_ARRIVAL
    departure_timestamp: Optional[datetime] = None
    arrival_timestamp: Optional[datetime] = None
    expected_arrival_timestamp: Optional[datetime] = None
    relative_wait_seconds: Optional[int] = None
    relative_message: Optional[str] = None
    journey_duration_seconds: Optional[int] = None
    fare: Optional[float] = None
    is_direct: bool = True
    is_ac: bool = False
    service_type: str = "REGULAR"
    absolute_origin: Optional[str] = None
    absolute_destination: Optional[str] = None
    searched_origin: Optional[str] = None
    searched_destination: Optional[str] = None
    stops_count: int = 0
    active_buses_count: int = 0
    nearest_bus: Optional[PassengerServiceSearchNearestBus] = None
    ranking_score: Optional[float] = None


class PassengerDepartureResponse(BaseModel):
    service_id: str
    service_name: str
    direction: str
    route_origin: str
    route_destination: str
    scheduled_time: Optional[datetime]
    expected_time: Optional[datetime]
    status: str


class PassengerPlanTripResponse(BaseModel):
    service_id: str
    service_name: str
    direction: str
    route_origin: str
    route_destination: str
    scheduled_departure: Optional[datetime]
    scheduled_arrival: Optional[datetime]


class PassengerMatchedSlabResponse(BaseModel):
    id: str
    min_distance_km: float
    max_distance_km: Optional[float]
    fare_amount: float


class PassengerFareCalculationResponse(BaseModel):
    distance_km: float
    fare_amount: float
    currency: str
    matched_slab: PassengerMatchedSlabResponse
    fare_configuration_id: str
    fare_configuration_name: str
