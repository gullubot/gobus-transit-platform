"""
Tests for batch telemetry ingestion client and packet construction.
"""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock
import uuid

from simulator.api.telemetry import create_telemetry_packet, send_telemetry_batch
from simulator.core.exceptions import AuthenticationError
from simulator.core.session import OperatorSession


class TestTelemetry(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.session = OperatorSession(employee_code="O-001")
        self.session.set_authenticated(
            token="valid-token",
            user_id="u1",
            name="Driver",
            role="DRIVER",
            organization_id="org1",
            organization_name="Org",
        )
        self.session.set_tracking_started("sess-123", "dev-456")

    def test_create_telemetry_packet_valid(self):
        now = datetime(2026, 9, 3, 10, 30, 0, tzinfo=timezone.utc)
        packet = create_telemetry_packet(
            latitude=22.572646,
            longitude=88.363895,
            device_sequence=1,
            speed_mps=8.5,
            heading=180.0,
            accuracy_m=4.5,
            observed_at=now,
            battery_level=90.0,
            network_type="CELLULAR",
            gps_status="AVAILABLE",
        )

        # 1. Packet identity
        self.assertTrue(uuid.UUID(packet["packet_id"]))
        # 2. Coordinates
        self.assertEqual(packet["latitude"], 22.572646)
        self.assertEqual(packet["longitude"], 88.363895)
        # 3. Monotonic sequence
        self.assertEqual(packet["device_sequence"], 1)
        # 4. UTC timestamp ISO format
        self.assertEqual(packet["observed_at"], "2026-09-03T10:30:00.000Z")
        # 5. Device telemetry
        self.assertEqual(packet["speed_mps"], 8.5)
        self.assertEqual(packet["heading"], 180.0)
        self.assertEqual(packet["accuracy_m"], 4.5)
        self.assertEqual(packet["battery_level"], 90.0)
        self.assertEqual(packet["network_type"], "CELLULAR")
        self.assertEqual(packet["gps_status"], "AVAILABLE")

        # 6. CRITICAL VERIFICATION: packet MUST NOT contain vehicle_id or route_id!
        self.assertNotIn("vehicle_id", packet)
        self.assertNotIn("route_id", packet)
        self.assertNotIn("service_id", packet)

    def test_invalid_coordinates_raise_error(self):
        with self.assertRaises(ValueError):
            create_telemetry_packet(latitude=95.0, longitude=88.0, device_sequence=1)

        with self.assertRaises(ValueError):
            create_telemetry_packet(latitude=22.0, longitude=185.0, device_sequence=1)

    def test_send_telemetry_batch_success(self):
        pkt1 = create_telemetry_packet(22.57, 88.36, device_sequence=1)
        pkt2 = create_telemetry_packet(22.58, 88.37, device_sequence=2)

        self.mock_client.post.return_value = {
            "accepted": [pkt1["packet_id"], pkt2["packet_id"]],
            "duplicates": [],
            "retryable": [],
            "rejected": [],
        }

        result = send_telemetry_batch(self.mock_client, self.session, [pkt1, pkt2])

        self.mock_client.post.assert_called_once_with(
            "/api/tracking/batch",
            json_data={"packets": [pkt1, pkt2], "session_id": "sess-123"},
            token="valid-token"
        )
        self.assertTrue(result.is_fully_accepted)
        self.assertEqual(len(result.accepted), 2)
        self.assertEqual(len(result.rejected), 0)

    def test_send_telemetry_batch_with_rejected_and_duplicates(self):
        pkt = create_telemetry_packet(22.57, 88.36, device_sequence=1)
        self.mock_client.post.return_value = {
            "accepted": [],
            "duplicates": [pkt["packet_id"]],
            "retryable": [],
            "rejected": [{"packet_id": "bad-id", "reason": "Coordinates out of range"}],
        }

        result = send_telemetry_batch(self.mock_client, self.session, [pkt])
        self.assertFalse(result.is_fully_accepted)
        self.assertEqual(len(result.duplicates), 1)
        self.assertEqual(len(result.rejected), 1)
        self.assertEqual(result.rejected[0].reason, "Coordinates out of range")

    def test_send_empty_or_oversized_batch_fails(self):
        with self.assertRaises(ValueError):
            send_telemetry_batch(self.mock_client, self.session, [])

        oversized = [create_telemetry_packet(22.57, 88.36, i) for i in range(501)]
        with self.assertRaises(ValueError):
            send_telemetry_batch(self.mock_client, self.session, oversized)


if __name__ == "__main__":
    unittest.main()
