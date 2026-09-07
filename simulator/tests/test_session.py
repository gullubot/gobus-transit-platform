"""
Tests for OperatorSession model and simulation state machine.
"""

import unittest

from simulator.core.session import AssignmentContext, OperatorSession, SimulationMode


class TestOperatorSession(unittest.TestCase):

    def test_session_state_progression(self):
        session = OperatorSession(employee_code="O-001")
        self.assertEqual(session.mode, SimulationMode.DISCONNECTED)
        self.assertIsNone(session.access_token)

        # 1. Authenticate
        session.set_authenticated(
            token="jwt.header.payload",
            user_id="u1",
            name="Driver",
            role="DRIVER",
            organization_id="org1",
            organization_name="WBTC",
        )
        self.assertEqual(session.mode, SimulationMode.AUTHENTICATED)
        self.assertEqual(session.access_token, "jwt.header.payload")

        # 2. Assign
        assignment = AssignmentContext(
            assignment_id="as1",
            trip_id="tr1",
            service_id="sv1",
            service_code="AC4B",
            service_name="Service",
            route_id="rt1",
            route_code="SD5",
            route_name="Route",
            direction="A_TO_B",
            vehicle_id="vh1",
            vehicle_number="WB04-1234",
            planned_start_at="2026-09-03T08:00:00Z",
            trip_status="PLANNED",
            operator_role="DRIVER",
            assignment_status="ASSIGNED",
            assigned_device_id="dev1",
        )
        session.set_assigned(assignment)
        self.assertEqual(session.mode, SimulationMode.ASSIGNED)
        self.assertEqual(session.device_id, "dev1")

        # 3. Track
        session.set_tracking_started("sess100", "dev1")
        self.assertEqual(session.mode, SimulationMode.TRACKING)
        self.assertEqual(session.active_tracking_session_id, "sess100")
        self.assertEqual(session.device_sequence, 0)

        # 4. Monotonic sequence increment
        self.assertEqual(session.next_sequence(), 1)
        self.assertEqual(session.next_sequence(), 2)
        self.assertEqual(session.next_sequence(), 3)
        self.assertEqual(session.device_sequence, 3)

        # 5. Stop
        session.set_tracking_ended()
        self.assertEqual(session.mode, SimulationMode.STOPPED)
        self.assertIsNone(session.active_tracking_session_id)

        # 6. Clear / Logout
        session.clear()
        self.assertEqual(session.mode, SimulationMode.DISCONNECTED)
        self.assertIsNone(session.access_token)

    def test_token_redacted_from_repr(self):
        session = OperatorSession(employee_code="O-001")
        session.set_authenticated(
            token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive_payload.signature",
            user_id="u1",
            name="Driver",
            role="DRIVER",
            organization_id="org1",
            organization_name="WBTC",
        )
        repr_str = repr(session)
        self.assertNotIn("eyJ", repr_str)
        self.assertNotIn("sensitive_payload", repr_str)

    def test_safe_summary_does_not_contain_secrets(self):
        session = OperatorSession(employee_code="O-001")
        session.set_authenticated(
            token="secret_token",
            user_id="u1",
            name="Driver",
            role="DRIVER",
            organization_id="org1",
            organization_name="WBTC",
        )
        summary = session.safe_summary()
        self.assertNotIn("access_token", summary)
        self.assertNotIn("token", summary)
        self.assertEqual(summary["employee_code"], "O-001")
        self.assertEqual(summary["mode"], "AUTHENTICATED")


if __name__ == "__main__":
    unittest.main()
