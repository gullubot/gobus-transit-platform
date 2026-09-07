"""
Unit and API integration tests for Mission Control Server (Phase 4).
Starts an in-process ThreadingHTTPServer on an ephemeral port (127.0.0.1:0)
and validates all REST endpoints and static asset serving.
"""

import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from simulator.config.settings import Settings
from simulator.server.app import make_server
from simulator.server.controller import SimulationController


class TestMissionControlServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.settings = Settings(
            backend_url="http://localhost:8000",
            request_timeout=2.0,
        )
        cls.controller = SimulationController(settings=cls.settings)
        # Bind to port 0 to let OS allocate an available port
        cls.server = make_server(
            host="127.0.0.1",
            port=0,
            controller=cls.controller,
            settings=cls.settings,
        )
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)  # Brief pause to ensure socket listening

    @classmethod
    def tearDownClass(cls):
        cls.controller.reset(confirm_backend_cleanup=True)
        cls.server.shutdown()
        cls.server.server_close()

    def _request(self, method: str, path: str, body: dict = None) -> tuple:
        """Helper to send HTTP requests to test server and return (status, parsed_json_or_text)."""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                status = resp.status
                content = resp.read().decode("utf-8")
                try:
                    return status, json.loads(content)
                except Exception:
                    return status, content
        except urllib.error.HTTPError as e:
            status = e.code
            content = e.read().decode("utf-8")
            try:
                return status, json.loads(content)
            except Exception:
                return status, content

    def test_get_health(self):
        """GET /api/health must report server running and probe backend."""
        status, data = self._request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["simulator_server"], "RUNNING")
        self.assertIn("simulator_lifecycle", data)
        self.assertIn("backend", data)

    def test_get_status(self):
        """GET /api/status must return valid SimulatorState projection."""
        status, data = self._request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["lifecycle"], "IDLE")
        self.assertIn("metrics", data)
        self.assertIn("fleet", data)
        self.assertIn("timeline", data)

    def test_get_scenarios_list_and_detail(self):
        """GET /api/scenarios and /api/scenarios/{name}."""
        status, data = self._request("GET", "/api/scenarios")
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) >= 7)

        status, detail = self._request("GET", "/api/scenarios/full_demo")
        self.assertEqual(status, 200)
        self.assertEqual(detail["name"], "full_demo")

        status_bad, _ = self._request("GET", "/api/scenarios/non_existent")
        self.assertEqual(status_bad, 404)

    def test_post_validate_scenario(self):
        """POST /api/scenarios/validate dry-run validation."""
        status, data = self._request("POST", "/api/scenarios/validate", {"scenario": "full_demo"})
        self.assertEqual(status, 200)
        self.assertTrue(data["valid"])

        status_bad, data_bad = self._request("POST", "/api/scenarios/validate", {"scenario": "bad_scenario"})
        self.assertEqual(status_bad, 200)
        self.assertFalse(data_bad["valid"])

    def test_post_pause_resume_conflict_when_idle(self):
        """Pausing or resuming while IDLE must return 409 Conflict."""
        status, _ = self._request("POST", "/api/simulation/pause")
        self.assertEqual(status, 409)

        status, _ = self._request("POST", "/api/simulation/resume")
        self.assertEqual(status, 409)

    def test_post_reset_when_idle(self):
        """Resetting while IDLE must succeed with 200."""
        status, data = self._request("POST", "/api/simulation/reset", {"confirm_backend_cleanup": False})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "IDLE")

    def test_malformed_json_body(self):
        """Malformed JSON must return 400 Bad Request."""
        url = f"{self.base_url}/api/simulation/start"
        raw_bad_data = b"This is not valid JSON {{}"
        req = urllib.request.Request(url, data=raw_bad_data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=3.0)
            self.fail("Expected HTTPError 400")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_unknown_api_endpoint(self):
        """Unknown API routes must return 404."""
        status, _ = self._request("GET", "/api/non_existent_route")
        self.assertEqual(status, 404)

    def test_static_asset_serving(self):
        """Static UI files must be served cleanly."""
        status, index_html = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("GoBus Transit Platform", index_html)
        self.assertIn("MISSION CONTROL", index_html)

        status, css = self._request("GET", "/styles.css")
        self.assertEqual(status, 200)
        self.assertIn("--bg-base", css)

        status, js = self._request("GET", "/app.js")
        self.assertEqual(status, 200)
        self.assertIn("pollStatus", js)


if __name__ == "__main__":
    unittest.main()
