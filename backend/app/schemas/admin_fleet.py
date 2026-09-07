from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Direction, VehicleStatus

# ── Shared Summaries ─────────────────────────────────────────────────────────

class PersonnelSummary(BaseModel):
    id: uuid.UUID
    name: str
    employee_code: Optional[str] = None
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ServiceSummary(BaseModel):
    id: uuid.UUID
    service_code: str
    service_name: str
    route_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

class VehicleSummary(BaseModel):
    id: uuid.UUID
    vehicle_number: str
    vehicle_type: str

    model_config = ConfigDict(from_attributes=True)

# ── Vehicle Schemas ──────────────────────────────────────────────────────────

class VehicleBase(BaseModel):
    vehicle_number: str = Field(..., max_length=50)
    registration_number: Optional[str] = Field(None, max_length=50)
    vehicle_type: str = Field(..., max_length=50)
    status: VehicleStatus = Field(default=VehicleStatus.ACTIVE)

class VehicleCreate(VehicleBase):
    service_id: Optional[uuid.UUID] = None

class VehicleUpdate(BaseModel):
    vehicle_number: Optional[str] = Field(None, max_length=50)
    registration_number: Optional[str] = Field(None, max_length=50)
    vehicle_type: Optional[str] = Field(None, max_length=50)
    status: Optional[VehicleStatus] = None

class VehicleResponse(VehicleBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    driver: Optional[PersonnelSummary] = None
    conductor: Optional[PersonnelSummary] = None
    service: Optional[ServiceSummary] = None

    model_config = ConfigDict(from_attributes=True)

class VehicleCrewAssignmentRequest(BaseModel):
    service_id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    conductor_id: Optional[uuid.UUID] = None

class VehicleCrewAssignmentResponse(BaseModel):
    vehicle_id: uuid.UUID
    service_id: uuid.UUID
    driver: Optional[PersonnelSummary] = None
    conductor: Optional[PersonnelSummary] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Depot Schedule Schemas ───────────────────────────────────────────────────

class DepotScheduleBase(BaseModel):
    vehicle_id: uuid.UUID
    service_id: uuid.UUID
    direction: Direction
    operating_date: date
    planned_departure: datetime
    planned_arrival: Optional[datetime] = None
    status: str = Field(default="PLANNED", max_length=20)
    source: Optional[str] = Field(None, max_length=50)

class DepotScheduleCreate(DepotScheduleBase):
    pass

class DepotScheduleUpdate(BaseModel):
    vehicle_id: Optional[uuid.UUID] = None
    service_id: Optional[uuid.UUID] = None
    direction: Optional[Direction] = None
    operating_date: Optional[date] = None
    planned_departure: Optional[datetime] = None
    planned_arrival: Optional[datetime] = None
    status: Optional[str] = Field(None, max_length=20)
    source: Optional[str] = Field(None, max_length=50)

class DepotScheduleResponse(DepotScheduleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    # Enrichment fields for the Admin UI
    service: Optional[ServiceSummary] = None
    vehicle: Optional[VehicleSummary] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------------
# FLEET SCHEDULE (SERVICE-SCOPED RECURRING TIMETABLE)
# -------------------------------------------------------------------------

class FleetScheduleItemResponse(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    vehicle_id: uuid.UUID
    vehicle_number: str
    vehicle_type: Optional[str] = None
    registration_number: Optional[str] = None
    vehicle_status: Optional[str] = None
    departure_time: str  # "HH:MM" e.g. "06:30"
    formatted_departure_time: str  # e.g. "06:30 AM"
    direction: Direction
    driver: Optional[PersonnelSummary] = None
    conductor: Optional[PersonnelSummary] = None
    every_day: bool = True
    status: str = "PLANNED"
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FleetScheduleCreateRequest(BaseModel):
    service_id: uuid.UUID
    vehicle_id: uuid.UUID
    direction: Direction = Direction.A_TO_B
    departure_time: str = Field(..., description="Departure time in HH:MM or HH:MM:SS format")
    every_day: bool = True


class FleetScheduleUpdateRequest(BaseModel):
    vehicle_id: Optional[uuid.UUID] = None
    direction: Optional[Direction] = None
    departure_time: Optional[str] = Field(None, description="Departure time in HH:MM or HH:MM:SS format")
    every_day: Optional[bool] = None


# -------------------------------------------------------------------------
# MAJOR DEPOT & DEPOT-CENTRIC COMBINED DEPARTURES
# -------------------------------------------------------------------------

class MajorDepotResponse(BaseModel):
    id: uuid.UUID
    stop_code: str
    stop_name: str
    routes_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DepotDepartureItemResponse(BaseModel):
    id: uuid.UUID
    departure_time: str
    formatted_departure_time: str
    vehicle_id: uuid.UUID
    vehicle_number: str
    registration_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_status: str
    service_id: uuid.UUID
    service_name: str
    service_code: str
    route_id: uuid.UUID
    route_code: Optional[str] = None
    route_name: Optional[str] = None
    origin_stop_id: uuid.UUID
    origin_stop_name: str
    origin_stop_code: Optional[str] = None
    destination_stop_id: uuid.UUID
    destination_stop_name: str
    destination_stop_code: Optional[str] = None
    direction: Direction
    status: str
    every_day: bool = True
    source: Optional[str] = None
    operating_date: date

    model_config = ConfigDict(from_attributes=True)


# ── Service ↔ Vehicle Membership Schemas ─────────────────────────────────────

class ServiceVehicleAssignRequest(BaseModel):
    vehicle_id: uuid.UUID

class ServiceVehicleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    service_id: uuid.UUID
    vehicle_id: uuid.UUID
    status: str
    assigned_at: datetime
    unassigned_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class AvailableVehicleOption(BaseModel):
    id: uuid.UUID
    vehicle_number: str
    registration_number: Optional[str] = None
    vehicle_type: str
    status: str
    is_assigned_to_current_service: bool = False
    assigned_services: list[ServiceSummary] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
