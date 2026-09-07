"""
Transit Platform — Service-Day Scheduler.

BUILD 4 Phase 5B: Coordinates full-day transit operations across multiple vehicles,
driving sequential trips, managing terminus layovers, and integrating cleanly with
the existing BusSimulator and MovementEngine.
"""

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from simulator.config.settings import Settings
from simulator.core.bus_simulator import BusSimulator, BusLifecycle, BusConfig
from simulator.service_day.clock import ServiceDayClock
from simulator.service_day.models import (
    ScheduledTrip,
    ServiceDayEvent,
    ServiceDayEventType,
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

logger = get_logger("service_day.scheduler")


class ServiceDayScheduler:
    """
    Executes a ServiceDayPlan either in dry-run mode or live against the real GoBus backend.
    """

    def __init__(
        self,
        plan: ServiceDayPlan,
        settings: Optional[Settings] = None,
        clock: Optional[ServiceDayClock] = None,
        timestamp_strategy: Optional[BackendTimestampStrategy] = None,
        dry_run: bool = False,
    ):
        self.plan = plan
        self.settings = settings or Settings()
        self.dry_run = dry_run

        # Initialize Clock
        if clock:
            self.clock = clock
        else:
            first_time_str = "05:00:00"
            if plan.first_departure:
                first_time_str = plan.first_departure.strftime("%H:%M:%S")
            self.clock = ServiceDayClock(
                service_date=datetime.strptime(plan.service_date, "%Y-%m-%d").date(),
                start_time_of_day=first_time_str,
                timezone_name=plan.timezone_name,
                time_multiplier=self.settings.time_multiplier if hasattr(self.settings, "time_multiplier") else 1.0,
            )

        # Timestamp strategy
        if timestamp_strategy:
            self.timestamp_strategy = timestamp_strategy
        elif dry_run:
            self.timestamp_strategy = SimulatedTimestampStrategy()
        else:
            self.timestamp_strategy = LiveTimestampStrategy()

        # Active bus simulator instances keyed by trip_id
        self._active_simulators: Dict[str, BusSimulator] = {}
        self._completed_trip_ids: set[str] = set()
        self._failed_trip_ids: set[str] = set()

        # Metrics
        self.ticks_executed: int = 0
        self.packets_sent_total: int = 0
        self.packets_accepted_total: int = 0
        self.events_dispatched: int = 0

        self._lock = threading.RLock()
        self.plan.state = ServiceDayState.DAY_READY

    @property
    def is_completed(self) -> bool:
        """True when all trips have reached a terminal state (COMPLETED, SKIPPED, ERROR)."""
        terminal_states = {TripExecutionState.COMPLETED, TripExecutionState.SKIPPED, TripExecutionState.ERROR}
        return all(t.state in terminal_states for t in self.plan.trips)

    def start(self) -> None:
        """Begins execution of the service day."""
        with self._lock:
            if self.plan.state in (ServiceDayState.DAY_RUNNING, ServiceDayState.DAY_COMPLETED):
                return
            self.plan.state = ServiceDayState.DAY_RUNNING
            logger.info(f"Service day '{self.plan.service_date}' started (Dry-Run={self.dry_run}).")

    def pause(self) -> None:
        """Pauses service day progression."""
        with self._lock:
            if self.plan.state == ServiceDayState.DAY_RUNNING:
                self.plan.state = ServiceDayState.DAY_PAUSED
                self.clock.pause()
                for sim in self._active_simulators.values():
                    sim.pause()
                logger.info("Service day paused.")

    def resume(self) -> None:
        """Resumes service day progression."""
        with self._lock:
            if self.plan.state == ServiceDayState.DAY_PAUSED:
                self.plan.state = ServiceDayState.DAY_RUNNING
                self.clock.resume()
                for sim in self._active_simulators.values():
                    sim.resume()
                logger.info("Service day resumed.")

    def stop(self) -> None:
        """Stops all active trips and shuts down the service day."""
        with self._lock:
            self.plan.state = ServiceDayState.DAY_STOPPING
            logger.info("Stopping all active service day trips...")

            for trip_id, sim in list(self._active_simulators.items()):
                try:
                    if not self.dry_run:
                        sim.stop()
                except Exception as e:
                    logger.error(f"Error stopping simulator for trip {trip_id}: {e}")

            self._active_simulators.clear()
            self.plan.state = ServiceDayState.DAY_COMPLETED
            self.clock.mark_completed()
            logger.info("Service day stopped.")

    def step(self, real_delta_seconds: float = 1.0) -> None:
        """
        Advances the service day by real_delta_seconds.
        Evaluates trip starts, drives active simulators, handles completions and layovers.
        """
        with self._lock:
            if self.plan.state != ServiceDayState.DAY_RUNNING:
                return

            # 1. Advance simulation clock
            sim_delta_s = self.clock.advance(real_delta_seconds)
            self.ticks_executed += 1
            current_sim_dt = self.clock.current_simulated_datetime

            # 2. Check for trips ready to start
            for trip in self.plan.trips:
                if trip.state == TripExecutionState.PENDING:
                    # Vehicle cannot start a new trip if already RUNNING another trip
                    v_duty = self.plan.vehicle_duties.get(trip.vehicle_id)
                    if v_duty and v_duty.state == VehicleOperationalState.RUNNING:
                        continue

                    # Operator cannot start a new trip if already RUNNING another trip
                    op_duty = self.plan.operator_duties.get(trip.operator_code)
                    if op_duty and any(t.state == TripExecutionState.RUNNING for t in op_duty.trips if t.trip_id != trip.trip_id):
                        continue

                    if current_sim_dt >= trip.planned_start:
                        self._start_trip(trip)

            # 3. Step active trips
            active_ids = list(self._active_simulators.keys())
            for trip_id in active_ids:
                sim = self._active_simulators.get(trip_id)
                trip = next((t for t in self.plan.trips if t.trip_id == trip_id), None)
                if not trip:
                    continue
                if not self.dry_run and not sim:
                    continue

                if self.dry_run:
                    # In dry-run mode, complete trip when current_sim_dt reaches planned_end
                    end_time = trip.planned_end or trip.planned_start
                    if current_sim_dt >= end_time:
                        self._complete_trip(trip, sim)
                else:
                    # In live mode, tick the real BusSimulator
                    try:
                        sim.tick(real_delta_seconds)
                        self.packets_sent_total += sim.packets_sent
                        self.packets_accepted_total += sim.packets_accepted

                        # Check if bus reached route completion
                        if sim.lifecycle == BusLifecycle.COMPLETED:
                            self._complete_trip(trip, sim)
                        elif sim.lifecycle == BusLifecycle.FAILED:
                            self._fail_trip(trip, sim, sim.error_message or "Bus simulator failed")
                    except Exception as e:
                        logger.exception(f"Exception ticking trip {trip_id}: {e}")
                        self._fail_trip(trip, sim, str(e))

            # 4. Check if entire service day is completed
            if self.is_completed:
                self.plan.state = ServiceDayState.DAY_COMPLETED
                self.clock.mark_completed()
                logger.info("All scheduled trips completed. Service day COMPLETE.")

    def _start_trip(self, trip: ScheduledTrip) -> None:
        """Initializes and starts an individual scheduled trip."""
        v_duty = self.plan.vehicle_duties.get(trip.vehicle_id)
        logger.info(
            f"[TRIP START] Trip {trip.trip_id} on Vehicle {trip.vehicle_number} "
            f"({trip.service_code} {trip.direction}) starting [Operator: {trip.operator_code}]"
        )

        trip.state = TripExecutionState.RUNNING
        trip.actual_start = self.clock.current_simulated_datetime
        if v_duty:
            v_duty.state = VehicleOperationalState.RUNNING

        if self.dry_run:
            # Create a mock simulator handle
            self._active_simulators[trip.trip_id] = None  # type: ignore
        else:
            # Instantiate real BusSimulator
            b_cfg = BusConfig(
                bus_id=f"bus-{trip.vehicle_id[:8]}",
                employee_code=trip.operator_code,
                speed_mps=self.settings.default_speed_mps,
                time_multiplier=self.clock.time_multiplier,
                dwell_seconds=self.settings.default_dwell_seconds,
            )
            sim = BusSimulator(
                config=b_cfg,
                backend_url=self.settings.backend_url,
                request_timeout=self.settings.request_timeout_seconds,
            )

            try:
                sim.initialize()
                self._active_simulators[trip.trip_id] = sim
            except Exception as e:
                logger.error(f"Failed to initialize live trip {trip.trip_id}: {e}")
                self._fail_trip(trip, sim, str(e))

    def _complete_trip(self, trip: ScheduledTrip, sim: Optional[BusSimulator]) -> None:
        """Handles successful trip arrival and vehicle transition to layover."""
        logger.info(f"[TRIP COMPLETE] Trip {trip.trip_id} on Vehicle {trip.vehicle_number} arrived.")
        trip.state = TripExecutionState.COMPLETED
        trip.actual_end = self.clock.current_simulated_datetime
        self._completed_trip_ids.add(trip.trip_id)

        if not self.dry_run and sim:
            try:
                sim.stop()
            except Exception as e:
                logger.warning(f"Error stopping simulator after trip completion: {e}")

        if trip.trip_id in self._active_simulators:
            del self._active_simulators[trip.trip_id]

        # Transition vehicle to LAYOVER or IDLE
        v_duty = self.plan.vehicle_duties.get(trip.vehicle_id)
        if v_duty:
            remaining_trips = [t for t in v_duty.trips if t.state == TripExecutionState.PENDING]
            if remaining_trips:
                v_duty.state = VehicleOperationalState.LAYOVER
                next_trip = remaining_trips[0]
                logger.info(
                    f"[LAYOVER] Vehicle {trip.vehicle_number} entering terminus layover until next trip at {next_trip.planned_start}."
                )
            else:
                v_duty.state = VehicleOperationalState.IDLE
                logger.info(f"[DUTY FINISHED] Vehicle {trip.vehicle_number} completed all scheduled duties.")

    def _fail_trip(self, trip: ScheduledTrip, sim: Optional[BusSimulator], error: str) -> None:
        """Handles trip failure while isolating other duties."""
        logger.error(f"[TRIP ERROR] Trip {trip.trip_id} failed: {error}")
        trip.state = TripExecutionState.ERROR
        trip.error_message = error
        self._failed_trip_ids.add(trip.trip_id)

        if not self.dry_run and sim:
            try:
                sim.stop()
            except Exception:
                pass

        if trip.trip_id in self._active_simulators:
            del self._active_simulators[trip.trip_id]

        v_duty = self.plan.vehicle_duties.get(trip.vehicle_id)
        if v_duty:
            # Leave in LAYOVER/IDLE so subsequent trips can still attempt dispatch
            v_duty.state = VehicleOperationalState.LAYOVER

    def run_dry_run_full_day(self, step_seconds: float = 60.0) -> Dict[str, Any]:
        """
        Executes a complete dry-run of the service day locally.
        Simulates the entire day schedule in seconds without making network calls.
        Returns execution summary metrics.
        """
        self.dry_run = True
        self.start()
        start_wall_time = time.time()

        max_steps = 100000
        steps = 0
        while not self.is_completed and self.plan.state == ServiceDayState.DAY_RUNNING and steps < max_steps:
            self.step(step_seconds)
            steps += 1

        elapsed_wall_time = time.time() - start_wall_time

        completed_count = sum(1 for t in self.plan.trips if t.state == TripExecutionState.COMPLETED)
        error_count = sum(1 for t in self.plan.trips if t.state == TripExecutionState.ERROR)

        return {
            "status": "COMPLETED" if self.is_completed else "INCOMPLETE",
            "service_date": self.plan.service_date,
            "total_trips": len(self.plan.trips),
            "completed_trips": completed_count,
            "failed_trips": error_count,
            "simulated_duration_s": self.clock.elapsed_service_seconds,
            "simulated_duration_hours": round(self.clock.elapsed_service_seconds / 3600.0, 2),
            "wall_clock_time_s": round(elapsed_wall_time, 3),
            "ticks_executed": self.ticks_executed,
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns live read-only status dictionary."""
        with self._lock:
            completed_count = sum(1 for t in self.plan.trips if t.state == TripExecutionState.COMPLETED)
            running_count = sum(1 for t in self.plan.trips if t.state == TripExecutionState.RUNNING)
            pending_count = sum(1 for t in self.plan.trips if t.state == TripExecutionState.PENDING)
            error_count = sum(1 for t in self.plan.trips if t.state == TripExecutionState.ERROR)

            return {
                "service_date": self.plan.service_date,
                "state": self.plan.state.value,
                "simulated_time": self.clock.time_string,
                "simulated_datetime": self.clock.isoformat,
                "elapsed_service_seconds": round(self.clock.elapsed_service_seconds, 1),
                "multiplier": self.clock.time_multiplier,
                "dry_run": self.dry_run,
                "trips_total": len(self.plan.trips),
                "trips_pending": pending_count,
                "trips_running": running_count,
                "trips_completed": completed_count,
                "trips_error": error_count,
                "active_buses_count": len(self._active_simulators),
                "vehicle_states": {
                    vid: duty.state.value for vid, duty in self.plan.vehicle_duties.items()
                },
                "metrics": {
                    "ticks_executed": self.ticks_executed,
                    "packets_sent": self.packets_sent_total,
                    "packets_accepted": self.packets_accepted_total,
                },
            }
