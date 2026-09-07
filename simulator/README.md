# GoBus Demo Simulator — Standalone Foundation & API Adapter

The GoBus Demo Simulator is a standalone external client application that emulates the behavior of physical Operator Android devices. It communicates with the GoBus transit platform exclusively through verified public HTTP REST APIs.

> **CRITICAL ARCHITECTURAL BOUNDARY:**
> - The simulator **never** accesses PostgreSQL or PostGIS directly.
> - The simulator **never** imports GoBus backend modules.
> - The simulator **never** modifies Build 3 intelligence engines or application state.
> - The simulator generates genuine telemetry events which Build 3 naturally consumes and processes.

---

## 1. Project Structure

```
simulator/
├── .env.example                               # Environment configuration template
├── requirements.txt                           # Minimal dependencies: requests, python-dotenv
├── README.md                                  # Documentation
├── logs/                                      # Runtime application logs (auto-redacted)
├── simulator/                                 # Standalone Python package
│   ├── __init__.py
│   ├── main.py                                # CLI entry point (health, inspect-assignment, smoke-test)
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                        # Environment & multi-operator settings loader
│   ├── core/
│   │   ├── __init__.py
│   │   ├── session.py                         # OperatorSession model & simulation state machine
│   │   └── exceptions.py                      # Specific simulator domain & API exceptions
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py                          # Safe requests.Session HTTP client wrapper
│   │   ├── auth.py                            # Operator login (POST /api/auth/operator/login)
│   │   ├── assignment.py                      # Duty assignment (GET /api/operator/me/assignment)
│   │   ├── trip.py                            # Trip start/end (POST /api/trips/{trip_id}/start & /end)
│   │   ├── telemetry.py                       # Batch telemetry (POST /api/tracking/batch)
│   │   ├── heartbeat.py                       # Device heartbeat (POST /api/tracking/heartbeat)
│   │   └── crowding.py                        # Crowding report (POST /api/crowding/reports)
│   ├── scenarios/
│   │   └── __init__.py                        # Reserved for Phase 8 scenarios
│   └── utils/
│       ├── __init__.py
│       └── logging.py                         # Redacted logging filter & formatting
└── tests/
    ├── __init__.py
    ├── test_api_client.py                     # HTTP client tests with mocked responses
    ├── test_auth.py                           # Login & token extraction tests
    ├── test_assignment.py                     # Assignment contract parser tests
    ├── test_trip.py                           # Trip start/end tests
    ├── test_telemetry.py                      # Packet UUIDs, sequences, coordinate checks, batching tests
    ├── test_heartbeat.py                      # Heartbeat payload tests
    ├── test_crowding.py                       # Crowding report payload & rate limit handling tests
    ├── test_session.py                        # OperatorSession state machine & safety tests
    └── test_logging_safety.py                 # Secret & JWT redaction verification tests
```

---

## 2. Installation

Requires Python 3.12+.

```bash
cd simulator
python -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

---

## 3. Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Environment Variable | Default | Description |
|---|---|---|
| `GOBUS_BACKEND_URL` | `http://localhost:8000` | Target GoBus backend URL |
| `GOBUS_OPERATOR_EMPLOYEE_CODE` | `O-001` | Demo operator employee code |
| `GOBUS_OPERATOR_PASSWORD` | `Password123!` | Demo operator password |
| `GOBUS_REQUEST_TIMEOUT` | `10.0` | Timeout in seconds |
| `GOBUS_LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 4. CLI Commands

### A. Health Check
Tests communication and reachability of the configured backend without requiring credentials:
```bash
python -m simulator.main health
```

### B. Inspect Duty Assignment
Logs in as the configured operator and displays current duty assignment details (vehicle, trip, route, direction):
```bash
python -m simulator.main inspect-assignment
```

### C. Single-Packet Smoke Test
Runs an end-to-end operational loop: login -> assignment -> start trip -> 1 telemetry packet -> heartbeat -> end trip:
```bash
python -m simulator.main smoke-test
```

### D. Route-Driven Bus Movement Simulation (Phase 2)
Simulates realistic physical bus movement along the assigned route with dwell at intermediate stops, forward bearing heading, and live batch telemetry ingestion:
```bash
python -m simulator.main simulate --speed 8.33 --multiplier 2.0 --dwell 15.0
```

### E. Deterministic Multi-Bus Scenarios (Phase 3)
Run any of the 7 built-in deterministic multi-bus demo scenarios:
```bash
python -m simulator.main simulate --scenario full_demo --duration 60 --multiplier 1.0
```

Available built-in scenarios:
- `normal_single_bus`: Baseline single-bus route traversal.
- `multi_bus_demo`: 2 independent buses running concurrently with staggered starts.
- `delay_demo`: Simulates traffic congestion (speed drops to 2.5 m/s at T+20s).
- `offline_demo`: Simulates telemetry silencing and stale recovery.
- `crowding_demo`: Submits crowding reports (HIGH at T+15s, FULL at T+45s).
- `service_shortage_demo`: Demonstrates service shortage (withholding Bus 2).
- `full_demo`: Unified multi-bus, delay, crowding, and stale recovery timeline.

---

## 5. Phase 4: Mission Control Dashboard

Phase 4 provides a lightweight, zero-dependency browser-based Mission Control dashboard for live SIH demonstration.

### Launching Mission Control

#### Windows 1-Click Launcher
Double-click `run_control_panel.bat` in the `simulator/` directory.

#### Command Line
```bash
python -m simulator.main ui --host 127.0.0.1 --port 8080
```

Access the dashboard at: `http://127.0.0.1:8080`

### Dashboard Capabilities
- **Backend Connection Status:** Probes GoBus backend connectivity and measures real-time ping latency.
- **Scenario Orchestration:** Select any of the 7 built-in scenarios, run offline validation, and inspect timeline previews.
- **Live Fleet Cards:** Multi-bus cards displaying route progress bars, current speed, stop dwell status, and sensor states (GPS, Telemetry, Heartbeat, Crowding).
- **Timeline Stepper:** Dynamic progress indicator marking completed, active, and upcoming scenario events.
- **Controls:** `START`, `PAUSE`, `RESUME`, `STOP`, and `RESET`.
- **Reset Safety:** Destructive reset of an active simulation requires explicit confirmation, ensuring active backend trip tracking sessions are cleanly terminated (`POST /api/trips/{trip_id}/end`) and operators logged out.
- **Operational Audit Stream:** Auto-scrolling, sanitized event log feed with zero secret leakage.

### Local Control API (`http://127.0.0.1:8080/api/...`)
- `GET /api/health`: Backend reachability and simulator lifecycle status.
- `GET /api/status`: Real-time `SimulatorState` projection (fleet, timeline, metrics, sanitized logs).
- `GET /api/scenarios`: List all available scenarios.
- `GET /api/scenarios/{name}`: Detailed scenario metadata.
- `POST /api/scenarios/validate`: Dry-run offline validation.
- `POST /api/simulation/start`: Launch background simulation worker.
- `POST /api/simulation/pause`: Pause simulated time.
- `POST /api/simulation/resume`: Resume simulated time.
- `POST /api/simulation/stop`: Stop fleet and close backend tracking sessions.
- `POST /api/simulation/reset`: Reset simulator to `IDLE` state (`confirm_backend_cleanup: true` required if active).

---

## 6. Security & Secret Redaction

* Passwords and JWT tokens are stored strictly in memory and are never persisted to disk or serialized in state projections.
* Control server binds strictly to `127.0.0.1` by default (never exposed to public LAN).
* All logs and event streams run through a strict `RedactingFilter` scrubbing:
  * JWT tokens (`eyJ...`)
  * Bearer authorization headers
  * Password parameters in serialized JSON payloads

---

## 7. Running Unit Tests

Run the complete offline test suite (96 unit tests covering all adapters, route math, clocks, movement engines, fleet orchestration, controller lifecycle, and HTTP server APIs):
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

