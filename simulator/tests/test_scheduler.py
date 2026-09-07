"""
Tests for ScenarioScheduler deterministic event execution.
"""

import unittest
from unittest.mock import MagicMock

from simulator.core.bus_simulator import BusConfig, BusLifecycle
from simulator.core.fleet import FleetManager
from simulator.core.scenario import ScenarioDefinition, ScenarioEvent, ScenarioEventType
from simulator.core.scheduler import ScenarioScheduler


class TestScheduler(unittest.TestCase):

    def setUp(self):
        self.fleet = FleetManager(backend_url="http://mock-backend:8000")
        self.b_conf = BusConfig("bus-1", "O-001", "pwd", speed_mps=10.0)
        self.fleet.add_bus(self.b_conf)
        self.bus = self.fleet.get_bus("bus-1")

        # Mock bus movement and backend methods
        self.bus.initialize_backend = MagicMock()
        self.bus.lifecycle = BusLifecycle.RUNNING
        self.bus.step = MagicMock(return_value={"packet_id": "pkt-1"})
        self.bus.transmit_packet = MagicMock()

    def test_scheduler_event_execution_timeline(self):
        scenario = ScenarioDefinition(
            name="test_timeline",
            description="Timeline test",
            buses=[self.b_conf],
            events=[
                ScenarioEvent(10.0, ScenarioEventType.SET_SPEED, "bus-1", {"speed_mps": 3.0}),
                ScenarioEvent(30.0, ScenarioEventType.RESTORE_SPEED, "bus-1"),
                ScenarioEvent(40.0, ScenarioEventType.SET_TELEMETRY_ENABLED, "bus-1", {"enabled": False}),
            ],
            duration_seconds=50.0,
        )
        scheduler = ScenarioScheduler(self.fleet, scenario, time_multiplier=1.0)

        # Tick 1: 5.0 seconds -> No events due yet (first is at 10.0s)
        res1 = scheduler.tick(5.0)
        self.assertEqual(res1["events_processed"], [])
        self.assertEqual(self.bus.current_speed_mps, 10.0)

        # Tick 2: 5.0 seconds -> Sim time = 10.0s -> SET_SPEED fires!
        res2 = scheduler.tick(5.0)
        self.assertEqual(res2["events_processed"], ["SET_SPEED"])
        self.assertEqual(self.bus.current_speed_mps, 3.0)

        # Tick 3: 20.0 seconds -> Sim time = 30.0s -> RESTORE_SPEED fires!
        res3 = scheduler.tick(20.0)
        self.assertEqual(res3["events_processed"], ["RESTORE_SPEED"])
        self.assertEqual(self.bus.current_speed_mps, 10.0)

        # Tick 4: 10.0 seconds -> Sim time = 40.0s -> SET_TELEMETRY_ENABLED fires!
        res4 = scheduler.tick(10.0)
        self.assertEqual(res4["events_processed"], ["SET_TELEMETRY_ENABLED"])
        self.assertFalse(self.bus.telemetry_enabled)

        # Tick 5: 10.0 seconds -> Sim time = 50.0s -> Duration reached!
        res5 = scheduler.tick(10.0)
        self.assertTrue(scheduler.is_completed)

    def test_wildcard_target_bus_event(self):
        # Adding a second bus
        b2_conf = BusConfig("bus-2", "DRV001", "pwd2", speed_mps=10.0)
        self.fleet.add_bus(b2_conf)
        bus2 = self.fleet.get_bus("bus-2")
        bus2.lifecycle = BusLifecycle.RUNNING
        bus2.step = MagicMock(return_value=None)

        scenario = ScenarioDefinition(
            name="wildcard_test",
            description="Testing target '*'",
            buses=[self.b_conf, b2_conf],
            events=[
                ScenarioEvent(0.0, ScenarioEventType.SET_SPEED, "*", {"speed_mps": 4.0}),
            ],
            duration_seconds=20.0,
        )
        scheduler = ScenarioScheduler(self.fleet, scenario, time_multiplier=1.0)

        scheduler.tick(1.0)
        self.assertEqual(self.bus.current_speed_mps, 4.0)
        self.assertEqual(bus2.current_speed_mps, 4.0)


if __name__ == "__main__":
    unittest.main()
