"""
Tests for BusSimulator virtual device context and lifecycle.
"""

import unittest
from unittest.mock import MagicMock, patch

from simulator.core.bus_simulator import BusConfig, BusLifecycle, BusSimulator
from simulator.core.route import RouteModel, SimulatedStop


class TestBusSimulator(unittest.TestCase):

    def setUp(self):
        self.config = BusConfig(
            bus_id="bus-1",
            employee_code="O-001",
            password="Password123!",
            speed_mps=10.0,
            time_multiplier=1.0,
            dwell_seconds=5.0,
        )
        self.bus = BusSimulator(
            config=self.config,
            backend_url="http://mock-backend:8000",
        )

        stop1 = SimulatedStop("s1", "Stop 1", 1, 22.5000, 88.3000)
        stop2 = SimulatedStop("s2", "Stop 2", 2, 22.5100, 88.3000)
        self.route = RouteModel("r1", "SD5", "Route", [stop1, stop2])

    @patch("simulator.core.bus_simulator.operator_login")
    @patch("simulator.core.bus_simulator.fetch_operator_assignment")
    @patch("simulator.core.bus_simulator.fetch_service_route")
    @patch("simulator.core.bus_simulator.start_trip_tracking")
    def test_initialize_backend_success(self, mock_start, mock_route, mock_assign, mock_login):
        mock_assign.return_value = MagicMock(service_id="srv-1", service_code="SD5", direction="A_TO_B", trip_id="tr-1")
        mock_route.return_value = self.route
        mock_start.return_value = {"tracking_session_id": "sess-100", "device_id": "dev-200"}

        self.bus.initialize_backend()

        self.assertEqual(self.bus.lifecycle, BusLifecycle.RUNNING)
        self.assertIsNotNone(self.bus.movement)
        self.assertIsNotNone(self.bus.route)
        self.assertIsNone(self.bus.error_message)

    @patch("simulator.core.bus_simulator.operator_login")
    def test_initialize_backend_error_isolated(self, mock_login):
        mock_login.side_effect = Exception("Invalid credentials")

        with self.assertRaises(Exception):
            self.bus.initialize_backend()

        self.assertEqual(self.bus.lifecycle, BusLifecycle.ERROR)
        self.assertIn("Invalid credentials", self.bus.error_message)

    def test_step_when_telemetry_disabled(self):
        # Manually set up running state
        self.bus.lifecycle = BusLifecycle.RUNNING
        self.bus.route = self.route
        from simulator.core.movement import MovementEngine
        self.bus.movement = MovementEngine(self.route, cruise_speed_mps=10.0)

        # Telemetry enabled: returns packet
        pkt1 = self.bus.step(1.0)
        self.assertIsNotNone(pkt1)

        # Telemetry disabled: returns None (stale/offline condition)
        self.bus.telemetry_enabled = False
        pkt2 = self.bus.step(1.0)
        self.assertIsNone(pkt2)

    def test_speed_modifier(self):
        self.bus.lifecycle = BusLifecycle.RUNNING
        self.bus.route = self.route
        from simulator.core.movement import MovementEngine
        self.bus.movement = MovementEngine(self.route, cruise_speed_mps=10.0)

        self.bus.set_speed(3.0)
        self.assertEqual(self.bus.current_speed_mps, 3.0)
        self.assertEqual(self.bus.movement.cruise_speed_mps, 3.0)

        self.bus.restore_speed()
        self.assertEqual(self.bus.current_speed_mps, 10.0)
        self.assertEqual(self.bus.movement.cruise_speed_mps, 10.0)

    def test_pause_and_resume(self):
        self.bus.lifecycle = BusLifecycle.RUNNING
        self.bus.pause()
        self.assertEqual(self.bus.lifecycle, BusLifecycle.PAUSED)
        self.assertTrue(self.bus.clock.is_paused)

        self.bus.resume()
        self.assertEqual(self.bus.lifecycle, BusLifecycle.RUNNING)
        self.assertFalse(self.bus.clock.is_paused)


if __name__ == "__main__":
    unittest.main()
