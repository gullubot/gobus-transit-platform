"""
Tests for device heartbeat client.
"""

import unittest
from unittest.mock import MagicMock

from simulator.api.heartbeat import send_device_heartbeat
from simulator.core.exceptions import AuthenticationError
from simulator.core.session import OperatorSession


class TestHeartbeat(unittest.TestCase):

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
        self.session.set_tracking_started("sess-100", "dev-200")

    def test_send_heartbeat_success(self):
        self.mock_client.post.return_value = {
            "status": "ok",
            "received_at": "2026-09-03T10:00:00Z",
            "device_status": "ACTIVE",
            "session_status": "ACTIVE",
        }

        resp = send_device_heartbeat(
            self.mock_client,
            self.session,
            battery_level=88.5,
            network_type="4G",
            gps_status="AVAILABLE",
            app_version="1.0.0",
        )

        self.mock_client.post.assert_called_once()
        call_args = self.mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/api/tracking/heartbeat")
        json_payload = call_args[1]["json_data"]
        self.assertEqual(json_payload["session_id"], "sess-100")
        self.assertEqual(json_payload["battery_level"], 88.5)
        self.assertEqual(json_payload["network_type"], "4G")
        self.assertEqual(json_payload["gps_status"], "AVAILABLE")
        self.assertEqual(json_payload["app_version"], "1.0.0")
        self.assertIn("timestamp", json_payload)

        self.assertEqual(resp["status"], "ok")
        self.assertEqual(resp["device_status"], "ACTIVE")

    def test_heartbeat_unauthenticated_fails(self):
        unauth_session = OperatorSession(employee_code="O-001")
        with self.assertRaises(AuthenticationError):
            send_device_heartbeat(self.mock_client, unauth_session)


if __name__ == "__main__":
    unittest.main()
