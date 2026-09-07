"""
Tests for trip tracking session lifecycle client (/start and /end).
"""

import unittest
from unittest.mock import MagicMock

from simulator.api.trip import start_trip_tracking, end_trip_tracking
from simulator.core.exceptions import AuthenticationError, TripSessionError
from simulator.core.session import AssignmentContext, OperatorSession, SimulationMode


class TestTripLifecycle(unittest.TestCase):

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
        self.assignment = AssignmentContext(
            assignment_id="as-1",
            trip_id="tr-100",
            service_id="sv-1",
            service_code="AC4B",
            service_name="Salt Lake",
            route_id="rt-1",
            route_code="SD5",
            route_name="Route 5",
            direction="A_TO_B",
            vehicle_id="vh-1",
            vehicle_number="WB04-1234",
            planned_start_at="2026-09-03T08:00:00Z",
            trip_status="PLANNED",
            operator_role="DRIVER",
            assignment_status="ASSIGNED",
            assigned_device_id="dev-1",
        )
        self.session.set_assigned(self.assignment)

    def test_start_trip_success(self):
        self.mock_client.post.return_value = {
            "tracking_session_id": "sess-999",
            "trip_id": "tr-100",
            "device_id": "dev-1",
            "status": "ACTIVE",
            "started_at": "2026-09-03T08:01:00Z",
        }

        resp = start_trip_tracking(self.mock_client, self.session)

        self.mock_client.post.assert_called_once_with(
            "/api/trips/tr-100/start",
            json_data={},
            token="valid-token"
        )
        self.assertEqual(resp["tracking_session_id"], "sess-999")
        self.assertEqual(self.session.mode, SimulationMode.TRACKING)
        self.assertEqual(self.session.active_tracking_session_id, "sess-999")
        self.assertEqual(self.session.device_sequence, 0)

    def test_start_trip_unauthenticated_fails(self):
        unauth_session = OperatorSession(employee_code="O-001")
        with self.assertRaises(AuthenticationError):
            start_trip_tracking(self.mock_client, unauth_session, trip_id="tr-100")

    def test_end_trip_success(self):
        self.session.set_tracking_started("sess-999", "dev-1")
        self.mock_client.post.return_value = {
            "tracking_session_id": "sess-999",
            "trip_id": "tr-100",
            "status": "ENDED",
            "ended_at": "2026-09-03T08:45:00Z",
        }

        resp = end_trip_tracking(self.mock_client, self.session)

        self.mock_client.post.assert_called_once_with(
            "/api/trips/tr-100/end",
            json_data={},
            token="valid-token"
        )
        self.assertEqual(resp["status"], "ENDED")
        self.assertEqual(self.session.mode, SimulationMode.STOPPED)
        self.assertIsNone(self.session.active_tracking_session_id)


if __name__ == "__main__":
    unittest.main()
