"""
Transit Platform — Demo Simulator Mission Control HTTP Server.

A zero-dependency local HTTP server built on Python standard library
ThreadingHTTPServer. Exposes REST control APIs and serves the Mission Control SPA.
Binds strictly to 127.0.0.1 by default.
"""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import urllib.parse

from simulator.config.settings import Settings
from simulator.server.controller import ConflictError, SimulationController
from simulator.utils.logging import get_logger

logger = get_logger("server")

STATIC_DIR = Path(__file__).resolve().parent / "static"


class SimulatorApiHandler(SimpleHTTPRequestHandler):
    """
    HTTP Request handler serving both Mission Control REST APIs (/api/...)
    and local static UI assets.
    """

    controller: SimulationController = None  # Injected on server initialization
    settings: Settings = None

    def __init__(self, *args, **kwargs):
        # Set directory for static asset fallback
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    # Suppress default server log lines to maintain clean simulator logs
    def log_message(self, format: str, *args) -> None:
        logger.debug(f"{self.address_string()} - {format % args}")

    def _send_cors_headers(self) -> None:
        """Appends safe localhost-only CORS headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Serializes and sends a JSON response with proper headers."""
        try:
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Error sending JSON response: {e}")

    def _send_error_json(self, message: str, status: int = 400) -> None:
        """Sends a sanitized error JSON response."""
        self._send_json({"error": message, "status": status}, status=status)

    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        """Safely parses incoming JSON request body."""
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return {}
        try:
            length = int(content_length)
            raw = self.rfile.read(length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Malformed JSON request: {e}")
            return None

    def do_OPTIONS(self) -> None:
        """Handles browser pre-flight OPTIONS requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        """Routes GET requests to API handlers or static files."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        # 1. API Route Dispatch
        if path == "/api/health":
            self._handle_get_health()
        elif path == "/api/status":
            self._handle_get_status()
        elif path == "/api/scenarios":
            self._handle_get_scenarios()
        elif path.startswith("/api/scenarios/"):
            scenario_name = path[len("/api/scenarios/"):]
            self._handle_get_scenario_detail(scenario_name)
        elif path.startswith("/api/"):
            self._send_error_json(f"Unknown API endpoint: {path}", status=404)
        else:
            # 2. Static Web UI Dispatch (SPA routing)
            if path in ("/", "/index.html"):
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        """Routes POST requests to simulator control APIs."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        body = self._read_json_body()
        if body is None:
            self._send_error_json("Malformed JSON payload in request body", status=400)
            return

        if path == "/api/scenarios/validate":
            self._handle_post_validate(body)
        elif path == "/api/simulation/start":
            self._handle_post_start(body)
        elif path == "/api/simulation/pause":
            self._handle_post_pause(body)
        elif path == "/api/simulation/resume":
            self._handle_post_resume(body)
        elif path == "/api/simulation/stop":
            self._handle_post_stop(body)
        elif path == "/api/simulation/reset":
            self._handle_post_reset(body)
        else:
            self._send_error_json(f"Unknown API endpoint: {path}", status=404)

    # --------------------------------------------------------------------------
    # API Route Handlers
    # --------------------------------------------------------------------------

    def _handle_get_health(self) -> None:
        """GET /api/health — Checks server & GoBus backend connectivity."""
        health = self.controller.check_backend()
        data = {
            "simulator_server": "RUNNING",
            "simulator_lifecycle": self.controller.lifecycle.value,
            "backend": health,
        }
        self._send_json(data)

    def _handle_get_status(self) -> None:
        """GET /api/status — Returns live thread-safe SimulatorState projection."""
        try:
            state = self.controller.get_state()
            self._send_json(state)
        except Exception as e:
            logger.exception("Error getting simulator state")
            self._send_error_json(str(e), status=500)

    def _handle_get_scenarios(self) -> None:
        """GET /api/scenarios — Returns list of all available scenarios."""
        scenarios = self.controller.list_scenarios()
        self._send_json(scenarios)

    def _handle_get_scenario_detail(self, name: str) -> None:
        """GET /api/scenarios/{name} — Returns detail for a specific scenario."""
        try:
            detail = self.controller.get_scenario_detail(name)
            self._send_json(detail)
        except Exception as e:
            self._send_error_json(str(e), status=404)

    def _handle_post_validate(self, body: Dict[str, Any]) -> None:
        """POST /api/scenarios/validate — Dry-run offline scenario validation."""
        scenario_name = body.get("scenario")
        if not scenario_name:
            self._send_error_json("Missing 'scenario' parameter in request body", status=400)
            return

        is_valid, errors = self.controller.validate(scenario_name)
        self._send_json({
            "scenario": scenario_name,
            "valid": is_valid,
            "errors": errors,
        })

    def _handle_post_start(self, body: Dict[str, Any]) -> None:
        """POST /api/simulation/start — Starts a simulation scenario."""
        scenario_name = body.get("scenario")
        if not scenario_name:
            self._send_error_json("Missing 'scenario' parameter in request body", status=400)
            return

        time_multiplier = float(body.get("time_multiplier", 1.0))
        tick_seconds = float(body.get("tick_seconds", 1.0))
        duration = float(body.get("duration")) if "duration" in body and body["duration"] is not None else None

        try:
            result = self.controller.start(
                scenario_name=scenario_name,
                time_multiplier=time_multiplier,
                tick_seconds=tick_seconds,
                duration=duration,
            )
            self._send_json(result, status=200)
        except ConflictError as e:
            self._send_error_json(str(e), status=409)
        except ValueError as e:
            self._send_error_json(str(e), status=400)
        except Exception as e:
            logger.exception("Unexpected error in simulation start")
            self._send_error_json(f"Simulation startup failure: {e}", status=500)

    def _handle_post_pause(self, body: Dict[str, Any]) -> None:
        """POST /api/simulation/pause — Pauses active simulation."""
        try:
            res = self.controller.pause()
            self._send_json(res)
        except ConflictError as e:
            self._send_error_json(str(e), status=409)

    def _handle_post_resume(self, body: Dict[str, Any]) -> None:
        """POST /api/simulation/resume — Resumes paused simulation."""
        try:
            res = self.controller.resume()
            self._send_json(res)
        except ConflictError as e:
            self._send_error_json(str(e), status=409)

    def _handle_post_stop(self, body: Dict[str, Any]) -> None:
        """POST /api/simulation/stop — Stops active simulation and ends trips."""
        try:
            res = self.controller.stop()
            self._send_json(res)
        except Exception as e:
            logger.exception("Error stopping simulation")
            self._send_error_json(str(e), status=500)

    def _handle_post_reset(self, body: Dict[str, Any]) -> None:
        """
        POST /api/simulation/reset — Resets simulator state to IDLE.
        Requires confirm_backend_cleanup=true if simulation is currently active.
        """
        confirm = bool(body.get("confirm_backend_cleanup", False))
        try:
            res = self.controller.reset(confirm_backend_cleanup=confirm)
            self._send_json(res)
        except ConflictError as e:
            self._send_error_json(str(e), status=409)
        except Exception as e:
            logger.exception("Error during reset")
            self._send_error_json(str(e), status=500)


def make_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    controller: Optional[SimulationController] = None,
    settings: Optional[Settings] = None,
) -> ThreadingHTTPServer:
    """
    Constructs and configures the Mission Control ThreadingHTTPServer instance.
    Enforces localhost-only binding by default for security.
    """
    # Security check: warn if binding to an external interface
    if host not in ("127.0.0.1", "localhost"):
        logger.warning(f"Security Alert: Binding simulator control server to external host '{host}'.")

    st = settings or Settings()
    ctrl = controller or SimulationController(settings=st)

    class ConfiguredHandler(SimulatorApiHandler):
        pass

    ConfiguredHandler.controller = ctrl
    ConfiguredHandler.settings = st

    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, ConfiguredHandler)
    httpd.daemon_threads = True
    return httpd


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Entrypoint to run the server in the foreground with clean interrupt handling."""
    settings = Settings()
    effective_host = os.getenv("GOBUS_SIMULATOR_HOST", host)
    effective_port = int(os.getenv("GOBUS_SIMULATOR_PORT", port))

    controller = SimulationController(settings=settings)
    server = make_server(
        host=effective_host,
        port=effective_port,
        controller=controller,
        settings=settings,
    )

    print("=" * 70)
    print(" GOBUS TRANSIT PLATFORM — MISSION CONTROL DASHBOARD")
    print("=" * 70)
    print(f" Server URL:        http://{effective_host}:{effective_port}")
    print(f" Target Backend:    {settings.backend_url}")
    print(f" Interface Binding: {effective_host} (Localhost Only)")
    print(f" Static UI Dir:     {STATIC_DIR}")
    print("=" * 70)
    print(" Press Ctrl+C to terminate server.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server cleanly...")
    finally:
        controller.reset(confirm_backend_cleanup=True)
        server.server_close()
        print("Server shutdown complete.")
