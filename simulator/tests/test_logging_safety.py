"""
Tests for secret and token redaction in simulator logging.
"""

import logging
import unittest

from simulator.utils.logging import RedactingFilter


class TestLoggingSafety(unittest.TestCase):

    def setUp(self):
        self.filter = RedactingFilter()

    def test_jwt_redaction(self):
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgN_p_mock_signature"
        raw_message = f"Received auth token: {token} for user"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg=raw_message,
            args=(),
            exc_info=None,
        )

        self.filter.filter(record)
        self.assertNotIn("eyJhbGciOi", record.msg)
        self.assertNotIn("dozjgN_p_mock_signature", record.msg)
        self.assertIn("[REDACTED_JWT]", record.msg)

    def test_bearer_token_redaction(self):
        raw_message = "Sending header Authorization: Bearer abcdef123456789 to server"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=20,
            msg=raw_message,
            args=(),
            exc_info=None,
        )

        self.filter.filter(record)
        self.assertNotIn("abcdef123456789", record.msg)
        self.assertIn("Bearer [REDACTED_TOKEN]", record.msg)

    def test_password_redaction(self):
        raw_message = 'Payload contains {"employee_code": "O-001", "password": "SuperSecretPassword123!"}'
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=30,
            msg=raw_message,
            args=(),
            exc_info=None,
        )

        self.filter.filter(record)
        self.assertNotIn("SuperSecretPassword123!", record.msg)
        self.assertIn('"password": "***REDACTED***"', record.msg)


if __name__ == "__main__":
    unittest.main()
