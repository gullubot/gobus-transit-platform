"""
Tests for TelemetryGenerator and packet contract adherence.
"""

from datetime import datetime, timezone
import unittest
import uuid

from simulator.core.clock import SimulationClock
from simulator.core.movement import MovementEngine
from simulator.core.route import RouteModel, SimulatedStop
from simulator.core.session import OperatorSession
from simulator.core.telemetry_generator import TelemetryGenerator


class TestTelemetryGenerator(unittest.TestCase):

    def setUp(self):
        self.stop1 = SimulatedStop("s1", "Stop 1", 1, 22.5000, 88.3000)
        self.stop2 = SimulatedStop("s2", "Stop 2", 2, 22.5100, 88.3000)
        self.route = RouteModel("r1", "R1", "Route", [self.stop1, self.stop2])

        self.session = OperatorSession(employee_code="O-001")
        self.session.set_authenticated(
            token="jwt-token",
            user_id="u1",
            name="Driver",
            role="DRIVER",
            organization_id="org1",
            organization_name="Org",
        )
        self.session.set_tracking_started("sess-1", "dev-1")

        start_time = datetime(2026, 9, 3, 10, 0, 0, tzinfo=timezone.utc)
        self.clock = SimulationClock(start_time=start_time)
        self.movement = MovementEngine(self.route, cruise_speed_mps=10.0)
        self.generator = TelemetryGenerator(self.session, self.clock)

    def test_generate_packet_fields(self):
        state = self.movement.advance(5.0)  # Move 50m
        self.clock.tick(5.0)

        packet = self.generator.generate_packet(state)

        # 1. Packet identity
        self.assertTrue(uuid.UUID(packet["packet_id"]))
        # 2. Coordinates
        self.assertEqual(packet["latitude"], state.current_latitude)
        self.assertEqual(packet["longitude"], state.current_longitude)
        # 3. Speed & Heading
        self.assertEqual(packet["speed_mps"], state.current_speed_mps)
        self.assertEqual(packet["heading"], state.current_heading)
        # 4. Monotonic device sequence
        self.assertEqual(packet["device_sequence"], 1)
        # 5. Timestamp
        self.assertEqual(packet["observed_at"], "2026-09-03T10:00:05.000Z")
        # 6. Device status
        self.assertEqual(packet["gps_status"], "AVAILABLE")
        self.assertEqual(packet["network_type"], "CELLULAR")
        self.assertGreater(packet["battery_level"], 95.0)

        # 7. CRITICAL ARCHITECTURAL CONTRACT:
        # Never include vehicle_id, route_id, or service_id in packet!
        self.assertNotIn("vehicle_id", packet)
        self.assertNotIn("route_id", packet)
        self.assertNotIn("service_id", packet)

    def test_sequence_increments_monotonically(self):
        state = self.movement.get_state()
        p1 = self.generator.generate_packet(state)
        p2 = self.generator.generate_packet(state)
        p3 = self.generator.generate_packet(state)

        self.assertEqual(p1["device_sequence"], 1)
        self.assertEqual(p2["device_sequence"], 2)
        self.assertEqual(p3["device_sequence"], 3)


if __name__ == "__main__":
    unittest.main()
