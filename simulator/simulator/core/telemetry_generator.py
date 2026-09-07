"""
Transit Platform — Movement-to-Telemetry Generator.

Translates the simulated movement state and simulation clock into verified
GoBus tracking packets matching the exact POST /api/tracking/batch schema.
"""

from typing import Any, Dict, Optional

from simulator.api.telemetry import create_telemetry_packet
from simulator.core.clock import SimulationClock
from simulator.core.movement import MovementState
from simulator.core.session import OperatorSession


class TelemetryGenerator:
    """
    Constructs sensor-style telemetry packets from physical simulation state.
    Never adds vehicle_id or route_id (backend resolves from session).
    """

    def __init__(
        self,
        session: OperatorSession,
        clock: SimulationClock,
        initial_battery: float = 98.0,
        battery_decay_rate_per_min: float = 0.05,
        default_accuracy_m: float = 5.0,
    ):
        self.session = session
        self.clock = clock
        self.initial_battery = float(initial_battery)
        self.battery_decay_rate_per_min = float(battery_decay_rate_per_min)
        self.default_accuracy_m = float(default_accuracy_m)

    def current_battery_level(self) -> float:
        """Calculates realistic battery level based on elapsed simulated time."""
        elapsed_mins = self.clock.elapsed_sim_seconds / 60.0
        battery = self.initial_battery - (elapsed_mins * self.battery_decay_rate_per_min)
        return max(5.0, min(100.0, round(battery, 1)))

    def generate_packet(
        self,
        state: MovementState,
        accuracy_m: Optional[float] = None,
        gps_status: str = "AVAILABLE",
        network_type: str = "CELLULAR",
    ) -> Dict[str, Any]:
        """
        Generates a validated telemetry packet for the current tick.
        Increments the operator session's monotonic sequence counter.
        """
        seq = self.session.next_sequence()
        battery = self.current_battery_level()
        acc = accuracy_m if accuracy_m is not None else self.default_accuracy_m

        packet = create_telemetry_packet(
            latitude=state.current_latitude,
            longitude=state.current_longitude,
            device_sequence=seq,
            speed_mps=state.current_speed_mps,
            heading=state.current_heading,
            accuracy_m=acc,
            observed_at=self.clock.current_time,
            battery_level=battery,
            network_type=network_type,
            gps_status=gps_status,
        )

        # Invariant assertion
        assert "vehicle_id" not in packet, "CRITICAL: vehicle_id must not be sent in telemetry packet"
        assert "route_id" not in packet, "CRITICAL: route_id must not be sent in telemetry packet"
        assert "service_id" not in packet, "CRITICAL: service_id must not be sent in telemetry packet"

        return packet
