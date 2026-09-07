from datetime import datetime, time
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from app.models.enums import Direction, RouteStatus, StopStatus, ServiceStatus


# --- Stops ---
class AdminStopBase(BaseModel):
    stop_code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    latitude: float
    longitude: float
    status: StopStatus = StopStatus.ACTIVE


class AdminStopCreate(AdminStopBase):
    aliases: List[str] = Field(default_factory=list)


class AdminStopUpdate(BaseModel):
    stop_code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[StopStatus] = None
    aliases: Optional[List[str]] = None


class AdminStopResponse(AdminStopBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    aliases: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RouteDuplicateCheckRequest(BaseModel):
    stops: List[uuid.UUID]


class RouteDuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    existing_route_id: Optional[uuid.UUID] = None
    route_code: Optional[str] = None
    route_name: Optional[str] = None
    matching_stops: List[str] = Field(default_factory=list)


# --- Routes ---
class AdminRouteBase(BaseModel):
    route_code: str = Field(..., max_length=50)
    route_name: str = Field(..., max_length=255)
    distance_km: Optional[float] = None
    status: RouteStatus = RouteStatus.ACTIVE


class RoutePreviewRequest(BaseModel):
    start_stop_id: uuid.UUID
    end_stop_id: uuid.UUID
    intermediate_stop_ids: List[uuid.UUID] = Field(default_factory=list)
    exclude_route_id: Optional[uuid.UUID] = None


class RoutePreviewStopItem(BaseModel):
    stop_id: uuid.UUID
    stop_code: str
    stop_name: str
    sequence_number: int
    distance_from_start: Optional[float] = None
    nominal_travel_time_seconds: Optional[int] = None


class RoutePreviewResponse(BaseModel):
    distance_km: float
    duration_seconds: int
    geometry: Dict[str, Any]
    stops: List[RoutePreviewStopItem]
    duplicate_match: Optional[RouteDuplicateCheckResponse] = None


class AdminRouteCreateWithStops(BaseModel):
    route_code: str = Field(..., max_length=50)
    route_name: str = Field(..., max_length=255)
    start_stop_id: uuid.UUID
    end_stop_id: uuid.UUID
    intermediate_stop_ids: List[uuid.UUID] = Field(default_factory=list)
    status: RouteStatus = RouteStatus.ACTIVE


class AdminRouteCreate(AdminRouteBase):
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON LineString dictionary
    # Optional stop sequence for atomic creation
    start_stop_id: Optional[uuid.UUID] = None
    end_stop_id: Optional[uuid.UUID] = None
    intermediate_stop_ids: Optional[List[uuid.UUID]] = None


class AdminRouteUpdate(BaseModel):
    route_code: Optional[str] = Field(None, max_length=50)
    route_name: Optional[str] = Field(None, max_length=255)
    distance_km: Optional[float] = None
    status: Optional[RouteStatus] = None
    geometry: Optional[Dict[str, Any]] = None
    start_stop_id: Optional[uuid.UUID] = None
    end_stop_id: Optional[uuid.UUID] = None
    intermediate_stop_ids: Optional[List[uuid.UUID]] = None


class AdminRouteResponse(AdminRouteBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    geometry: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Route Stops ---
class AdminRouteStopBase(BaseModel):
    stop_id: uuid.UUID
    sequence_number: int = Field(..., gt=0)
    distance_from_start: Optional[float] = None
    nominal_travel_time_seconds: Optional[int] = None


class AdminRouteStopCreate(AdminRouteStopBase):
    pass


class AdminRouteStopUpdate(BaseModel):
    sequence_number: Optional[int] = Field(None, gt=0)
    distance_from_start: Optional[float] = None
    nominal_travel_time_seconds: Optional[int] = None


class AdminRouteStopResponse(AdminRouteStopBase):
    id: uuid.UUID
    route_id: uuid.UUID
    
    # Hydrated stop details for the UI
    stop_code: Optional[str] = None
    stop_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminRouteStopBulkUpdate(BaseModel):
    stops: List[AdminRouteStopBase]


from app.schemas.admin_fare import FareSlabCreate


# --- Services ---
class AdminServiceBase(BaseModel):
    service_code: str = Field(..., max_length=50)
    service_name: str = Field(..., max_length=255)
    route_id: uuid.UUID
    fare_configuration_id: Optional[uuid.UUID] = None
    status: ServiceStatus = ServiceStatus.ACTIVE


class AdminServiceCreate(AdminServiceBase):
    initial_fare_slabs: Optional[List[FareSlabCreate]] = None


class AdminServiceUpdate(BaseModel):
    service_code: Optional[str] = Field(None, max_length=50)
    service_name: Optional[str] = Field(None, max_length=255)
    route_id: Optional[uuid.UUID] = None
    fare_configuration_id: Optional[uuid.UUID] = None
    status: Optional[ServiceStatus] = None


class AdminServiceResponse(AdminServiceBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Additional fields for UI convenience
    route_code: Optional[str] = None
    route_name: Optional[str] = None
    fare_configuration_name: Optional[str] = None
    fare_is_active: Optional[bool] = None
    fare_slabs_count: Optional[int] = None
    fare_currency: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Service Schedules ---
class AdminServiceScheduleBase(BaseModel):
    direction: Direction
    start_time: time
    end_time: time
    typical_interval_minutes: int = Field(..., gt=0)
    days_of_week: list[int] = Field(...)
    effective_from: datetime
    effective_until: Optional[datetime] = None
    status: str = "ACTIVE"


class AdminServiceScheduleCreate(AdminServiceScheduleBase):
    pass


class AdminServiceScheduleUpdate(BaseModel):
    direction: Optional[Direction] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    typical_interval_minutes: Optional[int] = Field(None, gt=0)
    days_of_week: Optional[list[int]] = Field(None)
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    status: Optional[str] = None


class AdminServiceScheduleResponse(AdminServiceScheduleBase):
    id: uuid.UUID
    service_id: uuid.UUID
    updated_at: datetime

    model_config = {"from_attributes": True}
