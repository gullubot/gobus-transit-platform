"""
Transit Platform — Deterministic Scenario Scheduler.

Executes scenario events at exact simulated time offsets and orchestrates
per-tick movement and telemetry dispatch across all active buses.
"""

from typing import Any, Callable, Dict, List, Optional

from simulator.core.bus_simulator import BusLifecycle
from simulator.core.fleet import FleetManager
from simulator.core.scenario import ScenarioDefinition, ScenarioEvent, ScenarioEventType
from simulator.utils.logging import get_logger

logger = get_logger("scheduler")


class ScenarioScheduler:
    """
    Drives fleet simulation progression against a deterministic scenario timeline.
    """

    def __init__(
        self,
        fleet: FleetManager,
        scenario: ScenarioDefinition,
        time_multiplier: float = 1.0,
    ):
        self.fleet = fleet
        self.scenario = scenario
        self.time_multiplier = float(time_multiplier)

        # Scheduled events sorted chronologically
        self._pending_events: List[ScenarioEvent] = list(scenario.events)
        self._executed_events: List[ScenarioEvent] = []

        self.sim_elapsed_seconds: float = 0.0
        self.tick_count: int = 0
        self.is_completed: bool = False

    def is_finished(self) -> bool:
        """True if scenario duration reached or all buses have completed/stopped."""
        if self.scenario.duration_seconds and self.sim_elapsed_seconds >= self.scenario.duration_seconds:
            return True
        if self.fleet.bus_count > 0 and self.fleet.active_buses_count == 0:
            # Check if any pending events could start a bus in the future
            has_future_starts = any(
                e.event_type == ScenarioEventType.START_BUS for e in self._pending_events
            )
            if not has_future_starts:
                return True
        return False

    def process_due_events(self, up_to_sim_time: Optional[float] = None) -> List[ScenarioEvent]:
        """Dispatches all scenario events scheduled at or before up_to_sim_time."""
        limit_time = self.sim_elapsed_seconds if up_to_sim_time is None else up_to_sim_time
        due_events: List[ScenarioEvent] = []
        remaining_events: List[ScenarioEvent] = []

        for event in self._pending_events:
            if event.sim_time_offset_s <= limit_time:
                due_events.append(event)
            else:
                remaining_events.append(event)

        self._pending_events = remaining_events

        for event in due_events:
            self._execute_event(event)
            self._executed_events.append(event)

        return due_events

    def _execute_event(self, event: ScenarioEvent) -> None:
        """Applies an individual scenario event to target bus(es)."""
        target_buses = (
            list(self.fleet.buses.values())
            if event.target_bus_id == "*"
            else [self.fleet.buses[event.target_bus_id]]
            if event.target_bus_id in self.fleet.buses
            else []
        )

        if not target_buses:
            logger.warning(f"Event {event.event_type} target '{event.target_bus_id}' not found in fleet.")
            return

        logger.info(
            f"[T+{self.sim_elapsed_seconds:0.1f}s] Executing event {event.event_type.value} "
            f"on target '{event.target_bus_id}' {event.parameters}"
        )

        for bus in target_buses:
            try:
                if event.event_type == ScenarioEventType.START_BUS:
                    if bus.lifecycle in (BusLifecycle.CREATED, BusLifecycle.STOPPED):
                        bus.initialize_backend()
                elif event.event_type == ScenarioEventType.STOP_BUS:
                    bus.stop()
                elif event.event_type == ScenarioEventType.PAUSE_BUS:
                    bus.pause()
                elif event.event_type == ScenarioEventType.RESUME_BUS:
                    bus.resume()
                elif event.event_type == ScenarioEventType.SET_SPEED:
                    speed = float(event.parameters.get("speed_mps", bus.base_speed_mps))
                    bus.set_speed(speed)
                elif event.event_type == ScenarioEventType.RESTORE_SPEED:
                    bus.restore_speed()
                elif event.event_type == ScenarioEventType.SET_CROWDING:
                    state = str(event.parameters.get("crowding_state", "MODERATE"))
                    conf = float(event.parameters.get("confidence", 0.85))
                    bus.submit_crowding(state, conf)
                elif event.event_type == ScenarioEventType.SET_TELEMETRY_ENABLED:
                    enabled = bool(event.parameters.get("enabled", True))
                    bus.telemetry_enabled = enabled
                    logger.info(f"[{bus.bus_id}] Telemetry transmission {'enabled' if enabled else 'DISABLED (stale/offline)'}")
                elif event.event_type == ScenarioEventType.SET_HEARTBEAT_ENABLED:
                    enabled = bool(event.parameters.get("enabled", True))
                    bus.heartbeat_enabled = enabled
                    logger.info(f"[{bus.bus_id}] Heartbeat transmission {'enabled' if enabled else 'DISABLED'}")
                elif event.event_type == ScenarioEventType.SET_NETWORK_TYPE:
                    bus.network_type = str(event.parameters.get("network_type", "CELLULAR"))
                elif event.event_type == ScenarioEventType.SET_GPS_STATUS:
                    bus.gps_status = str(event.parameters.get("gps_status", "AVAILABLE"))
            except Exception as e:
                logger.error(f"Error executing event {event.event_type} on '{bus.bus_id}': {e}")

    def tick(self, delta_real_seconds: float) -> Dict[str, Any]:
        """
        Executes a single simulation tick:
        1. Advances simulation clock window.
        2. Evaluates due scenario events within new window.
        3. Steps all active fleet buses.
        4. Transmits telemetry packets.
        5. Sends heartbeats.
        """
        self.tick_count += 1
        delta_sim = delta_real_seconds * self.time_multiplier
        new_sim_time = self.sim_elapsed_seconds + delta_sim

        # 1. Process due events up to new simulated time
        events_processed = self.process_due_events(up_to_sim_time=new_sim_time)

        # 2. Step fleet
        packets = self.fleet.step_fleet(delta_real_seconds)

        # 3. Transmit telemetry
        telemetry_results = self.fleet.transmit_fleet_telemetry(packets)

        # 4. Heartbeats
        hb_results = self.fleet.send_fleet_heartbeats(interval_sim_seconds=30.0)

        # 5. Commit simulation time
        self.sim_elapsed_seconds = new_sim_time

        if self.is_finished():
            self.is_completed = True

        return {
            "tick": self.tick_count,
            "sim_time_s": self.sim_elapsed_seconds,
            "events_processed": [e.event_type.value for e in events_processed],
            "packets_generated": sum(1 for p in packets.values() if p is not None),
            "telemetry_acks": telemetry_results,
            "heartbeats_sent": hb_results,
            "is_completed": self.is_completed,
        }
