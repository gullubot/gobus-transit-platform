"""
Tests for operator authentication adapter.
"""

import unittest
from unittest.mock import MagicMock

from simulator.api.auth import operator_login, operator_logout
from simulator.core.exceptions import AuthenticationError
from simulator.core.session import OperatorSession, SimulationMode


class TestOperatorAuth(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.session = OperatorSession(employee_code="O-001")

    def test_successful_login(self):
        self.mock_client.post.return_value = {
            "access_token": "mock.jwt.token",
            "token_type": "bearer",
            "user_id": "u-123",
            "name": "Demo Driver",
            "role": "DRIVER",
            "employee_code": "O-001",
            "organization_id": "org-456",
            "organization_name": "WBTC Kolkata",
        }

        operator_login(self.mock_client, self.session, "Password123!")

        # Verify client called with exact JSON endpoint and payload
        self.mock_client.post.assert_called_once_with(
            "/api/auth/operator/login",
            json_data={"employee_code": "O-001", "password": "Password123!"}
        )

        # Verify session state updated
        self.assertEqual(self.session.mode, SimulationMode.AUTHENTICATED)
        self.assertEqual(self.session.access_token, "mock.jwt.token")
        self.assertEqual(self.session.user_id, "u-123")
        self.assertEqual(self.session.name, "Demo Driver")
        self.assertEqual(self.session.role, "DRIVER")
        self.assertEqual(self.session.organization_id, "org-456")
        self.assertEqual(self.session.organization_name, "WBTC Kolkata")

    def test_missing_access_token_in_response(self):
        self.mock_client.post.return_value = {"status": "ok"}  # Missing access_token

        with self.assertRaises(AuthenticationError) as ctx:
            operator_login(self.mock_client, self.session, "Password123!")
        self.assertIn("valid 'access_token'", str(ctx.exception))

    def test_missing_credentials_raises_error(self):
        empty_session = OperatorSession(employee_code="")
        with self.assertRaises(AuthenticationError):
            operator_login(self.mock_client, empty_session, "pass")

        with self.assertRaises(AuthenticationError):
            operator_login(self.mock_client, self.session, "")

    def test_logout_clears_session(self):
        self.session.set_authenticated(
            token="token123",
            user_id="u1",
            name="Driver",
            role="DRIVER",
            organization_id="org1",
            organization_name="Org",
        )
        self.assertEqual(self.session.mode, SimulationMode.AUTHENTICATED)

        operator_logout(self.session)
        self.assertEqual(self.session.mode, SimulationMode.DISCONNECTED)
        self.assertIsNone(self.session.access_token)


if __name__ == "__main__":
    unittest.main()
