"""
Transit Platform — Multi-Bus Fleet Orchestrator.

Manages N independent simulated bus contexts, enforces unique operator credential
isolation, executes per-tick fleet steps, and isolates individual bus failures.
"""

from typing import Any, Dict, List, Optional

from simulator.core.bus_simulator import BusConfig, BusLifecycle, BusSimulator
from simulator.core.exceptions import SimulatorError
from simulator.utils.logging import get_logger

logger = get_logger("fleet")


class FleetManager:
    """
    Orchestrates multiple independent simulated buses.
    Enforces the non-negotiable rule: 1 bus = 1 distinct operator account.
    """

    def __init__(
        self,
        backend_url: str,
        request_timeout: float = 10.0,
    ):
        self.backend_url = backend_url
        self.request_timeout = request_timeout
        self.buses: Dict[str, BusSimulator] = {}
        self._employee_codes: Dict[str, str] = {}  # employee_code -> bus_id

    @property
    def bus_count(self) -> int:
        return len(self.buses)

    @property
    def active_buses_count(self) -> int:
        return sum(1 for b in self.buses.values() if b.is_active)

    def add_bus(self, config: BusConfig) -> BusSimulator:
        """
        Registers a new bus definition with the fleet.
        Enforces unique operator credential isolation.
        """
        if config.bus_id in self.buses:
            raise SimulatorError(f"Duplicate bus_id '{config.bus_id}' already registered in fleet.")

        # STRICT INVARIANT: 1 operator account cannot control multiple simultaneous buses
        if config.employee_code in self._employee_codes:
            conflict_bus = self._employee_codes[config.employee_code]
            raise SimulatorError(
                f"Duplicate operator credentials detected: employee_code '{config.employee_code}' "
                f"is already assigned to '{conflict_bus}'. Each simulated bus must have a distinct operator account."
            )

        bus = BusSimulator(
            config=config,
            backend_url=self.backend_url,
            request_timeout=self.request_timeout,
        )
        self.buses[config.bus_id] = bus
        self._employee_codes[config.employee_code] = config.bus_id
        logger.info(f"Registered bus '{config.bus_id}' (Operator: {config.employee_code}) with fleet.")
        return bus

    def get_bus(self, bus_id: str) -> BusSimulator:
        """Retrieves a bus simulator by ID."""
        if bus_id not in self.buses:
            raise KeyError(f"Bus '{bus_id}' not found in fleet.")
        return self.buses[bus_id]

    def initialize_bus(self, bus_id: str) -> bool:
        """Initializes a single bus backend context with error isolation."""
        bus = self.get_bus(bus_id)
        try:
            bus.initialize_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize bus '{bus_id}': {e}. Other fleet buses will continue.")
            return False

    def initialize_fleet(self) -> Dict[str, bool]:
        """Initializes all registered buses, isolating failures per bus."""
        results = {}
        logger.info(f"Initializing fleet of {len(self.buses)} buses...")
        for bus_id in self.buses:
            success = self.initialize_bus(bus_id)
            results[bus_id] = success
        return results

    def step_fleet(self, delta_real_seconds: float) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Advances all active buses by delta_real_seconds.
        Returns generated telemetry packets keyed by bus_id.
        """
        packets = {}
        for bus_id, bus in self.buses.items():
            if bus.lifecycle == BusLifecycle.RUNNING:
                try:
                    packet = bus.step(delta_real_seconds)
                    packets[bus_id] = packet
                except Exception as e:
                    logger.error(f"Error stepping bus '{bus_id}': {e}")
                    bus.lifecycle = BusLifecycle.ERROR
                    bus.error_message = str(e)
                    packets[bus_id] = None
        return packets

    def transmit_fleet_telemetry(self, packets: Dict[str, Optional[Dict[str, Any]]]) -> Dict[str, bool]:
        """
        Transmits telemetry packets to the backend for each bus.
        Isolates failures so a network error on one bus does not affect others.
        """
        results = {}
        for bus_id, packet in packets.items():
            if packet is None:
                continue
            bus = self.get_bus(bus_id)
            try:
                bus.transmit_packet(packet)
                results[bus_id] = True
            except Exception as e:
                logger.warning(f"Telemetry transmit error for bus '{bus_id}': {e}")
                results[bus_id] = False
        return results

    def send_fleet_heartbeats(self, interval_sim_seconds: float = 30.0) -> Dict[str, bool]:
        """Sends periodic heartbeats across the fleet."""
        results = {}
        for bus_id, bus in self.buses.items():
            if bus.is_active:
                sent = bus.check_and_send_heartbeat(interval_sim_seconds)
                results[bus_id] = sent
        return results

    def stop_bus(self, bus_id: str) -> None:
        """Stops an individual bus."""
        bus = self.get_bus(bus_id)
        bus.stop()

    def stop_fleet(self) -> None:
        """Stops all fleet buses and cleans up all active tracking sessions."""
        logger.info(f"Stopping fleet ({len(self.buses)} buses)...")
        for bus_id, bus in self.buses.items():
            try:
                bus.stop()
            except Exception as e:
                logger.warning(f"Error stopping bus '{bus_id}': {e}")

    def emergency_cleanup(self) -> None:
        """Failsafe cleanup attempting to end all active trip sessions."""
        logger.info("Executing fleet emergency cleanup...")
        for bus in self.buses.values():
            bus.emergency_cleanup()

    def get_fleet_summary(self) -> List[Dict[str, Any]]:
        """Returns safe status summaries for all buses."""
        return [bus.get_status_summary() for bus in self.buses.values()]
