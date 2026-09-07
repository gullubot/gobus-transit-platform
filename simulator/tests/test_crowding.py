"""
Tests for crowding report client.
"""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock
import uuid

from simulator.api.crowding import submit_crowding_report
from simulator.core.exceptions import AuthenticationError, RateLimitExceededError
from simulator.core.session import AssignmentContext, OperatorSession


class TestCrowding(unittest.TestCase):

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
            trip_id="tr-1",
            service_id="sv-1",
            service_code="AC4B",
            service_name="Route",
            route_id="rt-1",
            route_code="SD5",
            route_name="Route",
            direction="A_TO_B",
            vehicle_id="veh-888",
            vehicle_number="WB04-1234",
            planned_start_at="2026-09-03T08:00:00Z",
            trip_status="PLANNED",
            operator_role="DRIVER",
            assignment_status="ASSIGNED",
        )
        self.session.set_assigned(self.assignment)

    def test_submit_crowding_report_valid(self):
        now = datetime(2026, 9, 3, 11, 0, 0, tzinfo=timezone.utc)
        self.mock_client.post.return_value = {
            "report_id": "rep-123",
            "vehicle_id": "veh-888",
            "crowding_state": "HIGH",
            "confidence": 0.85,
            "observed_at": "2026-09-03T11:00:00.000Z",
            "received_at": "2026-09-03T11:00:01.000Z",
            "source_type": "OPERATOR",
        }

        resp = submit_crowding_report(
            self.mock_client,
            self.session,
            crowding_state="HIGH",
            confidence=0.85,
            observed_at=now,
            report_id="rep-123",
        )

        self.mock_client.post.assert_called_once()
        call_args = self.mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/api/crowding/reports")
        json_payload = call_args[1]["json_data"]

        # 1. Exact verified fields
        self.assertEqual(json_payload["report_id"], "rep-123")
        self.assertEqual(json_payload["vehicle_id"], "veh-888")
        self.assertEqual(json_payload["crowding_state"], "HIGH")
        self.assertEqual(json_payload["confidence"], 0.85)
        self.assertEqual(json_payload["observed_at"], "2026-09-03T11:00:00.000Z")

        # 2. CRITICAL: NEVER send 'level' or 'source_type'
        self.assertNotIn("level", json_payload)
        self.assertNotIn("source_type", json_payload)

        self.assertEqual(resp["crowding_state"], "HIGH")

    def test_invalid_crowding_state_raises_error(self):
        with self.assertRaises(ValueError) as ctx:
            submit_crowding_report(self.mock_client, self.session, crowding_state="JAMMED")
        self.assertIn("Invalid crowding_state", str(ctx.exception))

    def test_invalid_confidence_raises_error(self):
        with self.assertRaises(ValueError):
            submit_crowding_report(self.mock_client, self.session, confidence=1.5)

    def test_rate_limit_exceeded_handled(self):
        self.mock_client.post.side_effect = RateLimitExceededError("Operator rate limit exceeded")

        with self.assertRaises(RateLimitExceededError):
            submit_crowding_report(self.mock_client, self.session, crowding_state="FULL")


if __name__ == "__main__":
    unittest.main()
