# BUILD 4 — DEMO SIMULATOR PHASE 1 IMPLEMENTATION REPORT

## A. Existing Simulator State
Prior to Phase 1, the simulator existed as an early prototype (`src/client.py`, `src/physics.py`, `src/config.py`, and `main.py`). The audit revealed several critical contract discrepancies:
1. **Crowding Payload Defect:** The prototype transmitted `{"level": level}` which is completely rejected by the GoBus FastAPI backend (`HTTP 422 Unprocessable Entity`). The verified backend requires `crowding_state` (enum: `LOW`, `MODERATE`, `HIGH`, `FULL`, `UNKNOWN`) and `confidence` (float `0.0` to `1.0`).
2. **GPS Status Values:** The prototype hardcoded `"gps_status": "GRANTED"` instead of the standard operational statuses used by the backend and Android client (`"AVAILABLE"`, `"ACQUIRING"`, `"OK"`).
3. **Missing Architectural Modularity:** The prototype lacked clean error normalization, secret redaction, structured logging, a monotonic sequence manager, and duty assignment validation.

In Phase 1, the standalone foundation was completely rebuilt as a clean, modular Python package (`simulator/`) strictly decoupled from backend internals.

---

## B. Verified Backend Contract Used
The API adapter implements the exact contracts determined in Phase 0:
* `POST /api/auth/operator/login`: JSON payload with `employee_code` and `password`. Returns JWT `access_token` and operator metadata.
* `GET /api/operator/me/assignment`: Authenticated with Bearer token. Returns `trip_id`, `service_id`, `route_id`, `vehicle_id`, and `assigned_device_id`.
* `POST /api/trips/{trip_id}/start`: Initiates tracking session. Returns `tracking_session_id`, `device_id`, and `status`.
* `POST /api/tracking/batch`: Telemetry batch with optional `session_id` and list of `TrackingPacketIn` packets.
* `POST /api/tracking/heartbeat`: Periodic device status (`battery_level`, `network_type`, `gps_status`, `app_version`).
* `POST /api/crowding/reports`: Verified crowding submission with `crowding_state` and `confidence`.
* `POST /api/trips/{trip_id}/end`: Ends active tracking session.

---

## C. Configuration
Implemented in `simulator/config/settings.py` and template `.env.example`:
* Supports environment variables and `.env` files:
  * `GOBUS_BACKEND_URL` (default: `http://localhost:8000`)
  * `GOBUS_OPERATOR_EMPLOYEE_CODE` (e.g. `O-001`)
  * `GOBUS_OPERATOR_PASSWORD`
  * `GOBUS_REQUEST_TIMEOUT` (default: `10.0` seconds)
  * `GOBUS_LOG_LEVEL` (default: `INFO`)
  * `GOBUS_OPERATORS_CONFIG` (optional JSON file for future multi-operator scenarios)
* Extensible architecture for defining multiple operator credentials (`OperatorCredentials`) without hardcoding secrets in source code.
* Password masking implemented on `__repr__` of all configuration objects.

---

## D. HTTP Client
Implemented in `simulator/api/client.py`:
* Wraps `requests.Session` for persistent HTTP connection pooling.
* Automatically attaches `Authorization: Bearer <token>` when tokens are present.
* Centralizes error handling and response normalization:
  * HTTP 401 -> `AuthenticationError`
  * HTTP 403 -> `AccountForbiddenError`
  * HTTP 404 -> `AssignmentNotFoundError`
  * HTTP 422 -> `InvalidPayloadError`
  * HTTP 429 -> `RateLimitExceededError`
  * HTTP 400 -> `TripSessionError`
  * Timeouts / Connection Refused -> `BackendUnavailableError`
* Never logs authorization headers or sensitive request payloads.

---

## E. Authentication
Implemented in `simulator/api/auth.py`:
* `operator_login(client, session, password)`: Dispatches JSON payload to `POST /api/auth/operator/login`.
* Validates presence of `access_token` in response.
* Populates runtime identity (`user_id`, `name`, `role`, `organization_id`, `organization_name`).
* Stores the JWT token strictly in-memory inside `OperatorSession._access_token`.
* `operator_logout(session)`: Clears in-memory credentials and resets state.
* Does not persist tokens or passwords to disk.

---

## F. Assignment Discovery
Implemented in `simulator/api/assignment.py`:
* `fetch_operator_assignment(client, session)`: Calls `GET /api/operator/me/assignment`.
* Parses response into typed `AssignmentContext`:
  * `assignment_id`, `trip_id`, `service_id`, `service_code`, `service_name`
  * `route_id`, `route_code`, `route_name`, `direction`
  * `vehicle_id`, `vehicle_number`, `planned_start_at`, `trip_status`
  * `assigned_device_id`, `active_tracking_session_id`
* Emits a clean `AssignmentNotFoundError` if no active duty assignment is dispatched.

---

## G. Trip Start / End
Implemented in `simulator/api/trip.py`:
* `start_trip_tracking(client, session, trip_id)`: Dispatches `POST /api/trips/{trip_id}/start` with `{}` body. Captures `tracking_session_id` and sets session state to `TRACKING`.
* `end_trip_tracking(client, session, trip_id)`: Dispatches `POST /api/trips/{trip_id}/end` with `{}` body. Clears tracking session and sets mode to `STOPPED`.

---

## H. Telemetry Client
Implemented in `simulator/api/telemetry.py`:
* `send_telemetry_batch(client, session, packets, session_id)`: Sends `POST /api/tracking/batch`.
* Accepts batches from 1 to 500 packets (`min_length=1, max_length=500`).
* Parses `TrackingBatchResponse`: captures `accepted`, `duplicates`, `retryable`, and `rejected` details.
* **CRITICAL INVARIANT PRESERVED:** Telemetry packets do **NOT** contain `vehicle_id` or `route_id`. The backend derives these via `session.trip_id`.

---

## I. Packet Identity
* Each packet generated by `create_telemetry_packet()` receives a newly generated RFC 4122 version 4 UUID (`packet_id`).
* Guarantees packet-level idempotency and deduplication across uploads.

---

## J. Device Sequence
* Maintained by `OperatorSession.next_sequence()`:
  * Strictly monotonically increasing integer (`device_sequence = 1, 2, 3...`).
  * Initialized to 0 upon session creation and preserved across batches during an active session.
  * Prevents sequence deduplication rejection by the GoBus ingestion pipeline.

---

## K. Timestamp Handling
* Handled by `create_telemetry_packet()`:
  * Timestamps formatted in ISO-8601 UTC: `YYYY-MM-DDTHH:MM:SS.sssZ`.
  * Normalized to UTC (`timezone.utc`).
  * Real-time default: timestamps reflect current UTC time, avoiding future skew rejection (`allowed_skew = 300s`).

---

## L. Heartbeat Client
Implemented in `simulator/api/heartbeat.py`:
* `send_device_heartbeat(client, session, battery_level, network_type, gps_status, app_version)`:
  * Dispatches `POST /api/tracking/heartbeat`.
  * Supports real backend fields (`session_id`, `battery_level`, `network_type`, `gps_status`, `app_version`, `timestamp`).
  * Updates device connectivity and battery indicators.

---

## M. Crowding Client
Implemented in `simulator/api/crowding.py`:
* `submit_crowding_report(client, session, vehicle_id, crowding_state, confidence, observed_at)`:
  * Dispatches `POST /api/crowding/reports`.
  * Uses verified fields: `report_id`, `vehicle_id`, `crowding_state`, `confidence`, `observed_at`.
  * Validates state against allowed `CrowdingState` enum (`UNKNOWN`, `LOW`, `MODERATE`, `HIGH`, `FULL`).
  * Enforces confidence between `0.0` and `1.0`.
  * Does NOT send `"level"` or `"source_type"`.
  * Gracefully catches and raises `RateLimitExceededError` on HTTP 429.

---

## N. Error Handling
* Domain-specific exception hierarchy in `simulator/core/exceptions.py`.
* Every API error response extracts backend JSON `detail` and raises typed exceptions.
* Recoverable errors (duplicates, rejected packets, rate limits) are surfaced as clean diagnostic objects rather than crashing execution.

---

## O. Logging & Secret Redaction
Implemented in `simulator/utils/logging.py`:
* Configures dual logging to console and `logs/simulator.log`.
* `RedactingFilter` automatically scrubs:
  * JWT access tokens (`eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+`) -> `[REDACTED_JWT]`
  * Bearer authorization headers -> `Bearer [REDACTED_TOKEN]`
  * Password values in key-value and JSON strings -> `***REDACTED***`
* Operator passwords and JWTs are never written to logs or disk.

---

## P. CLI Commands
Implemented in `simulator/main.py`:
* `python -m simulator.main health`: Checks backend reachability without requiring credentials.
* `python -m simulator.main inspect-assignment`: Authenticates as the configured operator and prints duty assignment details without starting tracking.
* `python -m simulator.main smoke-test`: Full single-bus integration loop (Login -> Assignment -> Start Trip -> 1 Telemetry Packet -> Heartbeat -> End Trip).

---

## Q. Automated Tests
Comprehensive offline test suite in `tests/` using Python's standard `unittest` framework with mocked HTTP sessions:
* `test_api_client.py` (10 tests): URL building, headers, status code mapping, timeout/connection errors.
* `test_auth.py` (4 tests): JSON login format, token extraction, error handling, session cleanup.
* `test_assignment.py` (3 tests): Duty assignment parsing, unauthenticated checks, 404 clean handling.
* `test_trip.py` (3 tests): Trip start/end requests and session mode transitions.
* `test_telemetry.py` (5 tests): UUIDs, coordinate validation, non-inclusion of vehicle/route IDs, batch ACK handling.
* `test_heartbeat.py` (2 tests): Heartbeat payload formatting and response validation.
* `test_crowding.py` (4 tests): Verified field validation (`crowding_state`, `confidence`), rate limit handling.
* `test_session.py` (3 tests): State progression, monotonic sequence counter, safe summary generation.
* `test_logging_safety.py` (3 tests): Verified redaction of JWTs, Bearer headers, and passwords.

**Test Run Results:**
```
Ran 37 tests in 0.076s
OK (All 37 passed)
```

**Compilation Results:**
```
python -m compileall simulator
Listing 'simulator'...
Compiling 'simulator/__init__.py'...
Listing 'simulator/api'...
Listing 'simulator/config'...
Listing 'simulator/core'...
Listing 'simulator/scenarios'...
Listing 'simulator/utils'...
OK (Exit code 0)
```

---

## R. Real Backend Integration Result
* Connectivity test executed:
  `python -m simulator.main health`
* Backend state: Port 8000 was offline (`ConnectionRefusedError`). The simulator correctly and gracefully caught `BackendUnavailableError`, logged the connection status safely without crashing, and returned exit code 1.
* Standalone offline smoke testing with mocks verified 100% of the lifecycle components.

---

## S. Build 3 Safety
* The simulator does not duplicate or bypass Build 3.
* Contains no ETA calculations, route matching, dwell detection, or stop progression logic.
* Generates only raw external telemetry inputs (`observed_at`, `lat`, `lon`, `speed_mps`, `heading`, `device_sequence`) which Build 3 ingests through `IntelligenceOrchestrator`.

---

## T. Product Code Safety
* **Zero GoBus product files modified.**
* All additions reside strictly within `simulator/`, `tests/`, `.env.example`, `requirements.txt`, and `README.md`.
* `git status` confirmed no files in `backend/`, `apps/`, or database migrations were modified.

---

## U. Dependencies
* Minimal dependencies maintained:
  * `requests>=2.28.0`
  * `python-dotenv>=1.0.0`
* No heavy database, GIS, or machine learning libraries installed.

---

## V. File Structure
```
simulator/
├── .env.example
├── requirements.txt
├── README.md
├── logs/
│   └── simulator.log
├── simulator/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── assignment.py
│   │   ├── auth.py
│   │   ├── client.py
│   │   ├── crowding.py
│   │   ├── heartbeat.py
│   │   ├── telemetry.py
│   │   └── trip.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py
│   │   └── session.py
│   ├── scenarios/
│   │   └── __init__.py
│   └── utils/
│       ├── __init__.py
│       └── logging.py
└── tests/
    ├── __init__.py
    ├── test_api_client.py
    ├── test_assignment.py
    ├── test_auth.py
    ├── test_crowding.py
    ├── test_heartbeat.py
    ├── test_logging_safety.py
    ├── test_session.py
    ├── test_telemetry.py
    └── test_trip.py
```

---

## W. Known Limitations
* Phase 1 is strictly the HTTP API adapter and session state foundation.
* No spatial route interpolation or multi-bus movement generation is implemented yet (reserved for subsequent phases).

---

## X. Next Phase Recommendation
* **Phase 2:** Authentication refinement and multi-operator credential provisioning.
* **Phase 3:** Route topology and stop sequence discovery through public passenger endpoints (`/api/passenger/services/{service_id}`).
* **Phase 4 & 5:** Single-bus route movement generator and continuous telemetry transmission loop.
