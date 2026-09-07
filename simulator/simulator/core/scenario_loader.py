"""
Transit Platform — Scenario Loader and Registry.

Provides built-in scenarios (normal, multi-bus, delay, offline, crowding, service shortage, full demo),
loads external scenario JSON configurations, and provides dry-run validation without network calls.
"""

import json
import os
from typing import Any, Dict, List, Optional

from simulator.config.settings import Settings
from simulator.core.bus_simulator import BusConfig
from simulator.core.exceptions import SimulatorError
from simulator.core.scenario import ScenarioDefinition, ScenarioEvent, ScenarioEventType
from simulator.utils.logging import get_logger

logger = get_logger("scenario_loader")


def validate_scenario(scenario: ScenarioDefinition) -> List[str]:
    """
    Dry-run validation of scenario configuration without network calls or backend mutations.
    Returns a list of error strings (empty if valid).
    """
    errors: List[str] = []

    if not scenario.name:
        errors.append("Scenario must have a non-empty name.")

    if not scenario.buses:
        errors.append("Scenario must define at least one bus.")

    # Invariant: unique bus IDs and unique operator employee codes
    seen_bus_ids = set()
    seen_employee_codes = set()

    for bus in scenario.buses:
        if not bus.bus_id:
            errors.append("Bus definition missing bus_id.")
        elif bus.bus_id in seen_bus_ids:
            errors.append(f"Duplicate bus_id '{bus.bus_id}' found in scenario.")
        else:
            seen_bus_ids.add(bus.bus_id)

        if not bus.employee_code:
            errors.append(f"Bus '{bus.bus_id}' missing employee_code.")
        elif bus.employee_code in seen_employee_codes:
            errors.append(
                f"Duplicate employee_code '{bus.employee_code}' assigned to multiple buses. "
                "Each simulated bus requires an independent operator account."
            )
        else:
            seen_employee_codes.add(bus.employee_code)

        if bus.speed_mps <= 0:
            errors.append(f"Bus '{bus.bus_id}' speed_mps must be > 0, got {bus.speed_mps}")

        if bus.time_multiplier <= 0:
            errors.append(f"Bus '{bus.bus_id}' time_multiplier must be > 0, got {bus.time_multiplier}")

    # Validate event targets
    for event in scenario.events:
        if event.target_bus_id != "*" and event.target_bus_id not in seen_bus_ids:
            errors.append(
                f"Event at T+{event.sim_time_offset_s}s targets non-existent bus '{event.target_bus_id}'."
            )

        if event.event_type == ScenarioEventType.SET_SPEED:
            speed = event.parameters.get("speed_mps")
            if speed is None or float(speed) <= 0:
                errors.append(f"SET_SPEED event for '{event.target_bus_id}' must have positive speed_mps.")

        if event.event_type == ScenarioEventType.SET_CROWDING:
            state = event.parameters.get("crowding_state")
            valid_states = {"UNKNOWN", "LOW", "MODERATE", "HIGH", "FULL"}
            if state not in valid_states:
                errors.append(
                    f"SET_CROWDING event state '{state}' is invalid. Allowed: {valid_states}"
                )

    return errors


def build_scenario(
    name: str,
    settings: Settings,
    custom_buses: Optional[List[BusConfig]] = None,
) -> ScenarioDefinition:
    """
    Builds a scenario definition by name using configured operator credentials.
    """
    normalized_name = name.lower().strip()

    # Resolve primary operator
    primary_op = settings.get_primary_operator()
    p_code = primary_op.employee_code if primary_op else "O-001"
    p_pwd = primary_op.password if primary_op else "Password123!"

    # Resolve secondary operator if available, otherwise fallback to DRV001 from seed
    s_code = "DRV001"
    s_pwd = "operator123"
    if len(settings.operators) > 1:
        s_code = settings.operators[1].employee_code
        s_pwd = settings.operators[1].password

    if normalized_name in ("normal", "normal_single_bus"):
        bus1 = BusConfig(
            bus_id="bus-1",
            employee_code=p_code,
            password=p_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
            dwell_seconds=15.0,
        )
        return ScenarioDefinition(
            name="normal_single_bus",
            description="Normal single bus operating continuously along assigned route.",
            buses=[bus1],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.START_BUS, "bus-1"),
            ],
            duration_seconds=300.0,
        )

    elif normalized_name in ("delay", "delay_demo"):
        bus1 = BusConfig(
            bus_id="bus-1",
            employee_code=p_code,
            password=p_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
            dwell_seconds=15.0,
        )
        return ScenarioDefinition(
            name="delay_demo",
            description="Simulates traffic congestion: bus speed drops from 8.3m/s to 2.5m/s at T+20s, recovering at T+60s.",
            buses=[bus1],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.START_BUS, "bus-1"),
                ScenarioEvent(20.0, ScenarioEventType.SET_SPEED, "bus-1", {"speed_mps": 2.5}),
                ScenarioEvent(60.0, ScenarioEventType.RESTORE_SPEED, "bus-1"),
            ],
            duration_seconds=120.0,
        )

    elif normalized_name in ("offline", "offline_demo", "stale", "stale_demo"):
        bus1 = BusConfig(
            bus_id="bus-1",
            employee_code=p_code,
            password=p_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
            dwell_seconds=15.0,
        )
        return ScenarioDefinition(
            name="offline_demo",
            description="Simulates telemetry loss: bus ceases telemetry and heartbeat at T+20s, recovering at T+60s.",
            buses=[bus1],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.START_BUS, "bus-1"),
                ScenarioEvent(20.0, ScenarioEventType.SET_TELEMETRY_ENABLED, "bus-1", {"enabled": False}),
                ScenarioEvent(20.0, ScenarioEventType.SET_HEARTBEAT_ENABLED, "bus-1", {"enabled": False}),
                ScenarioEvent(60.0, ScenarioEventType.SET_TELEMETRY_ENABLED, "bus-1", {"enabled": True}),
                ScenarioEvent(60.0, ScenarioEventType.SET_HEARTBEAT_ENABLED, "bus-1", {"enabled": True}),
            ],
            duration_seconds=120.0,
        )

    elif normalized_name in ("crowding", "crowding_demo"):
        bus1 = BusConfig(
            bus_id="bus-1",
            employee_code=p_code,
            password=p_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
            dwell_seconds=15.0,
        )
        return ScenarioDefinition(
            name="crowding_demo",
            description="Submits verified crowding reports: HIGH at T+15s and FULL at T+45s via /api/crowding/reports.",
            buses=[bus1],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.START_BUS, "bus-1"),
                ScenarioEvent(15.0, ScenarioEventType.SET_CROWDING, "bus-1", {"crowding_state": "HIGH", "confidence": 0.9}),
                ScenarioEvent(45.0, ScenarioEventType.SET_CROWDING, "bus-1", {"crowding_state": "FULL", "confidence": 0.95}),
            ],
            duration_seconds=90.0,
        )

    elif normalized_name in ("shortage", "service_shortage", "service_shortage_demo"):
        # Defines 2 expected buses on the service, but only starts Bus 1; Bus 2 is withheld
        bus1 = BusConfig(
            bus_id="bus-1",
            employee_code=p_code,
            password=p_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
        )
        bus2 = BusConfig(
            bus_id="bus-2",
            employee_code=s_code,
            password=s_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
        )
        return ScenarioDefinition(
            name="service_shortage_demo",
            description="Demonstrates service shortage: schedules 2 buses, runs Bus 1 normally, withholds Bus 2.",
            buses=[bus1, bus2],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.START_BUS, "bus-1"),
                # Bus 2 is never started, allowing backend schedule vs. active monitoring to detect shortage
            ],
            duration_seconds=120.0,
        )

    elif normalized_name in ("multi", "multi_bus", "multi_bus_demo"):
        bus1 = BusConfig(
            bus_id="bus-1",
            employee_code=p_code,
            password=p_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
            direction="A_TO_B",
        )
        bus2 = BusConfig(
            bus_id="bus-2",
            employee_code=s_code,
            password=s_pwd,
            speed_mps=7.5,
            time_multiplier=1.0,
            direction="B_TO_A",
        )
        return ScenarioDefinition(
            name="multi_bus_demo",
            description="Simulates 2 independent buses running concurrently with staggered starts.",
            buses=[bus1, bus2],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.START_BUS, "bus-1"),
                ScenarioEvent(10.0, ScenarioEventType.START_BUS, "bus-2"),
            ],
            duration_seconds=180.0,
        )

    elif normalized_name in ("full", "full_demo"):
        bus1 = BusConfig(
            bus_id="bus-1",
            employee_code=p_code,
            password=p_pwd,
            speed_mps=8.33,
            time_multiplier=1.0,
        )
        bus2 = BusConfig(
            bus_id="bus-2",
            employee_code=s_code,
            password=s_pwd,
            speed_mps=7.5,
            time_multiplier=1.0,
        )
        return ScenarioDefinition(
            name="full_demo",
            description="Unified demo combining multi-bus, delay, stale recovery, and crowding in a single timeline.",
            buses=[bus1, bus2],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.START_BUS, "bus-1"),
                ScenarioEvent(10.0, ScenarioEventType.START_BUS, "bus-2"),
                ScenarioEvent(25.0, ScenarioEventType.SET_SPEED, "bus-1", {"speed_mps": 2.5}),
                ScenarioEvent(35.0, ScenarioEventType.SET_CROWDING, "bus-2", {"crowding_state": "HIGH", "confidence": 0.88}),
                ScenarioEvent(45.0, ScenarioEventType.SET_TELEMETRY_ENABLED, "bus-1", {"enabled": False}),
                ScenarioEvent(65.0, ScenarioEventType.SET_TELEMETRY_ENABLED, "bus-1", {"enabled": True}),
                ScenarioEvent(65.0, ScenarioEventType.RESTORE_SPEED, "bus-1"),
            ],
            duration_seconds=120.0,
        )

    else:
        raise SimulatorError(
            f"Unknown scenario '{name}'. Available built-in scenarios: "
            "normal_single_bus, multi_bus_demo, delay_demo, offline_demo, crowding_demo, service_shortage_demo, full_demo"
        )
