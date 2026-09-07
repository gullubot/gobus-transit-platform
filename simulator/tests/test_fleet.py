"""
Tests for FleetManager orchestration and credential uniqueness enforcement.
"""

import unittest
from unittest.mock import MagicMock, patch

from simulator.core.bus_simulator import BusConfig, BusLifecycle
from simulator.core.exceptions import SimulatorError
from simulator.core.fleet import FleetManager


class TestFleet(unittest.TestCase):

    def setUp(self):
        self.fleet = FleetManager(backend_url="http://mock-backend:8000")
        self.b1_config = BusConfig("bus-1", "O-001", "pwd1")
        self.b2_config = BusConfig("bus-2", "DRV001", "pwd2")

    def test_add_distinct_buses_success(self):
        self.fleet.add_bus(self.b1_config)
        self.fleet.add_bus(self.b2_config)
        self.assertEqual(self.fleet.bus_count, 2)

    def test_reject_duplicate_bus_id(self):
        self.fleet.add_bus(self.b1_config)
        duplicate_id_config = BusConfig("bus-1", "DRV002", "pwd3")
        with self.assertRaises(SimulatorError) as ctx:
            self.fleet.add_bus(duplicate_id_config)
        self.assertIn("Duplicate bus_id", str(ctx.exception))

    def test_reject_duplicate_operator_credentials(self):
        # NON-NEGOTIABLE RULE: 1 operator account cannot control multiple simultaneous buses
        self.fleet.add_bus(self.b1_config)
        duplicate_operator_config = BusConfig("bus-2", "O-001", "pwd1")
        with self.assertRaises(SimulatorError) as ctx:
            self.fleet.add_bus(duplicate_operator_config)
        self.assertIn("Duplicate operator credentials detected", str(ctx.exception))

    @patch("simulator.core.bus_simulator.BusSimulator.initialize_backend")
    def test_fleet_error_isolation(self, mock_init):
        # Bus 1 succeeds, Bus 2 throws error
        def side_effect_init():
            return None
        self.fleet.add_bus(self.b1_config)
        self.fleet.add_bus(self.b2_config)

        bus1 = self.fleet.get_bus("bus-1")
        bus2 = self.fleet.get_bus("bus-2")

        bus1.initialize_backend = MagicMock(return_value=None)
        bus1.lifecycle = BusLifecycle.RUNNING
        bus2.initialize_backend = MagicMock(side_effect=Exception("Database locked"))

        init_results = self.fleet.initialize_fleet()
        self.assertTrue(init_results["bus-1"])
        self.assertFalse(init_results["bus-2"])
        # Bus 1 continues running despite Bus 2 failure
        self.assertEqual(bus1.lifecycle, BusLifecycle.RUNNING)

    def test_stop_fleet_calls_stop_on_all_buses(self):
        self.fleet.add_bus(self.b1_config)
        self.fleet.add_bus(self.b2_config)

        b1 = self.fleet.get_bus("bus-1")
        b2 = self.fleet.get_bus("bus-2")
        b1.stop = MagicMock()
        b2.stop = MagicMock()

        self.fleet.stop_fleet()
        b1.stop.assert_called_once()
        b2.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
