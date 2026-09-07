"""
Transit Platform — Deterministic Scenario and Event Definitions.

Provides event structures and scenario models to orchestrate repeatable operational conditions
(normal operations, delay, stale/offline, crowding, and service shortage) without mutating backend logic.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class BusConfig:
    """Configuration for an individual simulated bus in a scenario."""
    bus_id: str
    employee_code: str
    password: str
    direction: str = "A_TO_B"
    speed_mps: float = 8.33
    time_multiplier: float = 1.0
    tick_seconds: float = 1.0
    dwell_seconds: float = 15.0
    start_offset_seconds: float = 0.0
    enable_noise: bool = False
    random_seed: Optional[int] = None
    initial_battery: float = 98.0
    network_type: str = "CELLULAR"
    gps_status: str = "AVAILABLE"


class ScenarioEventType(str, Enum):
    """Types of timeline events that can modify simulated bus behavior."""
    START_BUS = "START_BUS"
    STOP_BUS = "STOP_BUS"
    PAUSE_BUS = "PAUSE_BUS"
    RESUME_BUS = "RESUME_BUS"
    SET_SPEED = "SET_SPEED"
    RESTORE_SPEED = "RESTORE_SPEED"
    SET_CROWDING = "SET_CROWDING"
    SET_TELEMETRY_ENABLED = "SET_TELEMETRY_ENABLED"
    SET_HEARTBEAT_ENABLED = "SET_HEARTBEAT_ENABLED"
    SET_NETWORK_TYPE = "SET_NETWORK_TYPE"
    SET_GPS_STATUS = "SET_GPS_STATUS"


@dataclass
class ScenarioEvent:
    """Individual deterministic event scheduled at a specific simulation time offset."""
    sim_time_offset_s: float
    event_type: ScenarioEventType
    target_bus_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sim_time_offset_s < 0:
            raise ValueError(f"sim_time_offset_s cannot be negative, got {self.sim_time_offset_s}")
        if isinstance(self.event_type, str):
            self.event_type = ScenarioEventType(self.event_type)


@dataclass
class ScenarioDefinition:
    """Full scenario specification containing participating buses and scheduled events."""
    name: str
    description: str
    buses: List[BusConfig]
    events: List[ScenarioEvent] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    random_seed: Optional[int] = 42

    def __post_init__(self) -> None:
        if not self.buses:
            raise ValueError("Scenario must define at least 1 bus")
        # Ensure events are sorted chronologically
        self.events = sorted(self.events, key=lambda e: e.sim_time_offset_s)
