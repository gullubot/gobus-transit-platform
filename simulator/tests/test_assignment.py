"""
Tests for duty assignment client.
"""

import unittest
from unittest.mock import MagicMock

from simulator.api.assignment import fetch_operator_assignment
from simulator.core.exceptions import AssignmentNotFoundError, AuthenticationError
from simulator.core.session import OperatorSession, SimulationMode


class TestAssignment(unittest.TestCase):

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

    def test_fetch_assignment_success(self):
        self.mock_client.get.return_value = {
            "assignment_id": "as-100",
            "trip_id": "tr-200",
            "service_id": "sv-300",
            "service_code": "AC4B",
            "service_name": "Howrah to Salt Lake",
            "route_id": "rt-400",
            "route_code": "SD5",
            "route_name": "Express Route 5",
            "direction": "A_TO_B",
            "vehicle_id": "veh-500",
            "vehicle_number": "WB04-1234",
            "planned_start_at": "2026-09-03T08:00:00Z",
            "trip_status": "PLANNED",
            "operator_role": "DRIVER",
            "assignment_status": "ASSIGNED",
            "assigned_device_id": "dev-600",
            "assigned_device_status": "ACTIVE",
            "active_tracking_session_id": None,
            "tracking_session_status": None,
        }

        assignment = fetch_operator_assignment(self.mock_client, self.session)

        self.mock_client.get.assert_called_once_with(
            "/api/operator/me/assignment",
            token="valid-token"
        )
        self.assertEqual(assignment.trip_id, "tr-200")
        self.assertEqual(assignment.service_code, "AC4B")
        self.assertEqual(assignment.vehicle_number, "WB04-1234")
        self.assertEqual(assignment.direction, "A_TO_B")
        self.assertEqual(self.session.mode, SimulationMode.ASSIGNED)
        self.assertEqual(self.session.device_id, "dev-600")

    def test_fetch_assignment_unauthenticated_fails(self):
        unauth_session = OperatorSession(employee_code="O-001")
        with self.assertRaises(AuthenticationError):
            fetch_operator_assignment(self.mock_client, unauth_session)

    def test_assignment_not_found_raises_clean_error(self):
        self.mock_client.get.side_effect = AssignmentNotFoundError("No assignment")

        with self.assertRaises(AssignmentNotFoundError) as ctx:
            fetch_operator_assignment(self.mock_client, self.session)
        self.assertIn("dispatch a trip to this operator", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
