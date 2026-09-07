"""
Transit Platform — Service-Day Domain Model.

BUILD 4 Phase 5B: Immutable domain models representing full-day schedules,
vehicle duties, operator assignments, and execution timelines.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ServiceDayState(str, Enum):
    """Lifecycle state of the entire simulated service day."""
    DAY_NOT_STARTED = "DAY_NOT_STARTED"
    DAY_READY = "DAY_READY"
    DAY_RUNNING = "DAY_RUNNING"
    DAY_PAUSED = "DAY_PAUSED"
    DAY_STOPPING = "DAY_STOPPING"
    DAY_COMPLETED = "DAY_COMPLETED"
    DAY_ERROR = "DAY_ERROR"


class TripExecutionState(str, Enum):
    """Execution state of an individual scheduled trip."""
    PENDING = "PENDING"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    ENDING = "ENDING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class VehicleOperationalState(str, Enum):
    """Operational status of a vehicle within a service day duty."""
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    LAYOVER = "LAYOVER"
    ERROR = "ERROR"


class ServiceDayEventType(str, Enum):
    """Events occurring along the service-day operational timeline."""
    TRIP_START = "TRIP_START"
    TRIP_END = "TRIP_END"
    LAYOVER_START = "LAYOVER_START"
    LAYOVER_END = "LAYOVER_END"
    VEHICLE_UNAVAILABLE = "VEHICLE_UNAVAILABLE"
    OPERATOR_UNAVAILABLE = "OPERATOR_UNAVAILABLE"


@dataclass
class ScheduledTrip:
    """Represents a scheduled transit trip on the GoBus platform."""
    trip_id: str
    service_id: str
    route_id: str
    vehicle_id: str
    operator_code: str
    direction: str  # "A_TO_B" or "B_TO_A"
    operating_date: str  # "YYYY-MM-DD"
    planned_start: datetime
    planned_end: Optional[datetime] = None
    service_code: str = "UNKNOWN"
    route_code: str = "UNKNOWN"
    vehicle_number: str = "UNKNOWN"
    source: str = "SCHEDULE"
    state: TripExecutionState = TripExecutionState.PENDING
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Returns planned duration in seconds if planned_end is set, else 0."""
        if self.planned_end and self.planned_end >= self.planned_start:
            return (self.planned_end - self.planned_start).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Returns clean serialization omitting credentials."""
        return {
            "trip_id": self.trip_id,
            "service_id": self.service_id,
            "service_code": self.service_code,
            "route_id": self.route_id,
            "route_code": self.route_code,
            "vehicle_id": self.vehicle_id,
            "vehicle_number": self.vehicle_number,
            "operator_code": self.operator_code,
            "direction": self.direction,
            "operating_date": self.operating_date,
            "planned_start": self.planned_start.isoformat(),
            "planned_end": self.planned_end.isoformat() if self.planned_end else None,
            "duration_seconds": self.duration_seconds,
            "state": self.state.value,
            "actual_start": self.actual_start.isoformat() if self.actual_start else None,
            "actual_end": self.actual_end.isoformat() if self.actual_end else None,
            "error_message": self.error_message,
        }


@dataclass
class VehicleDuty:
    """Represents sequential trips assigned to a single vehicle."""
    vehicle_id: str
    vehicle_number: str
    vehicle_type: str = "BUS"
    trips: List[ScheduledTrip] = field(default_factory=list)
    state: VehicleOperationalState = VehicleOperationalState.IDLE

    @property
    def trip_count(self) -> int:
        return len(self.trips)

    @property
    def first_departure(self) -> Optional[datetime]:
        return self.trips[0].planned_start if self.trips else None

    @property
    def final_arrival(self) -> Optional[datetime]:
        return self.trips[-1].planned_end if (self.trips and self.trips[-1].planned_end) else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "vehicle_number": self.vehicle_number,
            "vehicle_type": self.vehicle_type,
            "trip_count": self.trip_count,
            "state": self.state.value,
            "first_departure": self.first_departure.isoformat() if self.first_departure else None,
            "final_arrival": self.final_arrival.isoformat() if self.final_arrival else None,
            "trips": [t.to_dict() for t in self.trips],
        }


@dataclass
class OperatorDuty:
    """Represents participation of an operator identity in the day plan."""
    operator_code: str
    operator_name: str = "Operator"
    trips: List[ScheduledTrip] = field(default_factory=list)

    @property
    def trip_count(self) -> int:
        return len(self.trips)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator_code": self.operator_code,
            "operator_name": self.operator_name,
            "trip_count": self.trip_count,
            "assigned_trip_ids": [t.trip_id for t in self.trips],
        }


@dataclass
class ServiceDayEvent:
    """Deterministic timeline event dispatched by the service-day scheduler."""
    event_id: str
    event_type: ServiceDayEventType
    sim_time_offset_s: float
    sim_datetime: datetime
    target_vehicle_id: Optional[str] = None
    target_trip_id: Optional[str] = None
    target_operator_code: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    executed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "sim_time_offset_s": self.sim_time_offset_s,
            "sim_datetime": self.sim_datetime.isoformat(),
            "target_vehicle_id": self.target_vehicle_id,
            "target_trip_id": self.target_trip_id,
            "target_operator_code": self.target_operator_code,
            "payload": self.payload,
            "executed": self.executed,
        }


@dataclass
class ServiceCoverageSummary:
    """Coverage and schedule metrics for a specific service."""
    service_id: str
    service_code: str
    service_name: str
    route_id: str
    direction: str
    first_departure: datetime
    final_departure: datetime
    trip_count: int
    headway_minutes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "service_code": self.service_code,
            "service_name": self.service_name,
            "route_id": self.route_id,
            "direction": self.direction,
            "first_departure": self.first_departure.isoformat(),
            "final_departure": self.final_departure.isoformat(),
            "trip_count": self.trip_count,
            "headway_minutes": self.headway_minutes,
        }


@dataclass
class FleetCoverageSummary:
    """Fleet utilization metrics across the operating day."""
    total_vehicles: int
    active_vehicles_with_duties: int
    idle_vehicles_without_duties: int
    max_simultaneous_vehicles: int
    total_scheduled_trips: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_vehicles": self.total_vehicles,
            "active_vehicles_with_duties": self.active_vehicles_with_duties,
            "idle_vehicles_without_duties": self.idle_vehicles_without_duties,
            "max_simultaneous_vehicles": self.max_simultaneous_vehicles,
            "total_scheduled_trips": self.total_scheduled_trips,
        }


@dataclass
class ServiceDayPlan:
    """Master immutable domain plan for an entire GoBus transit day."""
    service_date: str  # YYYY-MM-DD
    timezone_name: str = "Asia/Kolkata"
    vehicle_duties: Dict[str, VehicleDuty] = field(default_factory=dict)
    operator_duties: Dict[str, OperatorDuty] = field(default_factory=dict)
    trips: List[ScheduledTrip] = field(default_factory=list)
    events: List[ServiceDayEvent] = field(default_factory=list)
    fleet_coverage: Optional[FleetCoverageSummary] = None
    service_coverages: List[ServiceCoverageSummary] = field(default_factory=list)
    state: ServiceDayState = ServiceDayState.DAY_READY
    first_departure: Optional[datetime] = None
    final_arrival: Optional[datetime] = None
    total_duration_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Safe export containing zero passwords, JWTs, or secrets."""
        return {
            "service_date": self.service_date,
            "timezone": self.timezone_name,
            "state": self.state.value,
            "total_duration_s": self.total_duration_s,
            "first_departure": self.first_departure.isoformat() if self.first_departure else None,
            "final_arrival": self.final_arrival.isoformat() if self.final_arrival else None,
            "fleet_coverage": self.fleet_coverage.to_dict() if self.fleet_coverage else None,
            "service_coverages": [sc.to_dict() for sc in self.service_coverages],
            "vehicle_duties": {vid: vd.to_dict() for vid, vd in self.vehicle_duties.items()},
            "operator_duties": {op: od.to_dict() for op, od in self.operator_duties.items()},
            "trips": [t.to_dict() for t in self.trips],
            "events_count": len(self.events),
        }
