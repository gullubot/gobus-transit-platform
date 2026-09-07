"""
Transit Platform — Individual Simulated Bus Context.

Encapsulates complete runtime state, credentials, API client, trip assignment,
movement engine, and telemetry generator for a single virtual operator device.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from simulator.api.assignment import fetch_operator_assignment
from simulator.api.auth import operator_login, operator_logout
from simulator.api.client import GoBusHttpClient
from simulator.api.crowding import submit_crowding_report
from simulator.api.heartbeat import send_device_heartbeat
from simulator.api.route import fetch_service_route
from simulator.api.telemetry import BatchAckResult, send_telemetry_batch
from simulator.api.trip import end_trip_tracking, start_trip_tracking
from simulator.config.settings import OperatorCredentials
from simulator.core.clock import SimulationClock
from simulator.core.exceptions import (
    AssignmentNotFoundError,
    AuthenticationError,
    SimulatorError,
)
from simulator.core.movement import MovementEngine, MovementState
from simulator.core.route import RouteModel
from simulator.core.scenario import BusConfig
from simulator.core.session import AssignmentContext, OperatorSession
from simulator.core.telemetry_generator import TelemetryGenerator
from simulator.utils.logging import get_logger

logger = get_logger("bus_sim")


class BusLifecycle(str, Enum):
    """Lifecycle states of a simulated bus context."""
    CREATED = "CREATED"
    AUTHENTICATED = "AUTHENTICATED"
    ASSIGNED = "ASSIGNED"
    TRIP_STARTED = "TRIP_STARTED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class BusSimulator:
    """
    Simulates a single physical Android operator device.
    Maintains private network session, token, sequence counter, and movement state.
    """

    def __init__(
        self,
        config: BusConfig,
        backend_url: str,
        request_timeout: float = 10.0,
    ):
        self.config = config
        self.bus_id = config.bus_id
        self.lifecycle = BusLifecycle.CREATED
        self.error_message: Optional[str] = None

        # Dedicated isolated HTTP client and operator session
        self.client = GoBusHttpClient(base_url=backend_url, timeout=request_timeout)
        self.session = OperatorSession(employee_code=config.employee_code)

        # Simulation models
        self.assignment: Optional[AssignmentContext] = None
        self.route: Optional[RouteModel] = None
        self.clock = SimulationClock(time_multiplier=config.time_multiplier)
        self.movement: Optional[MovementEngine] = None
        self.telemetry_gen = TelemetryGenerator(
            session=self.session,
            clock=self.clock,
            initial_battery=config.initial_battery,
        )

        # Modifiers and switches
        self.current_speed_mps = config.speed_mps
        self.base_speed_mps = config.speed_mps
        self.time_multiplier = config.time_multiplier
        self.dwell_seconds = config.dwell_seconds
        self.telemetry_enabled: bool = True
        self.heartbeat_enabled: bool = True
        self.gps_status = config.gps_status
        self.network_type = config.network_type

        # Statistics
        self.packets_sent: int = 0
        self.packets_accepted: int = 0
        self.packets_rejected: int = 0
        self.last_heartbeat_sim_time: float = 0.0

    @property
    def is_active(self) -> bool:
        """True if bus is running or paused."""
        return self.lifecycle in (BusLifecycle.RUNNING, BusLifecycle.PAUSED)

    def initialize_backend(self) -> None:
        """
        Executes setup sequence: Login -> Assignment -> Route -> Start Trip.
        Isolated per bus; raises specific errors on failure without corrupting fleet.
        """
        try:
            # 1. Login
            self.lifecycle = BusLifecycle.CREATED
            logger.info(f"[{self.bus_id}] Authenticating operator {self.session.employee_code}...")
            operator_login(self.client, self.session, self.config.password)
            self.lifecycle = BusLifecycle.AUTHENTICATED

            # 2. Assignment
            logger.info(f"[{self.bus_id}] Discovering duty assignment...")
            self.assignment = fetch_operator_assignment(self.client, self.session)
            self.lifecycle = BusLifecycle.ASSIGNED

            # 3. Route
            direction = self.assignment.direction or self.config.direction
            logger.info(f"[{self.bus_id}] Loading route for service {self.assignment.service_code} ({direction})...")
            self.route = fetch_service_route(
                client=self.client,
                service_id=self.assignment.service_id,
                organization_id=self.session.organization_id or "",
                direction=direction,
            )

            # 4. Start Trip
            logger.info(f"[{self.bus_id}] Starting trip tracking session for trip {self.assignment.trip_id}...")
            start_resp = start_trip_tracking(self.client, self.session)
            self.lifecycle = BusLifecycle.TRIP_STARTED

            # 5. Initialize Movement Engine
            self.movement = MovementEngine(
                route=self.route,
                cruise_speed_mps=self.current_speed_mps,
                dwell_duration_seconds=self.dwell_seconds,
                enable_noise=self.config.enable_noise,
                random_seed=self.config.random_seed,
            )
            self.lifecycle = BusLifecycle.RUNNING
            logger.info(f"[{self.bus_id}] Bus initialized successfully on route {self.route.route_code}.")

        except Exception as e:
            self.lifecycle = BusLifecycle.ERROR
            self.error_message = str(e)
            logger.error(f"[{self.bus_id}] Initialization failed: {e}")
            raise

    def step(self, delta_real_seconds: float) -> Optional[Dict[str, Any]]:
        """
        Advances the simulated bus by delta_real_seconds.
        Updates clock, moves along route, and returns generated packet if telemetry is enabled.
        """
        if self.lifecycle != BusLifecycle.RUNNING or not self.movement:
            return None

        # Advance clock and movement
        sim_time = self.clock.tick(delta_real_seconds)
        delta_sim = delta_real_seconds * self.clock.time_multiplier
        state = self.movement.advance(delta_sim)

        # Check route completion
        if self.movement.is_completed:
            self.lifecycle = BusLifecycle.COMPLETED
            logger.info(f"[{self.bus_id}] Reached final route destination '{self.route.stops[-1].stop_name}'.")

        # Telemetry generation
        if not self.telemetry_enabled:
            return None

        packet = self.telemetry_gen.generate_packet(
            state=state,
            gps_status=self.gps_status,
            network_type=self.network_type,
        )
        return packet

    def transmit_packet(self, packet: Dict[str, Any]) -> BatchAckResult:
        """Transmits a telemetry packet to the real backend."""
        self.packets_sent += 1
        try:
            ack = send_telemetry_batch(self.client, self.session, [packet])
            self.packets_accepted += len(ack.accepted) + len(ack.duplicates)
            self.packets_rejected += len(ack.rejected)
            return ack
        except Exception as e:
            self.packets_rejected += 1
            logger.warning(f"[{self.bus_id}] Telemetry transmission failed: {e}")
            raise

    def check_and_send_heartbeat(self, interval_sim_seconds: float = 30.0) -> bool:
        """Sends device heartbeat if interval has elapsed and heartbeat is enabled."""
        if not self.heartbeat_enabled or not self.session.active_tracking_session_id:
            return False

        current_sim_time = self.clock.elapsed_sim_seconds
        if current_sim_time - self.last_heartbeat_sim_time >= interval_sim_seconds:
            try:
                battery = self.telemetry_gen.current_battery_level()
                send_device_heartbeat(
                    client=self.client,
                    session=self.session,
                    battery_level=battery,
                    network_type=self.network_type,
                    gps_status=self.gps_status,
                )
                self.last_heartbeat_sim_time = current_sim_time
                return True
            except Exception as e:
                logger.debug(f"[{self.bus_id}] Heartbeat error: {e}")
                return False
        return False

    def submit_crowding(self, crowding_state: str, confidence: float = 0.85) -> Dict[str, Any]:
        """Submits an operator-sourced crowding report."""
        if not self.assignment:
            raise SimulatorError("Cannot submit crowding report: no active duty assignment")

        logger.info(f"[{self.bus_id}] Submitting crowding report: {crowding_state} (Confidence: {confidence:.2f})")
        return submit_crowding_report(
            client=self.client,
            session=self.session,
            crowding_state=crowding_state,
            confidence=confidence,
            observed_at=self.clock.current_time,
        )

    def set_speed(self, speed_mps: float) -> None:
        """Sets the current bus cruise speed (used in delay scenarios)."""
        self.current_speed_mps = max(0.5, speed_mps)
        if self.movement:
            self.movement.cruise_speed_mps = self.current_speed_mps
        logger.info(f"[{self.bus_id}] Speed modified to {self.current_speed_mps:.1f} m/s")

    def restore_speed(self) -> None:
        """Restores the configured base speed."""
        self.set_speed(self.base_speed_mps)

    def pause(self) -> None:
        """Pauses bus simulation."""
        if self.lifecycle == BusLifecycle.RUNNING:
            self.lifecycle = BusLifecycle.PAUSED
            self.clock.pause()
            logger.info(f"[{self.bus_id}] Bus simulation paused.")

    def resume(self) -> None:
        """Resumes bus simulation."""
        if self.lifecycle == BusLifecycle.PAUSED:
            self.lifecycle = BusLifecycle.RUNNING
            self.clock.resume()
            logger.info(f"[{self.bus_id}] Bus simulation resumed.")

    def stop(self) -> None:
        """Stops simulation and cleans up the active tracking session."""
        if self.lifecycle in (BusLifecycle.RUNNING, BusLifecycle.PAUSED, BusLifecycle.TRIP_STARTED):
            logger.info(f"[{self.bus_id}] Ending active trip session...")
            try:
                end_trip_tracking(self.client, self.session)
            except Exception as e:
                logger.warning(f"[{self.bus_id}] Error ending trip during stop: {e}")
        self.lifecycle = BusLifecycle.STOPPED
        operator_logout(self.session)
        self.client.close()

    def emergency_cleanup(self) -> None:
        """Failsafe emergency cleanup attempting to end trip session without throwing."""
        try:
            if self.session.active_tracking_session_id:
                end_trip_tracking(self.client, self.session)
        except Exception:
            pass
        finally:
            self.lifecycle = BusLifecycle.STOPPED
            operator_logout(self.session)
            self.client.close()

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns safe operational snapshot without secrets."""
        m_state = self.movement.get_state() if self.movement else None
        return {
            "bus_id": self.bus_id,
            "employee_code": self.session.employee_code,
            "lifecycle": self.lifecycle.value,
            "speed_mps": m_state.current_speed_mps if m_state else 0.0,
            "heading": m_state.current_heading if m_state else 0.0,
            "lat": m_state.current_latitude if m_state else None,
            "lon": m_state.current_longitude if m_state else None,
            "is_dwelling": m_state.is_dwelling if m_state else False,
            "dwell_remaining_s": m_state.dwell_time_remaining_s if m_state else 0.0,
            "progress_m": m_state.total_progress_m if m_state else 0.0,
            "total_m": self.route.total_distance_m if self.route else 0.0,
            "current_stop": m_state.current_stop.stop_name if m_state else "N/A",
            "next_stop": m_state.next_stop.stop_name if (m_state and m_state.next_stop) else "DESTINATION",
            "packets_sent": self.packets_sent,
            "packets_accepted": self.packets_accepted,
            "packets_rejected": self.packets_rejected,
            "telemetry_enabled": self.telemetry_enabled,
            "heartbeat_enabled": self.heartbeat_enabled,
            "error": self.error_message,
        }
