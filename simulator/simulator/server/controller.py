"""
Transit Platform — Thread-Safe Simulation Controller.

Orchestrates the existing Phase 1-3 simulator components (FleetManager,
ScenarioScheduler, BusSimulator) in a controlled background worker thread.
Exposes a safe, read-only state projection and thread-safe control lifecycle
(start, pause, resume, stop, reset) without exposing secrets.
"""

from collections import deque
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from simulator.api.client import GoBusHttpClient
from simulator.config.settings import Settings
from simulator.core.exceptions import SimulatorError
from simulator.core.fleet import FleetManager
from simulator.core.scenario import ScenarioDefinition, ScenarioEventType
from simulator.core.scenario_loader import (
    build_scenario,
    validate_scenario,
)
from simulator.utils.logging import RedactingFilter, get_logger

logger = get_logger("controller")


class SimulationLifecycle(str, Enum):
    """Explicit lifecycle states for the simulation controller."""
    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class ConflictError(Exception):
    """Raised when an operation conflicts with the current lifecycle state."""
    pass


class SafeLogHandler(logging.Handler):
    """Captures simulator log messages into a bounded in-memory buffer."""

    def __init__(self, log_buffer: deque, max_entries: int = 200):
        super().__init__()
        self.log_buffer = log_buffer
        self.max_entries = max_entries
        self.addFilter(RedactingFilter())
        self.setFormatter(logging.Formatter("[%(levelname)s] [%(name)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
            self.log_buffer.append({
                "timestamp": now_str,
                "level": record.levelname,
                "message": msg,
            })
        except Exception:
            self.handleError(record)


class SimulationController:
    """
    Thread-safe controller managing simulator lifecycle, background execution,
    and read-only state projection.
    """

    BUILTIN_SCENARIOS = [
        "normal_single_bus",
        "multi_bus_demo",
        "delay_demo",
        "offline_demo",
        "crowding_demo",
        "service_shortage_demo",
        "full_demo",
    ]

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._lock = threading.RLock()
        self._lifecycle = SimulationLifecycle.IDLE
        self._error_message: Optional[str] = None

        # Background worker management
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default

        # Active simulation engine instances (Phase 3 components)
        self._active_scenario_name: Optional[str] = None
        self._scenario: Optional[ScenarioDefinition] = None
        self._fleet: Optional[FleetManager] = None
        self._scheduler: Optional[Any] = None  # ScenarioScheduler

        # Observability & safe telemetry counters
        self._metrics = {
            "packets_generated": 0,
            "packets_accepted": 0,
            "packets_rejected": 0,
            "heartbeats_sent": 0,
            "crowding_reports_sent": 0,
            "last_error": None,
        }

        # Bounded in-memory event stream (200 entries max)
        self._event_log: deque = deque(maxlen=200)

        # Attach custom log handler to simulator logger hierarchy
        self._log_handler = SafeLogHandler(self._event_log)
        root_sim_logger = logging.getLogger("simulator")
        root_sim_logger.addHandler(self._log_handler)

        # Backend health probe cache
        self._last_health_check_time: float = 0.0
        self._cached_health: Dict[str, Any] = {
            "connected": False,
            "latency_ms": 0.0,
            "backend_url": self.settings.backend_url,
            "last_probe": None,
        }

    @property
    def lifecycle(self) -> SimulationLifecycle:
        with self._lock:
            return self._lifecycle

    def record_event(self, message: str, level: str = "INFO") -> None:
        """Appends a sanitized operational message to the safe event stream."""
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        sanitized = RedactingFilter.redact(message)
        self._event_log.append({
            "timestamp": now_str,
            "level": level,
            "message": sanitized,
        })

    def check_backend(self) -> Dict[str, Any]:
        """Probes GoBus backend connectivity with latency measurement."""
        now = time.time()
        # Cache health checks for 2 seconds to avoid excessive network overhead
        if now - self._last_health_check_time < 2.0:
            return dict(self._cached_health)

        start_time = time.perf_counter()
        connected = False
        status_code = None
        latency_ms = 0.0
        client = GoBusHttpClient(base_url=self.settings.backend_url, timeout=3.0)
        try:
            resp = client.check_health()
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            connected = resp.get("status") in ("ok", "healthy") or "service" in resp
            status_code = 200
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            connected = False
            logger.debug(f"Health probe failure: {e}")
        finally:
            client.close()

        with self._lock:
            self._cached_health = {
                "connected": connected,
                "latency_ms": latency_ms,
                "backend_url": self.settings.backend_url,
                "status_code": status_code,
                "last_probe": datetime.now(timezone.utc).isoformat(),
            }
            self._last_health_check_time = now
            return dict(self._cached_health)

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """Returns safe metadata summaries for all available scenarios."""
        summaries = []
        for name in self.BUILTIN_SCENARIOS:
            try:
                sc = build_scenario(name, self.settings)
                summaries.append({
                    "name": sc.name,
                    "description": sc.description,
                    "bus_count": len(sc.buses),
                    "duration_s": sc.duration_seconds or 120.0,
                    "events_count": len(sc.events),
                })
            except Exception as e:
                summaries.append({
                    "name": name,
                    "description": f"Error loading scenario: {e}",
                    "bus_count": 0,
                    "duration_s": 0.0,
                    "events_count": 0,
                })
        return summaries

    def get_scenario_detail(self, name: str) -> Dict[str, Any]:
        """Returns detailed, secret-free metadata for a specific scenario."""
        sc = build_scenario(name, self.settings)
        return {
            "name": sc.name,
            "description": sc.description,
            "duration_s": sc.duration_seconds,
            "buses": [
                {
                    "bus_id": b.bus_id,
                    "employee_code": b.employee_code,
                    "speed_mps": b.speed_mps,
                    "time_multiplier": b.time_multiplier,
                }
                for b in sc.buses
            ],
            "events": [
                {
                    "time_s": ev.sim_time_offset_s,
                    "event_type": ev.event_type.value,
                    "target_bus_id": ev.target_bus_id,
                    "parameters": ev.parameters,
                }
                for ev in sc.events
            ],
        }

    def validate(self, scenario_name: str) -> Tuple[bool, List[str]]:
        """Performs dry-run offline validation on a scenario."""
        try:
            sc = build_scenario(scenario_name, self.settings)
            errors = validate_scenario(sc)
            return len(errors) == 0, errors
        except Exception as e:
            return False, [str(e)]

    def start(
        self,
        scenario_name: str,
        time_multiplier: float = 1.0,
        tick_seconds: float = 1.0,
        duration: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Launches a simulation scenario in the background worker thread.
        Enforces single active simulation rule.
        """
        with self._lock:
            if self._lifecycle in (SimulationLifecycle.RUNNING, SimulationLifecycle.PAUSED, SimulationLifecycle.STARTING):
                raise ConflictError(
                    f"Simulation is already active (Lifecycle: {self._lifecycle.value}). "
                    "Stop or reset the current simulation before starting a new one."
                )

            # 1. Load and validate scenario
            try:
                scenario = build_scenario(scenario_name, self.settings)
            except Exception as e:
                raise ValueError(f"Unknown or invalid scenario '{scenario_name}': {e}")

            if duration is not None and duration > 0:
                scenario.duration_seconds = duration

            errors = validate_scenario(scenario)
            if errors:
                raise ValueError(f"Scenario validation failed: {'; '.join(errors)}")

            # 2. Reset worker control events
            self._stop_event.clear()
            self._pause_event.set()
            self._lifecycle = SimulationLifecycle.STARTING
            self._active_scenario_name = scenario.name
            self._scenario = scenario
            self._error_message = None

            # Reset metrics for new run
            self._metrics = {
                "packets_generated": 0,
                "packets_accepted": 0,
                "packets_rejected": 0,
                "heartbeats_sent": 0,
                "crowding_reports_sent": 0,
                "last_error": None,
            }

            self.record_event(f"Starting scenario '{scenario.name}' ({len(scenario.buses)} buses)...")

            # 3. Launch background worker thread
            self._worker_thread = threading.Thread(
                target=self._run_simulation_worker,
                args=(scenario, time_multiplier, tick_seconds),
                name=f"sim-worker-{scenario.name}",
                daemon=True,
            )
            self._worker_thread.start()

            return {
                "status": "STARTED",
                "scenario": scenario.name,
                "buses": len(scenario.buses),
                "duration_s": scenario.duration_seconds,
            }

    def _run_simulation_worker(
        self,
        scenario: ScenarioDefinition,
        time_multiplier: float,
        tick_seconds: float,
    ) -> None:
        """Background execution loop driving FleetManager and ScenarioScheduler."""
        fleet: Optional[FleetManager] = None
        from simulator.core.scheduler import ScenarioScheduler

        try:
            # 1. Initialize Fleet
            fleet = FleetManager(
                backend_url=self.settings.backend_url,
                request_timeout=self.settings.request_timeout,
            )
            for bus_config in scenario.buses:
                fleet.add_bus(bus_config)

            scheduler = ScenarioScheduler(
                fleet=fleet,
                scenario=scenario,
                time_multiplier=time_multiplier,
            )

            with self._lock:
                self._fleet = fleet
                self._scheduler = scheduler
                self._lifecycle = SimulationLifecycle.RUNNING

            self.record_event(f"Fleet ready. Simulation '{scenario.name}' RUNNING.")

            # 2. Main Simulation Tick Loop
            while not self._stop_event.is_set():
                # Handle Pause: wait until pause_event is set or stop_event is set
                while not self._pause_event.is_set() and not self._stop_event.is_set():
                    time.sleep(0.1)

                if self._stop_event.is_set():
                    break

                # Sleep real tick duration
                if tick_seconds > 0:
                    time.sleep(tick_seconds)

                if self._stop_event.is_set():
                    break

                # Advance scheduler by one tick
                tick_result = scheduler.tick(tick_seconds)

                # Update metrics
                with self._lock:
                    self._metrics["packets_generated"] += tick_result.get("packets_generated", 0)
                    acks = tick_result.get("telemetry_acks", {})
                    for accepted in acks.values():
                        if accepted:
                            self._metrics["packets_accepted"] += 1
                        else:
                            self._metrics["packets_rejected"] += 1

                    hb_results = tick_result.get("heartbeats_sent", {})
                    self._metrics["heartbeats_sent"] += sum(1 for sent in hb_results.values() if sent)

                    # Check for completed crowding reports
                    events_done = tick_result.get("events_processed", [])
                    for ev in events_done:
                        if ev == ScenarioEventType.SET_CROWDING.value:
                            self._metrics["crowding_reports_sent"] += 1
                        self.record_event(f"Event executed: {ev}")

                if scheduler.is_completed:
                    self.record_event(f"Scenario '{scenario.name}' timeline completed.")
                    break

            # Completed or Stopped
            with self._lock:
                if self._lifecycle != SimulationLifecycle.STOPPED:
                    self._lifecycle = SimulationLifecycle.STOPPED

        except Exception as e:
            logger.exception(f"Simulation worker error: {e}")
            with self._lock:
                self._lifecycle = SimulationLifecycle.ERROR
                self._error_message = str(e)
                self._metrics["last_error"] = str(e)
            self.record_event(f"Simulation error: {e}", level="ERROR")
        finally:
            # Clean up fleet tracking sessions if fleet was initialized
            if fleet is not None:
                try:
                    fleet.stop_fleet()
                except Exception as e:
                    logger.warning(f"Error stopping fleet in worker cleanup: {e}")

    def pause(self) -> Dict[str, Any]:
        """Pauses the active simulation."""
        with self._lock:
            if self._lifecycle != SimulationLifecycle.RUNNING:
                raise ConflictError(
                    f"Cannot pause simulation in state '{self._lifecycle.value}'. "
                    "Simulation must be RUNNING to pause."
                )
            self._pause_event.clear()
            self._lifecycle = SimulationLifecycle.PAUSED
            self.record_event("Simulation PAUSED.")
            return {"status": "PAUSED"}

    def resume(self) -> Dict[str, Any]:
        """Resumes a paused simulation."""
        with self._lock:
            if self._lifecycle != SimulationLifecycle.PAUSED:
                raise ConflictError(
                    f"Cannot resume simulation in state '{self._lifecycle.value}'. "
                    "Simulation must be PAUSED to resume."
                )
            self._pause_event.set()
            self._lifecycle = SimulationLifecycle.RUNNING
            self.record_event("Simulation RESUMED.")
            return {"status": "RUNNING"}

    def stop(self) -> Dict[str, Any]:
        """
        Gracefully stops the active simulation and ends active backend trips.
        """
        with self._lock:
            if self._lifecycle in (SimulationLifecycle.IDLE, SimulationLifecycle.STOPPED):
                return {"status": self._lifecycle.value, "message": "Simulation already stopped or idle."}

            self._lifecycle = SimulationLifecycle.STOPPING
            self._stop_event.set()
            self._pause_event.set()  # Unblock if paused

        # Join worker thread outside lock
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)

        with self._lock:
            if self._fleet:
                try:
                    self._fleet.stop_fleet()
                except Exception as e:
                    logger.warning(f"Error stopping fleet: {e}")

            self._lifecycle = SimulationLifecycle.STOPPED
            self.record_event("Simulation STOPPED cleanly.")
            return {"status": "STOPPED"}

    def reset(self, confirm_backend_cleanup: bool = False) -> Dict[str, Any]:
        """
        Resets simulator state.
        If RUNNING or PAUSED, requires confirm_backend_cleanup=True.
        """
        with self._lock:
            is_active = self._lifecycle in (SimulationLifecycle.RUNNING, SimulationLifecycle.PAUSED, SimulationLifecycle.STARTING)

            if is_active and not confirm_backend_cleanup:
                raise ConflictError(
                    "Simulation is currently active. Reset will terminate active backend trips "
                    "and clear fleet state. Explicit confirmation required: confirm_backend_cleanup=true"
                )

        # Stop active worker first
        self.stop()

        with self._lock:
            # Failsafe emergency cleanup
            if self._fleet:
                try:
                    self._fleet.emergency_cleanup()
                except Exception as e:
                    logger.warning(f"Error during reset emergency cleanup: {e}")

            # Reset local state
            self._fleet = None
            self._scheduler = None
            self._scenario = None
            self._active_scenario_name = None
            self._error_message = None
            self._lifecycle = SimulationLifecycle.IDLE

            # Reset metrics
            self._metrics = {
                "packets_generated": 0,
                "packets_accepted": 0,
                "packets_rejected": 0,
                "heartbeats_sent": 0,
                "crowding_reports_sent": 0,
                "last_error": None,
            }

            self.record_event("Simulation state RESET to IDLE.")
            return {"status": "IDLE"}

    def get_state(self) -> Dict[str, Any]:
        """
        Thread-safe read-only projection of the current simulator state.
        Guaranteed to contain zero secrets (no passwords, JWTs, or tokens).
        """
        with self._lock:
            # 1. Fleet State
            fleet_summary: List[Dict[str, Any]] = []
            if self._fleet:
                for bus_id, bus in self._fleet.buses.items():
                    m_state = bus.movement.get_state() if bus.movement else None
                    progress_pct = 0.0
                    if bus.route and bus.route.total_distance_m > 0 and m_state:
                        progress_pct = round(min(100.0, (m_state.total_progress_m / bus.route.total_distance_m) * 100.0), 1)

                    speed_kmh = round(m_state.current_speed_mps * 3.6, 1) if m_state else 0.0

                    fleet_summary.append({
                        "bus_id": bus.bus_id,
                        "operator": bus.session.employee_code,
                        "operator_name": bus.session.name or "Driver",
                        "organization": bus.session.organization_name or "GoBus Transit",
                        "vehicle_id": bus.assignment.vehicle_number if bus.assignment else "Unassigned",
                        "service_code": bus.assignment.service_code if bus.assignment else "N/A",
                        "route_name": bus.route.route_name if bus.route else (bus.assignment.route_name if bus.assignment else "Route"),
                        "state": bus.lifecycle.value,
                        "current_stop": m_state.current_stop.stop_name if m_state else "Start Terminus",
                        "next_stop": m_state.next_stop.stop_name if (m_state and m_state.next_stop) else "Destination",
                        "speed_mps": round(m_state.current_speed_mps, 2) if m_state else 0.0,
                        "speed_kmh": speed_kmh,
                        "heading": round(m_state.current_heading, 1) if m_state else 0.0,
                        "latitude": round(m_state.current_latitude, 6) if m_state else None,
                        "longitude": round(m_state.current_longitude, 6) if m_state else None,
                        "is_dwelling": m_state.is_dwelling if m_state else False,
                        "dwell_remaining_s": round(m_state.dwell_time_remaining_s, 1) if m_state else 0.0,
                        "progress_percent": progress_pct,
                        "telemetry_enabled": bus.telemetry_enabled,
                        "heartbeat_enabled": bus.heartbeat_enabled,
                        "crowding_state": getattr(bus, "crowding_state", "NORMAL") or "NORMAL",
                        "packets_sent": bus.packets_sent,
                        "packets_accepted": bus.packets_accepted,
                        "error": bus.error_message,
                    })

            # 2. Timeline Events State
            timeline: List[Dict[str, Any]] = []
            sim_time_s = self._scheduler.sim_elapsed_seconds if self._scheduler else 0.0

            if self._scenario:
                for ev in self._scenario.events:
                    if ev.sim_time_offset_s < sim_time_s:
                        ev_status = "COMPLETED"
                    elif abs(ev.sim_time_offset_s - sim_time_s) <= 1.0:
                        ev_status = "ACTIVE"
                    else:
                        ev_status = "UPCOMING"

                    timeline.append({
                        "time_s": ev.sim_time_offset_s,
                        "event_type": ev.event_type.value,
                        "target_bus_id": ev.target_bus_id,
                        "parameters": ev.parameters,
                        "status": ev_status,
                    })

            # 3. Assemble Snapshot Projection
            snapshot = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "lifecycle": self._lifecycle.value,
                "error": self._error_message,
                "scenario": {
                    "name": self._scenario.name if self._scenario else (self._active_scenario_name or "None"),
                    "duration_s": self._scenario.duration_seconds if self._scenario else 0.0,
                    "bus_count": len(self._scenario.buses) if self._scenario else 0,
                },
                "simulation_time_s": round(sim_time_s, 1),
                "tick_count": self._scheduler.tick_count if self._scheduler else 0,
                "is_completed": self._scheduler.is_completed if self._scheduler else False,
                "backend": dict(self._cached_health),
                "metrics": dict(self._metrics),
                "fleet": fleet_summary,
                "timeline": timeline,
                "event_log": list(self._event_log)[-50:],  # Last 50 messages for UI
            }

            return snapshot
