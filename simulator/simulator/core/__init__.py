"""Core domain models and exceptions for GoBus Simulator."""
from simulator.core.clock import SimulationClock
from simulator.core.exceptions import (
    AccountForbiddenError,
    AssignmentNotFoundError,
    AuthenticationError,
    BackendUnavailableError,
    InvalidPayloadError,
    RateLimitExceededError,
    SimulatorError,
    TelemetryBatchError,
    TripSessionError,
)
from simulator.core.geo import calculate_bearing, haversine_distance, interpolate_point
from simulator.core.movement import MovementEngine, MovementState
from simulator.core.route import RouteModel, RouteSegment, SimulatedStop
from simulator.core.scenario import ScenarioDefinition, ScenarioEvent, ScenarioEventType
from simulator.core.session import AssignmentContext, OperatorSession, SimulationMode

__all__ = [
    "SimulatorError",
    "BackendUnavailableError",
    "AuthenticationError",
    "AccountForbiddenError",
    "AssignmentNotFoundError",
    "TripSessionError",
    "TelemetryBatchError",
    "RateLimitExceededError",
    "InvalidPayloadError",
    "SimulationMode",
    "AssignmentContext",
    "OperatorSession",
    "haversine_distance",
    "calculate_bearing",
    "interpolate_point",
    "SimulatedStop",
    "RouteSegment",
    "RouteModel",
    "SimulationClock",
    "MovementEngine",
    "MovementState",
    "ScenarioEventType",
    "ScenarioEvent",
    "ScenarioDefinition",
]
