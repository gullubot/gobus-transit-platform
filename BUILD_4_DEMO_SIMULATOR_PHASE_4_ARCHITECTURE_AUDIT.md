# BUILD 4 — PHASE 4: DEMO CONTROL PANEL & PRESENTATION LAYER
# ARCHITECTURE AUDIT & DESIGN SPECIFICATION

**Document Version:** 1.0.0  
**Date:** 2026-09-03  
**Status:** ARCHITECTURE AUDIT / RESEARCH ONLY (Implementation Frozen)  
**Author:** AI Pair Programmer & System Architect  

---

## Executive Summary

Phase 1 (Foundation & API Client), Phase 2 (Route Kinematics & Movement Engine), Phase 3 (Multi-Bus Fleet & Scenario Engine), and Phase 3.6 (Runtime Recovery & Live GoBus Integration) have been completed and verified against the live FastAPI backend and PostGIS database.

This document establishes the authoritative architectural design for **Phase 4: Demo Control Panel & Presentation Layer**. The objective is to provide an intuitive, high-impact mission control interface for live Smart India Hackathon (SIH) demonstrations, allowing evaluators and demo operators to orchestrate deterministic transit scenarios on a separate laptop without touching a terminal or modifying product source code.

In strict adherence to the project charter:
- **Build 3 and GoBus backend remain completely frozen.**
- Direct database access is **strictly prohibited**.
- The control panel operates exclusively as an external presentation layer orchestrating the existing simulator core.

---

## 1. Current Phase 1–3 Architecture Summary

The existing simulator codebase is organized into cleanly decoupled packages under `simulator/`:

```
simulator/
├── requirements.txt           # requests>=2.28.0, python-dotenv>=1.0.0
├── simulator/
│   ├── api/                   # Phase 1: GoBus HTTP client, Auth, Assignment, Telemetry, Crowding, Heartbeat
│   ├── config/                # Settings, environment parser, operator definitions
│   ├── core/                  # Phase 2 & 3: MovementEngine, Route, BusSimulator, FleetManager, Scheduler
│   │   ├── bus_simulator.py   # Single bus state machine (CREATED, RUNNING, PAUSED, STOPPED, ERROR)
│   │   ├── clock.py           # SimulationClock with deterministic time scaling
│   │   ├── fleet.py           # FleetManager orchestrating N isolated buses (1 bus = 1 distinct operator)
│   │   ├── movement.py        # Haversine distance, segment interpolation, stop dwelling
│   │   ├── route.py           # Topologically verified route model (stops, segments, polyline)
│   │   ├── scenario.py        # ScenarioDefinition, ScenarioEvent, ScenarioEventType
│   │   ├── scenario_loader.py # 7 built-in scenarios, YAML/JSON loader, dry-run validator
│   │   ├── scheduler.py       # Deterministic timeline event dispatcher and per-tick fleet step
│   │   ├── session.py         # OperatorSession state with in-memory JWT & secret redaction
│   │   └── telemetry_generator.py # Monotonic packet sequence & kinematic payload generator
│   └── utils/
│       ├── geo.py             # Spherical trigonometry (bearing, normalization, interpolation)
│       └── logging.py         # SecretsFilter redacting JWTs, Bearer tokens, passwords
└── tests/                     # 80 passing unit tests (0.191s execution time)
```

### Key Architectural Assets Reused in Phase 4
1. **`FleetManager` (`fleet.py`):** Provides `initialize_fleet()`, `step_fleet()`, `transmit_fleet_telemetry()`, `send_fleet_heartbeats()`, `stop_fleet()`, and `get_fleet_summary()`.
2. **`ScenarioScheduler` (`scheduler.py`):** Drives simulation progression via `tick(delta_real_seconds)`. Tracks elapsed simulated time, pending events, executed events, and completion state.
3. **`validate_scenario()` (`scenario_loader.py`):** Dry-run scenario validation ensuring operator uniqueness, target bus existence, and parameter validity without network calls.
4. **`SecretsFilter` (`logging.py`):** Universal regex-based filter masking passwords, Bearer tokens, and JWT strings in memory before log dispatch.

---

## 2. Candidate UI Approaches & Evaluation

To ensure portability, reliability, and visual wow-factor on a standalone demo laptop, four architectural candidates were evaluated:

| Criterion | Option A: Embedded Local HTTP + Browser UI | Option B: Desktop GUI (Tkinter / PyQt) | Option C: Terminal / TUI (Textual / curses) | Option D: Hybrid Electron / Tauri |
|---|:---:|:---:|:---:|:---:|
| **Zero New Pip Dependencies** | **YES** (Python `http.server`) | YES (Tkinter only) / NO (PyQt) | NO (`textual`, `rich`) | NO (Node.js, npm, Rust) |
| **Visual Aesthetics (WOW Factor)** | **EXCELLENT** (Modern Dark Mode / Glassmorphism) | POOR (Tkinter 1990s look) / GOOD (PyQt) | MODERATE (CLI aesthetic) | EXCELLENT |
| **Windows Portability** | **EXCELLENT** (Single folder, runs anywhere) | MODERATE (Tkinter DPI issues / PyQt DLLs) | MODERATE (Windows Terminal dependencies) | POOR (Heavy runtime binary) |
| **Resource Footprint** | **NEGLIGIBLE** (< 25 MB RAM) | LOW (Tkinter) / HIGH (PyQt) | VERY LOW (< 15 MB RAM) | HIGH (> 250 MB RAM) |
| **Screen Dual-Projection** | **EXCELLENT** (Projector tab alongside Admin Web) | MODERATE (OS window placement) | POOR (Console font scaling) | GOOD |
| **Decoupling from Core** | **PERFECT** (Clean REST/SSE State API) | TIGHT (UI loop coupled to Python thread) | TIGHT (Event loop coupled to async engine) | PERFECT |

### Detailed Evaluation of Candidates:

1. **Option B (Desktop GUI - Tkinter/PyQt):**
   - *Tkinter:* Included with Python on Windows, but inherently lacks modern aesthetic primitives. Building animated route progress bars, sleek dark-mode glassmorphic cards, and real-time status pills in Tkinter produces a clunky 1990s appearance that diminishes presentation value for SIH evaluators.
   - *PyQt / PySide:* Requires installing large external C++ binary wheels (~150MB pip download), introduces licensing considerations, and frequently suffers from DPI scaling and thread lockup issues across different Windows laptop resolutions.
2. **Option C (Terminal UI - Textual):**
   - Highly portable and clean, but non-technical evaluators cannot interact via mouse easily. It cannot be displayed in a browser tab side-by-side with the GoBus Admin Web, creating awkward window switching during live demonstrations.
3. **Option D (Electron / Tauri):**
   - Demands Node.js, npm, native compilation toolchains, and bundle sizes exceeding 200MB. Violates the core mandate of minimal dependencies and effortless portability.
4. **Option A (Embedded Local HTTP Server + Browser UI):**
   - **Zero additional pip dependencies** if implemented using Python's built-in `http.server` (or minimal micro-framework).
   - Zero npm, zero Node.js, zero Webpack/Vite build step (plain HTML5, CSS3, ES6 JavaScript).
   - Instant launch via browser (Chrome, Edge, Firefox) on `http://127.0.0.1:8080`.
   - Allows presenting the **Demo Control Panel** in one browser window and the **GoBus Admin Web** in an adjacent window, enabling evaluators to see simulator actions translate immediately into live operational changes.

---

## 3. Recommended Architecture: Standalone Embedded Web Console

We recommend **Option A: Python Standard Library `ThreadingHTTPServer` with an Embedded Single-Page Application (SPA)**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DEMO LAPTOP / BROWSER                           │
│  http://127.0.0.1:8080                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     GoBus Mission Control UI                     │  │
│  │  [Status Pill]  [Scenario Selector]  [Control Bar: Start/Pause]  │  │
│  │  [Fleet Cards: Bus-1, Bus-2]  [Scenario Timeline]  [Event Log]   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ HTTP REST + Polling / SSE
                                    │ (localhost only)
┌───────────────────────────────────▼────────────────────────────────────┐
│                    STANDALONE DEMO SIMULATOR HOST                      │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Control Server (simulator/server/app.py)                         │  │
│  │  - Python ThreadingHTTPServer on 127.0.0.1:8080                  │  │
│  │  - Serves static assets (HTML/CSS/JS)                            │  │
│  │  - Exposes safe /api/control endpoints                           │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │ Thread-safe state lock           │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │  Simulation Execution Controller (simulator/server/controller.py) │  │
│  │  - Background worker thread driving tick loop                    │  │
│  │  - Thread-safe state projection (SimulatorState)                 │  │
│  │  - Clean Start / Pause / Resume / Stop / Reset lifecycle         │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │ Calls existing APIs              │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │  EXISTING PHASE 1–3 SIMULATOR ENGINE (UNTOUCHED)                 │  │
│  │  FleetManager ──► BusSimulator (N) ──► GoBusHttpClient           │  │
│  │  ScenarioScheduler ──► MovementEngine ──► TelemetryGenerator     │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
└─────────────────────────────────────┼──────────────────────────────────┘
                                      │ HTTP /api/tracking, /api/auth
                                      ▼
                        ┌───────────────────────────┐
                        │    REAL GOBUS BACKEND     │
                        │    (Localhost or LAN)     │
                        │    FastAPI + PostGIS      │
                        └───────────────────────────┘
```

### Why this is the cleanest approach:
1. **Zero Impact on Simulator Core:** The existing `FleetManager`, `BusSimulator`, `ScenarioScheduler`, and `MovementEngine` classes remain 100% unaltered. The controller simply holds an instance and calls `tick()` in a background thread.
2. **Zero Dependencies Added to `requirements.txt`:** Python's built-in `http.server`, `urllib`, and `threading` libraries handle HTTP routing and static file serving. No FastAPI or Flask is required inside the simulator package.
3. **Guaranteed Localhost Security:** Server listens exclusively on `127.0.0.1`.
4. **Complete Separation:** The UI is purely a projection of the state. If the browser is closed or refreshed, the simulation running in the Python daemon continues smoothly.

---

## 4. Dependency Analysis

### Existing Simulator Dependencies (`simulator/requirements.txt`):
```
requests>=2.28.0
python-dotenv>=1.0.0
```

### Proposed Phase 4 Dependencies:
**NO NEW DEPENDENCIES REQUIRED.**

The presentation layer will be implemented using:
- **Server:** Standard Library `http.server.ThreadingHTTPServer` + `http.server.SimpleHTTPRequestHandler`.
- **Concurrency:** Standard Library `threading.Thread`, `threading.Lock`, `threading.Event`.
- **Data Encoding:** Standard Library `json`.
- **Frontend:** Standard Web Technologies (HTML5, Vanilla CSS3, ES6 Vanilla JavaScript).
- **Icons:** Inline SVGs (zero external CDN or font dependencies, works completely offline with no internet access).

---

## 5. Control API Proposal

All control endpoints are local-only (`http://127.0.0.1:8080/api/...`) and return `application/json`.

### Endpoints Specification

| Method | Route | Description | Request Body | Response Payload |
|---|---|---|---|---|
| `GET` | `/api/health` | Probes GoBus backend connectivity & returns ping latency | None | `{"backend_status": "CONNECTED", "latency_ms": 14.2, "backend_url": "http://127.0.0.1:8000"}` |
| `GET` | `/api/status` | Read-only projection of the current simulator state | None | `SimulatorState` (see Section 6) |
| `GET` | `/api/scenarios` | Lists all available scenarios with summary metadata | None | `[{"name": "multi_bus_demo", "description": "...", "bus_count": 2, "duration_s": 15.0}]` |
| `GET` | `/api/scenarios/{name}` | Retrieves full event timeline and bus definitions | None | `{"name": "...", "buses": [...], "events": [...]}` |
| `POST` | `/api/scenarios/validate` | Dry-run validation of a scenario without network | `{"scenario": "full_demo"}` | `{"valid": true, "errors": []}` |
| `POST` | `/api/simulation/start` | Initializes fleet and launches simulation thread | `{"scenario": "delay_demo", "time_multiplier": 1.0, "tick_seconds": 1.0}` | `{"status": "STARTED", "scenario": "delay_demo"}` |
| `POST` | `/api/simulation/pause` | Pauses simulation clock and fleet movement | None | `{"status": "PAUSED"}` |
| `POST` | `/api/simulation/resume` | Resumes simulation clock and fleet movement | None | `{"status": "RESUMED"}` |
| `POST` | `/api/simulation/stop` | Stops fleet and closes active backend sessions | None | `{"status": "STOPPED"}` |
| `POST` | `/api/simulation/reset` | Emergency cleanup, closes trips, resets scheduler | None | `{"status": "IDLE"}` |

---

## 6. Live State Model Proposal (`SimulatorState`)

The presentation layer consumes a thread-safe, immutable snapshot projected by the `SimulatorEngineController`:

```json
{
  "timestamp": "2026-09-03T02:45:00.123Z",
  "lifecycle": "RUNNING",
  "active_scenario": "full_demo",
  "sim_elapsed_seconds": 25.0,
  "duration_seconds": 50.0,
  "time_multiplier": 1.0,
  "tick_count": 25,
  "backend": {
    "status": "CONNECTED",
    "url": "http://127.0.0.1:8000",
    "latency_ms": 12.5,
    "last_probe": "2026-09-03T02:44:59Z"
  },
  "metrics": {
    "packets_generated": 35,
    "packets_accepted": 35,
    "packets_rejected": 0,
    "heartbeats_sent": 2,
    "crowding_reports_sent": 1,
    "last_error": null
  },
  "fleet": [
    {
      "bus_id": "bus-1",
      "operator_code": "O-001",
      "operator_name": "Demo Driver 1",
      "service_code": "SD5",
      "route_name": "Sonarpur Station Terminus to Kharibaria Terminus",
      "vehicle_number": "WB04-DEMO-001",
      "lifecycle": "RUNNING",
      "speed_mps": 2.5,
      "speed_kmh": 9.0,
      "heading": 85.4,
      "coordinates": {"lat": 22.4412, "lon": 88.4231},
      "progress_percent": 18.5,
      "current_stop": "Sonarpur",
      "next_stop": "Sahebpara",
      "is_dwelling": false,
      "dwell_remaining_s": 0.0,
      "telemetry_enabled": true,
      "heartbeat_enabled": true,
      "crowding_state": "NONE",
      "packets_sent": 25,
      "packets_accepted": 25,
      "error": null
    },
    {
      "bus_id": "bus-2",
      "operator_code": "DRV001",
      "operator_name": "Demo Driver 2",
      "service_code": "AC4B",
      "route_name": "City Center to Tech Park",
      "vehicle_number": "PNB005234",
      "lifecycle": "RUNNING",
      "speed_mps": 7.5,
      "speed_kmh": 27.0,
      "heading": 120.0,
      "coordinates": {"lat": 22.5801, "lon": 88.4102},
      "progress_percent": 34.0,
      "current_stop": "City Center",
      "next_stop": "MG Road",
      "is_dwelling": false,
      "dwell_remaining_s": 0.0,
      "telemetry_enabled": true,
      "heartbeat_enabled": true,
      "crowding_state": "HIGH",
      "packets_sent": 10,
      "packets_accepted": 10,
      "error": null
    }
  ],
  "timeline": [
    {"time_s": 0.0, "event": "START_BUS", "target": "bus-1", "status": "COMPLETED"},
    {"time_s": 10.0, "event": "START_BUS", "target": "bus-2", "status": "COMPLETED"},
    {"time_s": 25.0, "event": "SET_SPEED (2.5 m/s)", "target": "bus-1", "status": "COMPLETED"},
    {"time_s": 35.0, "event": "SET_CROWDING (HIGH)", "target": "bus-2", "status": "UPCOMING"},
    {"time_s": 45.0, "event": "SET_TELEMETRY (OFFLINE)", "target": "bus-1", "status": "UPCOMING"}
  ],
  "event_log": [
    {"timestamp": "02:44:35", "message": "[bus-1] Authenticated O-001 (Kolkata Transit Authority)", "level": "INFO"},
    {"timestamp": "02:44:36", "message": "[bus-1] Session started: e6f3fef5...", "level": "INFO"},
    {"timestamp": "02:44:46", "message": "[bus-2] Authenticated DRV001 (Transit Demo Authority)", "level": "INFO"},
    {"timestamp": "02:45:00", "message": "[bus-1] Traffic congestion: Speed reduced to 2.5 m/s", "level": "WARN"}
  ]
}
```

---

## 7. UI Screen & Information Architecture

The UI is structured as a **single-screen Mission Control Dashboard** optimized for 1080p presentation displays.

### Visual Layout Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GOBUS MISSION CONTROL  [● BACKEND CONNECTED: 12ms] [● SIMULATOR: RUNNING] [T+00:25s / 00:50s]   │
├────────────────────────────────────────────────────────┬─────────────────────────────────────────┤
│ 1. SCENARIO ORCHESTRATION                              │ 2. CONTROL ACTIONS                      │
│ Scenario: [ full_demo                           ▼ ]    │ [ ▶ START ]  [ ⏸ PAUSE ]  [ ⏹ STOP ]     │
│ Multi-bus, traffic delay, crowding, and offline        │ [ ↺ RESET ]  [ ⚡ RESTART ]              │
│ Validation: [✓ Valid — 2 Distinct Operators Assigned]  │ Speed Multiplier: [ 1.0x ▼ ]            │
├────────────────────────────────────────────────────────┴─────────────────────────────────────────┤
│ 3. LIVE FLEET STATUS (2 Active Buses)                                                            │
│ ┌──────────────────────────────────────────────┐  ┌────────────────────────────────────────────┐ │
│ │ BUS 1: Sonarpur Terminus → Kharibaria (SD5)  │  │ BUS 2: City Center → Tech Park (AC4B)      │ │
│ │ Driver: O-001 | Vehicle: WB04-DEMO-001       │  │ Driver: DRV001 | Vehicle: PNB005234        │ │
│ │ Status: [ RUNNING ] | Speed: 2.5 m/s (9 km/h)│  │ Status: [ RUNNING ] | Speed: 7.5 m/s       │ │
│ │ Current: Sonarpur  ──► Next: Sahebpara       │  │ Current: City Center ──► Next: MG Road     │ │
│ │ Route Progress: [████░░░░░░░░░░░░░░] 18.5%   │  │ Route Progress: [███████░░░░░░░░░░░] 34.0% │ │
│ │ Sensors: [GPS: OK] [Telemetry: ON] [HB: ON]  │  │ Sensors: [GPS: OK] [Telemetry: ON] [HB: ON]│ │
│ │ Crowding: NORMAL | Packets: 25 (100% ACK)    │  │ Crowding: [ HIGH ] | Packets: 10 (100% ACK)│ │
│ └──────────────────────────────────────────────┘  └────────────────────────────────────────────┘ │
├────────────────────────────────────────┬─────────────────────────────────────────────────────────┤
│ 4. SCENARIO TIMELINE                   │ 5. SANITIZED AUDIT & EVENT STREAM                       │
│ [✓] 00:00 START_BUS (bus-1)            │ 02:44:35 [bus-1] Authenticated O-001 (KTA)              │
│ [✓] 00:10 START_BUS (bus-2)            │ 02:44:36 [bus-1] Session started: e6f3fef5...           │
│ [✓] 00:25 SET_SPEED (bus-1, 2.5 m/s)   │ 02:44:46 [bus-2] Authenticated DRV001 (TDA)             │
│ [►] 00:35 SET_CROWDING (bus-2, HIGH)   │ 02:45:00 [bus-1] Traffic congestion: speed -> 2.5 m/s   │
│ [ ] 00:45 SET_TELEMETRY (bus-1, OFF)   │ 02:45:01 [telemetry] Batch ACK: accepted=2              │
├────────────────────────────────────────┴─────────────────────────────────────────────────────────┤
│ 6. TELEMETRY COUNTERS: Packets Sent: 35 | Accepted: 35 | Rejected: 0 | Heartbeats: 2 | Crowding: 1  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Details
1. **Header Bar:** Real-time ping indicator, backend URL pill, global state pill, high-contrast digital simulation timer.
2. **Scenario Orchestration Card:** Select scenario from dropdown, see summary parameters, click "Validate Scenario" to check for operator credential collisions before running.
3. **Control Actions:** Prominent tactile buttons with clear state disables (e.g. Pause is disabled when Idle; Start is disabled when Running).
4. **Fleet Status Grid:** Responsive multi-bus cards showing real-time route progress, instantaneous speed, stop dwell status, and device sensors.
5. **Timeline Stepper:** Dynamic progress indicator marking completed events with green checkmarks, the active event with a pulsating accent, and upcoming events in muted slate.
6. **Sanitized Event Feed:** Auto-scrolling, high-contrast log container displaying human-readable simulator actions.

---

## 8. Security Model

1. **Localhost Binding:** The HTTP server binds exclusively to `127.0.0.1` (or `localhost`). It will not bind to `0.0.0.0`, preventing access from unauthorized machines on the local network.
2. **Zero Secrets in State Projection:**
   - Password fields are completely omitted from the state model.
   - JWT tokens are strictly maintained in memory within `OperatorSession` objects and never serialized to JSON.
   - Operator credentials display only public identifiers (`employee_code`, `name`, `organization_name`).
3. **CORS Hardening:** API responses include `Access-Control-Allow-Origin: http://127.0.0.1:8080`, rejecting cross-origin requests from arbitrary external websites.
4. **Universal Logging Redaction:** All simulator events stream through the existing `SecretsFilter` before reaching the UI event buffer.

---

## 9. Portability & Standalone Deployment Model

A primary requirement is that the simulator directory can be transferred to a standalone demo laptop without installing the full GoBus transit platform.

### Target Laptop Requirements:
- **Operating System:** Windows 10 / 11, macOS, or Linux.
- **Python:** Python 3.10, 3.11, or 3.12 installed.
- **Network:** IP connectivity to the GoBus backend (can be localhost or over a local Wi-Fi router / Ethernet cable).
- **Installed Packages:** Only `requests` and `python-dotenv` (`pip install -r requirements.txt`).

### What is NOT Required on the Demo Laptop:
- **NO PostgreSQL or PostGIS.**
- **NO GoBus backend source code.**
- **NO Docker or Docker Compose.**
- **NO Node.js, npm, or frontend build tools.**
- **NO Android Studio or Android SDKs.**

### Standalone Launch Script:
Provide a zero-friction launch batch file for Windows (`run_control_panel.bat`):
```bat
@echo off
title GoBus Simulator Mission Control
echo Starting GoBus Simulator Control Panel...
python -m simulator.server
pause
```

When launched, the server automatically boots on port 8080 and opens the system default browser to `http://127.0.0.1:8080`.

---

## 10. Demo Reset Lifecycle Proposal

When presenting multiple back-to-back demonstrations to evaluators, the demo operator must be able to reset the simulator cleanly without leaving zombie sessions or corrupting backend state.

### Exact Reset Sequence (`POST /api/simulation/reset`):

```
1. Signal Simulation Thread
   └── Set `_stop_event` flag to halt tick loop.
   └── Join worker thread with 2.0s timeout.

2. Graceful Fleet Shutdown (via existing `FleetManager.stop_fleet()`)
   └── For each active bus with an active session:
       └── Call `POST /api/trips/{trip_id}/end` to mark backend tracking session completed.
       └── Call `operator_logout(session)` to clear in-memory auth tokens.
       └── Close HTTP client connection pool.

3. Failsafe Emergency Cleanup (via existing `FleetManager.emergency_cleanup()`)
   └── Catches any hanging sockets or unclosed sessions.

4. Clear Ephemeral Simulator Memory
   └── Deregister all buses from `FleetManager`.
   └── Reset `ScenarioScheduler` clock to 0.0s.
   └── Reset event queues (move executed events back to pending).
   └── Clear packet counters and live telemetry buffers.

5. Transition Global State
   └── Set lifecycle to `IDLE`.
   └── Emit audit log: "[RESET] Simulation reset complete. Ready for new scenario."
```

---

## 11. Testing Strategy

Phase 4 architecture will be validated across three isolated layers:

1. **State Projection & Serialization Unit Tests (`test_control_state.py`):**
   - Test that `SimulatorEngineController.get_state()` produces valid, secret-free JSON.
   - Test that JWTs and passwords never appear anywhere in serialized state dictionaries.
   - Test state progression through IDLE -> RUNNING -> PAUSED -> STOPPED -> IDLE.
2. **Control API Mock Integration Tests (`test_control_server.py`):**
   - Run tests against the local HTTP server using Python's `unittest` and `urllib.request`.
   - Test `/api/health`, `/api/scenarios`, `/api/simulation/start`, `/api/simulation/pause`, `/api/simulation/reset`.
   - Verify proper HTTP status codes (200, 400, 404, 500).
3. **UI Offline Static Validation:**
   - Verify that all static HTML/CSS/JS files load cleanly with zero external network requests (100% offline capability).
   - Test UI rendering using mock JSON fixtures in the absence of a running simulator.

---

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Thread Concurrency Lockup:** Background simulation thread blocking HTTP request handling. | High | Use `threading.Lock` strictly around state read/write; HTTP server runs on standard `ThreadingHTTPServer` pool. |
| **Backend Unavailability:** GoBus backend goes offline during demo. | High | Control Panel UI continuously displays backend ping status and disables "Start" button with clear guidance if backend is unreachable. |
| **Unclosed Backend Trips:** Abruptly stopping a simulation leaves trips in `ACTIVE` state on backend. | Medium | Reset lifecycle explicitly calls `end_trip_tracking` for all active buses and registers an `atexit` cleanup handler. |
| **Browser Dependency / CDN Outage:** Demo venue has no internet connectivity. | High | All assets (CSS, JS, SVG icons) are 100% locally embedded. Zero CDN dependencies (`fonts.googleapis.com`, `cdnjs`, etc.). |
| **Operator Credential Collision:** User selects a custom scenario with duplicate operators. | Medium | Scenario validation endpoint (`/api/scenarios/validate`) runs `validate_scenario()` before start, rejecting collisions. |

---

## 13. Exact Implementation Phases for Phase 4

When approved, Phase 4 implementation will be executed in three disciplined sub-phases:

### Sub-phase 4.1: Simulation Controller & State Projection
- Implement `simulator/server/controller.py`:
  - Wrap `FleetManager` and `ScenarioScheduler` in a thread-safe `SimulationController`.
  - Implement `start()`, `pause()`, `resume()`, `stop()`, `reset()`.
  - Implement thread-safe snapshot projection `get_state()`.
- Add unit tests in `tests/test_controller.py`.

### Sub-phase 4.2: Localhost HTTP API Server
- Implement `simulator/server/app.py`:
  - Lightweight standard-library `ThreadingHTTPServer`.
  - Handle REST routes (`/api/status`, `/api/scenarios`, `/api/simulation/*`).
  - Serve static directory `simulator/server/static/`.
- Add unit tests in `tests/test_server.py`.

### Sub-phase 4.3: Mission Control Presentation UI
- Implement `simulator/server/static/`:
  - `index.html`: Semantic, responsive dashboard structure.
  - `styles.css`: Glassmorphic dark theme, responsive layout, status badges, timeline stepper.
  - `app.js`: State polling loop (1s interval), DOM update routines, control button event handlers.
- Implement standalone runner `run_control_panel.bat` and CLI command `python -m simulator.main ui`.

---

## 14. Files Expected to Change / Be Created in Phase 4

### New Files to Create:
1. `simulator/simulator/server/__init__.py`
2. `simulator/simulator/server/controller.py` (Thread-safe engine controller)
3. `simulator/simulator/server/app.py` (Localhost HTTP server & API dispatcher)
4. `simulator/simulator/server/static/index.html` (Mission Control SPA)
5. `simulator/simulator/server/static/styles.css` (Glassmorphic dark design system)
6. `simulator/simulator/server/static/app.js` (UI state loop & controls)
7. `simulator/tests/test_controller.py` (Controller unit tests)
8. `simulator/tests/test_server.py` (Server & API unit tests)
9. `simulator/run_control_panel.bat` (Windows 1-click launcher)

### Existing Files to Modify (Minimal additions only):
1. `simulator/simulator/main.py`: Add `ui` sub-command (`python -m simulator.main ui --port 8080`).
2. `simulator/README.md`: Document Mission Control usage and launcher.

---

## 15. Confirmation of Product Code Integrity

* **`backend/`:** 100% untouched. No routes, schemas, models, or configurations modified.
* **`apps/` (Admin Web, Android):** 100% untouched.
* **`migrations/`:** 100% untouched.
* **`Build 3`:** Completely frozen.
* **Direct Database Access:** ZERO. The control panel and simulator interact with GoBus strictly via verified HTTP endpoints.

---

## Conclusion & Recommendation

The proposed **Embedded Web Console Architecture** satisfies all requirements:
1. It is **100% portable** with **zero new pip dependencies** and **zero npm/build dependencies**.
2. It delivers a **state-of-the-art visual presentation layer** that can be displayed side-by-side with the GoBus Admin Web.
3. It completely respects the boundary: it orchestrates the existing simulator core without modifying any GoBus product code.

**Next Steps:** Await user review and formal approval of this architecture audit before writing any Phase 4 implementation code.
