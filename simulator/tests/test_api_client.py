"""
Tests for GoBusHttpClient.
"""

import unittest
from unittest.mock import MagicMock, patch
import requests

from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import (
    AccountForbiddenError,
    AssignmentNotFoundError,
    AuthenticationError,
    BackendUnavailableError,
    InvalidPayloadError,
    RateLimitExceededError,
    TripSessionError,
)


class TestGoBusHttpClient(unittest.TestCase):

    def setUp(self):
        self.client = GoBusHttpClient(base_url="http://mock-backend:8000", timeout=5.0)

    def tearDown(self):
        self.client.close()

    def test_url_construction(self):
        self.assertEqual(self.client._build_url("/api/health"), "http://mock-backend:8000/api/health")
        self.assertEqual(self.client._build_url("api/health"), "http://mock-backend:8000/api/health")
        self.assertEqual(self.client._build_url("http://other:9000/api/test"), "http://other:9000/api/test")

    @patch("requests.Session.request")
    def test_get_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_resp

        result = self.client.get("/api/test", token="mock-token")
        self.assertEqual(result, {"status": "ok"})
        mock_request.assert_called_once()
        headers = mock_request.call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer mock-token")

    @patch("requests.Session.request")
    def test_post_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "123"}
        mock_request.return_value = mock_resp

        result = self.client.post("/api/submit", json_data={"key": "val"}, token="mock-token")
        self.assertEqual(result, {"id": "123"})
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer mock-token")
        self.assertEqual(call_kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(call_kwargs["json"], {"key": "val"})

    @patch("requests.Session.request")
    def test_http_401_authentication_error(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"detail": "Invalid credentials"}
        mock_request.return_value = mock_resp

        with self.assertRaises(AuthenticationError) as ctx:
            self.client.get("/api/protected")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid credentials", str(ctx.exception))

    @patch("requests.Session.request")
    def test_http_403_forbidden_error(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"detail": "User account is inactive"}
        mock_request.return_value = mock_resp

        with self.assertRaises(AccountForbiddenError) as ctx:
            self.client.get("/api/protected")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("inactive", str(ctx.exception))

    @patch("requests.Session.request")
    def test_http_404_not_found(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Assignment not found"}
        mock_request.return_value = mock_resp

        with self.assertRaises(AssignmentNotFoundError) as ctx:
            self.client.get("/api/operator/me/assignment")
        self.assertEqual(ctx.exception.status_code, 404)

    @patch("requests.Session.request")
    def test_http_422_invalid_payload(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {"detail": "Field required"}
        mock_request.return_value = mock_resp

        with self.assertRaises(InvalidPayloadError) as ctx:
            self.client.post("/api/test", json_data={})
        self.assertEqual(ctx.exception.status_code, 422)

    @patch("requests.Session.request")
    def test_http_429_rate_limit(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"detail": "Operator rate limit exceeded"}
        mock_request.return_value = mock_resp

        with self.assertRaises(RateLimitExceededError) as ctx:
            self.client.post("/api/crowding/reports", json_data={})
        self.assertEqual(ctx.exception.status_code, 429)

    @patch("requests.Session.request")
    def test_connection_error_raises_backend_unavailable(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with self.assertRaises(BackendUnavailableError):
            self.client.get("/api/health")

    @patch("requests.Session.request")
    def test_timeout_raises_backend_unavailable(self, mock_request):
        mock_request.side_effect = requests.exceptions.Timeout("Request timed out")

        with self.assertRaises(BackendUnavailableError):
            self.client.get("/api/health")


if __name__ == "__main__":
    unittest.main()
