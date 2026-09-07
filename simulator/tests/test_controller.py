"""
Unit tests for SimulationController (Phase 4).
Tests lifecycle state transitions, concurrency safety, reset confirmation,
and secret exclusion.
"""

import json
import unittest

from simulator.config.settings import Settings
from simulator.server.controller import ConflictError, SimulationController, SimulationLifecycle


class TestSimulationController(unittest.TestCase):

    def setUp(self):
        self.settings = Settings(
            backend_url="http://localhost:8000",
            operator_employee_code="O-001",
            operator_password="Password123!",
            request_timeout=2.0,
        )
        self.controller = SimulationController(settings=self.settings)

    def tearDown(self):
        # Always clean up controller state
        self.controller.reset(confirm_backend_cleanup=True)

    def test_initial_state(self):
        """Initial lifecycle must be IDLE and state projection must be complete."""
        self.assertEqual(self.controller.lifecycle, SimulationLifecycle.IDLE)
        state = self.controller.get_state()
        self.assertEqual(state["lifecycle"], "IDLE")
        self.assertEqual(state["simulation_time_s"], 0.0)
        self.assertEqual(state["tick_count"], 0)
        self.assertEqual(len(state["fleet"]), 0)
        self.assertIn("metrics", state)
        self.assertIn("timeline", state)
        self.assertIn("event_log", state)

    def test_pause_and_resume_invalid_when_idle(self):
        """Pausing or resuming while IDLE must raise ConflictError."""
        with self.assertRaises(ConflictError):
            self.controller.pause()

        with self.assertRaises(ConflictError):
            self.controller.resume()

    def test_local_reset_when_idle(self):
        """Resetting when already IDLE must succeed cleanly."""
        res = self.controller.reset(confirm_backend_cleanup=False)
        self.assertEqual(res["status"], "IDLE")
        self.assertEqual(self.controller.lifecycle, SimulationLifecycle.IDLE)

    def test_list_and_get_scenarios(self):
        """Scenarios list and detail must return safe metadata."""
        scenarios = self.controller.list_scenarios()
        self.assertTrue(len(scenarios) >= 7)
        names = [s["name"] for s in scenarios]
        self.assertIn("full_demo", names)
        self.assertIn("delay_demo", names)

        detail = self.controller.get_scenario_detail("full_demo")
        self.assertEqual(detail["name"], "full_demo")
        self.assertEqual(len(detail["buses"]), 2)
        self.assertTrue(len(detail["events"]) > 0)

    def test_offline_scenario_validation(self):
        """Dry-run validation must succeed for built-in scenarios."""
        valid, errors = self.controller.validate("full_demo")
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)

        valid_bad, errors_bad = self.controller.validate("non_existent_scenario")
        self.assertFalse(valid_bad)
        self.assertTrue(len(errors_bad) > 0)

    def test_secret_exclusion_in_state_projection(self):
        """
        CRITICAL SECURITY REQUIREMENT:
        State projection must NEVER contain passwords, JWTs, or Bearer tokens.
        """
        state = self.controller.get_state()
        serialized = json.dumps(state).lower()

        self.assertNotIn("password", serialized)
        self.assertNotIn("password123!", serialized)
        self.assertNotIn("bearer", serialized)
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("eyj", serialized)  # Common JWT prefix

    def test_safe_event_recording(self):
        """Custom events must appear in event_log buffer and be scrubbed."""
        self.controller.record_event('Safe message: {"password": "SecretPassword123!"} token=Bearer eyJhbGciOi.token.sig')
        state = self.controller.get_state()
        logs = state["event_log"]
        self.assertTrue(len(logs) > 0)
        last_log = logs[-1]["message"]
        # Must not contain plain secrets
        self.assertNotIn("SecretPassword123!", last_log)
        self.assertIn("REDACTED", last_log)


if __name__ == "__main__":
    unittest.main()
