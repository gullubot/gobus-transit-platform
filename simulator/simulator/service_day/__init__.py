"""
Transit Platform — Service-Day Planning & Execution Package.

BUILD 4 Phase 5B: Full-Fleet Full-Day Transit Simulation Foundation.
"""

from simulator.service_day.models import (
    ServiceDayState,
    TripExecutionState,
    VehicleOperationalState,
    ServiceDayEventType,
    ScheduledTrip,
    VehicleDuty,
    OperatorDuty,
    ServiceDayEvent,
    ServiceCoverageSummary,
    FleetCoverageSummary,
    ServiceDayPlan,
)
from simulator.service_day.clock import ServiceDayClock
from simulator.service_day.timestamp_strategy import (
    BackendTimestampStrategy,
    LiveTimestampStrategy,
    SimulatedTimestampStrategy,
)
from simulator.service_day.manifest import (
    ServiceDayManifest,
    load_manifest,
    create_default_manifest,
)
from simulator.service_day.planner import (
    ServiceDayPlanner,
    PlanValidationError,
)
from simulator.service_day.scheduler import ServiceDayScheduler
from simulator.service_day.executor import ServiceDayExecutor, VehicleDutyExecutor

__all__ = [
    "ServiceDayState",
    "TripExecutionState",
    "VehicleOperationalState",
    "ServiceDayEventType",
    "ScheduledTrip",
    "VehicleDuty",
    "OperatorDuty",
    "ServiceDayEvent",
    "ServiceCoverageSummary",
    "FleetCoverageSummary",
    "ServiceDayPlan",
    "ServiceDayClock",
    "BackendTimestampStrategy",
    "LiveTimestampStrategy",
    "SimulatedTimestampStrategy",
    "ServiceDayManifest",
    "load_manifest",
    "create_default_manifest",
    "ServiceDayPlanner",
    "PlanValidationError",
    "ServiceDayScheduler",
    "ServiceDayExecutor",
    "VehicleDutyExecutor",
]
