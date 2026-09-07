"""
Transit Platform — Service-Day Execution Engine.

BUILD 4 Phase 5C: Orchestrates full-fleet live transit operations against the real GoBus backend,
driving sequential trips per vehicle, handling terminus layovers, enforcing current timestamps,
and isolating errors across vehicles.
"""

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from simulator.config.settings import Settings
from simulator.core.bus_simulator import BusConfig, BusLifecycle, BusSimulator
from simulator.service_day.clock import ServiceDayClock
from simulator.service_day.models import (
    ScheduledTrip,
    ServiceDayPlan,
    ServiceDayState,
    TripExecutionState,
    VehicleDuty,
    VehicleOperationalState,
)
from simulator.service_day.timestamp_strategy import (
    BackendTimestampStrategy,
    LiveTimestampStrategy,
    SimulatedTimestampStrategy,
)
from simulator.utils.logging import get_logger

logger = get_logger("service_day.executor")

KNOWN_OPERATOR_PASSWORDS = {
    "O-001": "Password123!",
    "O-002": "Password123!",
    "O-003": "Password123!",
    "DRV001": "operator123",
    "DRV002": "operator123",
    "DRV003": "operator123",
    "DRV004": "operator123",
}


class VehicleDutyExecutor:
    """
    Manages the sequential operational lifecycle of a single vehicle across the service day.
    """

    def __init__(
        self,
        duty: VehicleDuty,
        settings: Settings,
        dry_run: bool = False,
    ):
        self.duty = duty
        self.settings = settings
        self.dry_run = dry_run

        self.current_trip_index: int = 0
        self.current_bus_simulator: Optional[BusSimulator] = None
        self.state: VehicleOperationalState = VehicleOperationalState.IDLE

        # Statistics
        self.trips_completed_count: int = 0
        self.trips_failed_count: int = 0
        self.packets_sent: int = 0
        self.packets_accepted: int = 0
        self.heartbeats_sent: int = 0
        self.last_error: Optional[str] = None

    @property
    def current_trip(self) -> Optional[ScheduledTrip]:
        if 0 <= self.current_trip_index < len(self.duty.trips):
            return self.duty.trips[self.current_trip_index]
        return None

    @property
    def is_duty_completed(self) -> bool:
        return self.current_trip_index >= len(self.duty.trips)

    def tick(
        self,
        sim_datetime: datetime,
        real_delta_seconds: float,
        clock: ServiceDayClock,
        timestamp_strategy: BackendTimestampStrategy,
    ) -> None:
        """
        Executes one time-step for this vehicle.
        Handles pending trip dispatch, active route movement, telemetry, and layovers.
        """
        if self.is_duty_completed:
            self.state = VehicleOperationalState.IDLE
            return

        trip = self.current_trip
        if not trip:
            return

        # ── State 1: IDLE or LAYOVER (Waiting for planned departure) ─────────
        if self.state in (VehicleOperationalState.IDLE, VehicleOperationalState.LAYOVER):
            if trip.state == TripExecutionState.PENDING:
                if sim_datetime >= trip.planned_start:
                    self._start_trip(trip, clock)
            return

        # ── State 2: RUNNING (Active trip execution) ─────────────────────────
        if self.state == VehicleOperationalState.RUNNING:
            if self.dry_run:
                # In dry-run mode, complete trip when simulated time passes planned_end
                end_time = trip.planned_end or trip.planned_start
                if sim_datetime >= end_time:
                    self._complete_trip(trip, clock)
            else:
                sim = self.current_bus_simulator
                if not sim:
                    self._fail_trip(trip, "Active simulator missing during RUNNING state")
                    return

                try:
                    # 1. Physical movement step
                    packet = sim.step(real_delta_seconds)

                    # 2. Telemetry transmission with LiveTimestampStrategy
                    if packet:
                        live_ts = timestamp_strategy.get_telemetry_timestamp(clock)
                        packet["observed_at"] = live_ts.isoformat()
                        ack = sim.transmit_packet(packet)
                        self.packets_sent += 1
                        self.packets_accepted += len(ack.accepted) + len(ack.duplicates)

                    # 3. Heartbeat check
                    if sim.check_and_send_heartbeat(interval_sim_seconds=30.0):
                        self.heartbeats_sent += 1

                    # 4. Check route completion
                    if sim.lifecycle == BusLifecycle.COMPLETED or (sim.movement and sim.movement.is_completed):
                        self._complete_trip(trip, clock)
                    elif sim.lifecycle == BusLifecycle.ERROR:
                        self._fail_trip(trip, sim.error_message or "Bus movement failed")

                except Exception as e:
                    logger.exception(f"[{self.duty.vehicle_number}] Error during trip tick: {e}")
                    self._fail_trip(trip, str(e))

    def _start_trip(self, trip: ScheduledTrip, clock: ServiceDayClock) -> None:
        """Initializes and dispatches the scheduled trip."""
        logger.info(
            f"[{self.duty.vehicle_number}] Starting Trip {trip.trip_id[:8]}... "
            f"({trip.service_code} {trip.direction}) [Operator: {trip.operator_code}]"
        )
        self.state = VehicleOperationalState.PREPARING
        trip.state = TripExecutionState.STARTING
        trip.actual_start = clock.current_simulated_datetime

        if self.dry_run:
            trip.state = TripExecutionState.RUNNING
            self.state = VehicleOperationalState.RUNNING
            return

        # Live Backend Execution
        password = KNOWN_OPERATOR_PASSWORDS.get(trip.operator_code, self.settings.operator_password or "Password123!")
        speed_mps = getattr(self.settings, "default_speed_mps", 8.33)
        dwell_seconds = getattr(self.settings, "default_dwell_seconds", 15.0)
        timeout_s = getattr(self.settings, "request_timeout", 10.0)

        b_cfg = BusConfig(
            bus_id=f"bus-{self.duty.vehicle_number}",
            employee_code=trip.operator_code,
            password=password,
            speed_mps=speed_mps,
            time_multiplier=clock.time_multiplier,
            dwell_seconds=dwell_seconds,
            direction=trip.direction,
        )

        sim = BusSimulator(
            config=b_cfg,
            backend_url=self.settings.backend_url,
            request_timeout=timeout_s,
        )

        try:
            sim.initialize_backend()
            self.current_bus_simulator = sim
            trip.state = TripExecutionState.RUNNING
            self.state = VehicleOperationalState.RUNNING
            logger.info(f"[{self.duty.vehicle_number}] Live trip {trip.trip_id[:8]} started on backend.")
        except Exception as e:
            logger.error(f"[{self.duty.vehicle_number}] Failed to start live trip {trip.trip_id[:8]}: {e}")
            self._fail_trip(trip, str(e))

    def _complete_trip(self, trip: ScheduledTrip, clock: ServiceDayClock) -> None:
        """Completes the trip and cleanly transitions vehicle to terminus layover."""
        logger.info(f"[{self.duty.vehicle_number}] Completed Trip {trip.trip_id[:8]} ({trip.service_code}).")
        trip.state = TripExecutionState.ENDING

        if not self.dry_run and self.current_bus_simulator:
            try:
                self.current_bus_simulator.stop()
            except Exception as e:
                logger.warning(f"[{self.duty.vehicle_number}] Warning stopping trip: {e}")

        trip.state = TripExecutionState.COMPLETED
        trip.actual_end = clock.current_simulated_datetime
        self.trips_completed_count += 1
        self.current_bus_simulator = None

        # Advance sequential trip index
        self.current_trip_index += 1

        if self.current_trip:
            # More trips remain: Enter terminus layover
            self.state = VehicleOperationalState.LAYOVER
            logger.info(
                f"[{self.duty.vehicle_number}] Terminus layover started. "
                f"Next trip {self.current_trip.trip_id[:8]} scheduled at {self.current_trip.planned_start}."
            )
        else:
            # All duties finished
            self.state = VehicleOperationalState.IDLE
            logger.info(f"[{self.duty.vehicle_number}] All {len(self.duty.trips)} scheduled duties completed.")

    def _fail_trip(self, trip: ScheduledTrip, error_msg: str) -> None:
        """Handles trip failure while protecting other duties."""
        logger.error(f"[{self.duty.vehicle_number}] Trip {trip.trip_id[:8]} failed: {error_msg}")
        trip.state = TripExecutionState.ERROR
        trip.error_message = error_msg
        self.trips_failed_count += 1
        self.last_error = error_msg

        if not self.dry_run and self.current_bus_simulator:
            try:
                self.current_bus_simulator.emergency_cleanup()
            except Exception:
                pass

        self.current_bus_simulator = None
        self.current_trip_index += 1

        # Leave in LAYOVER so subsequent scheduled trips can still attempt execution
        if self.current_trip:
            self.state = VehicleOperationalState.LAYOVER
        else:
            self.state = VehicleOperationalState.ERROR

    def stop(self) -> None:
        """Stops active simulator and cleans up resources."""
        if self.current_bus_simulator:
            try:
                self.current_bus_simulator.stop()
            except Exception:
                pass
            self.current_bus_simulator = None
        self.state = VehicleOperationalState.IDLE

    def get_status(self) -> Dict[str, Any]:
        """Returns runtime status dictionary for this vehicle."""
        curr_trip = self.current_trip
        sim = self.current_bus_simulator
        progress_m = sim.movement.distance_covered_m if (sim and sim.movement) else 0.0
        route_dist_m = sim.route.total_distance_m if (sim and sim.route) else 0.0
        pct = round((progress_m / route_dist_m * 100.0), 1) if route_dist_m > 0 else 0.0

        return {
            "vehicle_id": self.duty.vehicle_id,
            "vehicle_number": self.duty.vehicle_number,
            "vehicle_type": self.duty.vehicle_type,
            "state": self.state.value,
            "current_trip_index": self.current_trip_index,
            "total_trips": len(self.duty.trips),
            "current_trip_id": curr_trip.trip_id if curr_trip else None,
            "current_service": curr_trip.service_code if curr_trip else None,
            "current_operator": curr_trip.operator_code if curr_trip else None,
            "progress_percent": pct,
            "packets_sent": self.packets_sent,
            "packets_accepted": self.packets_accepted,
            "heartbeats_sent": self.heartbeats_sent,
            "last_error": self.last_error,
        }


class ServiceDayExecutor:
    """
    Central orchestration engine for executing a full-day, multi-bus transit schedule.
    """

    def __init__(
        self,
        plan: ServiceDayPlan,
        settings: Optional[Settings] = None,
        dry_run: bool = False,
        timestamp_strategy: Optional[BackendTimestampStrategy] = None,
    ):
        self.plan = plan
        self.settings = settings or Settings()
        self.dry_run = dry_run

        # Initialize Simulation Clock
        first_time_str = "05:00:00"
        if plan.first_departure:
            first_time_str = plan.first_departure.strftime("%H:%M:%S")

        self.clock = ServiceDayClock(
            service_date=datetime.strptime(plan.service_date, "%Y-%m-%d").date(),
            start_time_of_day=first_time_str,
            timezone_name=plan.timezone_name,
            time_multiplier=self.settings.time_multiplier if hasattr(self.settings, "time_multiplier") else 1.0,
        )

        # Enforce live timestamp strategy
        if timestamp_strategy:
            self.timestamp_strategy = timestamp_strategy
        elif dry_run:
            self.timestamp_strategy = SimulatedTimestampStrategy()
        else:
            self.timestamp_strategy = LiveTimestampStrategy()

        # Vehicle executors
        self.vehicle_executors: Dict[str, VehicleDutyExecutor] = {
            vid: VehicleDutyExecutor(duty=vd, settings=self.settings, dry_run=self.dry_run)
            for vid, vd in plan.vehicle_duties.items()
        }

        self.state = ServiceDayState.DAY_READY
        self.ticks_executed: int = 0
        self.start_wall_time: Optional[float] = None
        self._lock = threading.RLock()

    @property
    def is_completed(self) -> bool:
        """True when all vehicle executors have completed all scheduled duties."""
        return all(ve.is_duty_completed for ve in self.vehicle_executors.values())

    def start(self) -> None:
        """Begins execution of the full-day service."""
        with self._lock:
            if self.state == ServiceDayState.DAY_RUNNING:
                return
            self.state = ServiceDayState.DAY_RUNNING
            self.start_wall_time = time.time()
            logger.info(
                f"ServiceDayExecutor started: {len(self.vehicle_executors)} vehicles, "
                f"{len(self.plan.trips)} trips (Dry-Run={self.dry_run})."
            )

    def pause(self) -> None:
        """Pauses service day execution."""
        with self._lock:
            if self.state == ServiceDayState.DAY_RUNNING:
                self.state = ServiceDayState.DAY_PAUSED
                self.clock.pause()
                for ve in self.vehicle_executors.values():
                    if ve.current_bus_simulator:
                        ve.current_bus_simulator.pause()
                logger.info("ServiceDayExecutor paused.")

    def resume(self) -> None:
        """Resumes service day execution."""
        with self._lock:
            if self.state == ServiceDayState.DAY_PAUSED:
                self.state = ServiceDayState.DAY_RUNNING
                self.clock.resume()
                for ve in self.vehicle_executors.values():
                    if ve.current_bus_simulator:
                        ve.current_bus_simulator.resume()
                logger.info("ServiceDayExecutor resumed.")

    def stop(self) -> None:
        """Gracefully stops all active vehicle duties and trips."""
        with self._lock:
            self.state = ServiceDayState.DAY_STOPPING
            logger.info("Stopping ServiceDayExecutor and shutting down vehicles...")
            for ve in self.vehicle_executors.values():
                ve.stop()
            self.state = ServiceDayState.DAY_COMPLETED
            self.clock.mark_completed()
            logger.info("ServiceDayExecutor stopped.")

    def step(self, real_delta_seconds: float = 1.0) -> None:
        """Advances the service day by real_delta_seconds across all vehicles."""
        with self._lock:
            if self.state != ServiceDayState.DAY_RUNNING:
                return

            # Advance clock
            self.clock.advance(real_delta_seconds)
            self.ticks_executed += 1
            sim_dt = self.clock.current_simulated_datetime

            # Tick each vehicle executor
            for ve in self.vehicle_executors.values():
                ve.tick(
                    sim_datetime=sim_dt,
                    real_delta_seconds=real_delta_seconds,
                    clock=self.clock,
                    timestamp_strategy=self.timestamp_strategy,
                )

            # Check for total completion
            if self.is_completed:
                self.state = ServiceDayState.DAY_COMPLETED
                self.clock.mark_completed()
                logger.info("All vehicle duties completed. ServiceDayExecutor finished.")

    def run_live(
        self,
        max_duration_seconds: Optional[float] = None,
        max_trips: Optional[int] = None,
        tick_seconds: float = 1.0,
        max_simulated_minutes: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Runs the central deterministic execution loop until completion or threshold reached.
        """
        self.start()
        start_t = time.time()
        effective_tick = tick_seconds if tick_seconds > 0 else (60.0 if self.dry_run else 1.0)

        while not self.is_completed and self.state == ServiceDayState.DAY_RUNNING:
            self.step(effective_tick)

            now_t = time.time()
            elapsed_wall = now_t - start_t

            # Threshold checks
            if max_duration_seconds and elapsed_wall >= max_duration_seconds:
                logger.info(f"Max wall-clock duration ({max_duration_seconds}s) reached.")
                break

            if max_simulated_minutes and (self.clock.elapsed_service_seconds / 60.0) >= max_simulated_minutes:
                logger.info(f"Max simulated minutes ({max_simulated_minutes}m) reached.")
                break

            if max_trips:
                completed = sum(ve.trips_completed_count for ve in self.vehicle_executors.values())
                if completed >= max_trips:
                    logger.info(f"Max trips completed threshold ({max_trips}) reached.")
                    break

            # Sleep only for real-time live execution
            if not self.dry_run and tick_seconds > 0:
                time.sleep(tick_seconds)

        self.stop()
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive fleet-wide status dictionary."""
        with self._lock:
            # Trip metrics
            trips_pending = sum(1 for t in self.plan.trips if t.state == TripExecutionState.PENDING)
            trips_starting = sum(1 for t in self.plan.trips if t.state == TripExecutionState.STARTING)
            trips_running = sum(1 for t in self.plan.trips if t.state == TripExecutionState.RUNNING)
            trips_ending = sum(1 for t in self.plan.trips if t.state == TripExecutionState.ENDING)
            trips_completed = sum(1 for t in self.plan.trips if t.state == TripExecutionState.COMPLETED)
            trips_error = sum(1 for t in self.plan.trips if t.state == TripExecutionState.ERROR)
            trips_skipped = sum(1 for t in self.plan.trips if t.state == TripExecutionState.SKIPPED)

            # Fleet metrics
            total_vehs = len(self.vehicle_executors)
            running_vehs = sum(1 for ve in self.vehicle_executors.values() if ve.state == VehicleOperationalState.RUNNING)
            layover_vehs = sum(1 for ve in self.vehicle_executors.values() if ve.state == VehicleOperationalState.LAYOVER)
            completed_vehs = sum(1 for ve in self.vehicle_executors.values() if ve.is_duty_completed)
            error_vehs = sum(1 for ve in self.vehicle_executors.values() if ve.state == VehicleOperationalState.ERROR)

            total_pkts_sent = sum(ve.packets_sent for ve in self.vehicle_executors.values())
            total_pkts_accepted = sum(ve.packets_accepted for ve in self.vehicle_executors.values())
            total_heartbeats = sum(ve.heartbeats_sent for ve in self.vehicle_executors.values())

            elapsed_wall = (time.time() - self.start_wall_time) if self.start_wall_time else 0.0

            return {
                "service_date": self.plan.service_date,
                "state": self.state.value,
                "dry_run": self.dry_run,
                "simulated_time": self.clock.time_string,
                "simulated_datetime": self.clock.isoformat,
                "elapsed_service_seconds": round(self.clock.elapsed_service_seconds, 1),
                "elapsed_service_hours": round(self.clock.elapsed_service_seconds / 3600.0, 2),
                "real_elapsed_seconds": round(elapsed_wall, 2),
                "multiplier": self.clock.time_multiplier,
                "fleet": {
                    "planned": total_vehs,
                    "active": total_vehs - completed_vehs,
                    "running": running_vehs,
                    "layover": layover_vehs,
                    "completed": completed_vehs,
                    "error": error_vehs,
                },
                "trips": {
                    "total": len(self.plan.trips),
                    "pending": trips_pending,
                    "starting": trips_starting,
                    "running": trips_running,
                    "ending": trips_ending,
                    "completed": trips_completed,
                    "error": trips_error,
                    "skipped": trips_skipped,
                },
                "telemetry": {
                    "packets_sent": total_pkts_sent,
                    "packets_accepted": total_pkts_accepted,
                    "heartbeats_sent": total_heartbeats,
                },
                "vehicles": {vid: ve.get_status() for vid, ve in self.vehicle_executors.items()},
            }
