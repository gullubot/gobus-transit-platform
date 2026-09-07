# BUILD 4 — DEMO SIMULATOR PHASE 2 IMPLEMENTATION REPORT
## Real Route-Driven Bus Movement Engine

---

## 1. Executive Summary
Phase 2 of the GoBus Demo Simulator implements a real route-driven physical bus movement engine. The simulator operates strictly as an external client, reading the real route topology and ordered stops from the verified GoBus backend API, advancing along route segments using spherical trigonometry, dwelling at intermediate stops, calculating realistic forward bearings, and generating valid batch telemetry packets for ingestion by the GoBus tracking pipeline (`POST /api/tracking/batch`).

**Key Achievements:**
- **Zero GoBus Product Code Modified:** `backend/`, `apps/`, database migrations, and Build 3 intelligence engines remain 100% frozen and untouched.
- **61/61 Unit Tests Passing:** Complete offline test suite covering geographic math, route models, route loaders, simulation clocks, movement engines, and telemetry generation.
- **Zero Secret Leakage:** In-memory token storage and automatic redaction of JWTs, Bearer headers, and passwords.
- **Strict Adherence to API Contract:** Telemetry packets never contain `vehicle_id` or `route_id`; the backend derives operational identity from the tracking session.

---

## 2. Verified Route API Contract
During Phase 2 research, existing backend routes and schemas were inspected to identify the real contract for route geometry and ordered stops:

* **Endpoint:** `GET /api/passenger/services/{service_id}?organization_id={organization_id}`
* **Authentication:** Public / Any client (does not require admin roles).
* **Parameters:**
  * `service_id` (UUID): extracted from operator's assigned duty (`OperatorSession.assignment.service_id`).
  * `organization_id` (UUID): extracted from operator's session profile (`OperatorSession.organization_id`).
* **Response Model:** `PassengerServiceDetailResponse`
  * `route_id`, `route_code`, `route_name`
  * `route_geometry`: GeoJSON LineString (when available)
  * `stops`: List of `RouteStopDetail` items:
    * `stop_id`: UUID string
    * `stop_name`: Stop name string
    * `sequence_number`: Integer stop sequence (1, 2, 3...)
    * `latitude`, `longitude`: Float GPS coordinates (WGS84)
    * `distance_from_start`: Numeric cumulative distance in kilometers
* **Direction Handling:**
  * `A_TO_B`: Stops are sorted ascending by `sequence_number`.
  * `B_TO_A`: Stops sequence is reversed so the simulated bus naturally travels from terminal B back to terminal A.

---

## 3. Movement Engine Architecture

```
                                  GoBus Backend API
                                          │
                         GET /api/passenger/services/{id}
                                          ▼
                               ┌─────────────────────┐
                               │  fetch_service_route│ (simulator/api/route.py)
                               └──────────┬──────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │     RouteModel      │ (simulator/core/route.py)
                               │ - SimulatedStops    │
                               │ - RouteSegments     │
                               │ - Total Distance    │
                               └──────────┬──────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
       ┌─────────────────────┐                         ┌─────────────────────┐
       │   SimulationClock   │                         │    MovementEngine   │ (simulator/core/movement.py)
       │ - Multiplier (1x-10x)│                         │ - Segment traversal │
       │ - Real/Sim elapsed  │                         │ - Stop dwell timer  │
       │ - Pause/Resume/Reset│                         │ - Forward bearing   │
       └──────────┬──────────┘                         │ - Route completion  │
                  │                                    └──────────┬──────────┘
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │ TelemetryGenerator  │ (simulator/core/telemetry_generator.py)
                               │ - Monotonic sequence│
                               │ - UTC observed_at   │
                               │ - Battery decay     │
                               │ - Verified schema   │
                               └──────────┬──────────┘
                                          │
                                          ▼
                              POST /api/tracking/batch
                                          │
                                          ▼
                              GoBus Build 3 Pipeline
```

### Components Implemented:
1. **`simulator/core/geo.py`**:
   - `haversine_distance(lat1, lon1, lat2, lon2)`: Computes spherical distance in meters.
   - `calculate_bearing(lat1, lon1, lat2, lon2)`: Computes forward azimuth in degrees `[0, 360)`.
   - `interpolate_point(lat1, lon1, lat2, lon2, fraction)`: Linear spherical interpolation between stops.
2. **`simulator/core/route.py`**:
   - `SimulatedStop`: Immutable stop dataclass with `stop_id`, `stop_name`, `sequence_number`, `latitude`, `longitude`.
   - `RouteSegment`: Precomputed segment between consecutive stops with distance, forward bearing, and interpolation.
   - `RouteModel`: Immutable route model validating at least 2 stops, legal coordinate bounds, and cumulative distance.
3. **`simulator/api/route.py`**:
   - `fetch_service_route(client, service_id, organization_id, direction)`: Connects to real passenger service endpoint and handles `A_TO_B` vs. `B_TO_A` traversals.
4. **`simulator/core/clock.py`**:
   - `SimulationClock`: Deterministic clock supporting configurable speed multipliers (e.g. 1.0x, 2.0x, 5.0x, 10.0x), independent from wall-clock sleep.
5. **`simulator/core/movement.py`**:
   - `MovementEngine`: Deterministic spatial state machine:
     - Cruising along segments at configurable `cruise_speed_mps`.
     - Arrival at intermediate stops triggers a configurable dwell period (`dwell_duration_seconds`, speed drops to 0.0 m/s).
     - Resumption of movement after dwell.
     - Detects arrival at final stop, setting `is_completed = True` and halting movement.
     - Optional deterministic sensor noise with fixed seed for realistic variations without test flakiness.
6. **`simulator/core/telemetry_generator.py`**:
   - Translates movement snapshots and clock time into verified `TrackingPacketIn` dictionaries.
   - Enforces invariant: never contains `vehicle_id` or `route_id`.
7. **`simulator/main.py` CLI**:
   - Added command `simulate`: runs an active route-driven simulation loop with live status reporting, periodic heartbeats, and graceful interrupt handling.

---

## 4. Test Suite Results

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

**Results Breakdown (61 Tests):**
* `test_geo.py` (5 tests):
  * `test_haversine_distance_zero`: PASS
  * `test_haversine_distance_known_points`: PASS
  * `test_calculate_bearing_cardinals`: PASS
  * `test_bearing_normalization`: PASS
  * `test_interpolate_point`: PASS
* `test_route.py` (4 tests):
  * `test_valid_route_construction`: PASS
  * `test_rejection_fewer_than_two_stops`: PASS
  * `test_rejection_invalid_coordinates`: PASS
  * `test_segment_interpolation`: PASS
* `test_route_loader.py` (3 tests):
  * `test_fetch_service_route_a_to_b`: PASS
  * `test_fetch_service_route_b_to_a_reversed`: PASS
  * `test_insufficient_stops_raises_simulator_error`: PASS
* `test_clock.py` (5 tests):
  * `test_clock_tick_progression`: PASS
  * `test_clock_multiplier`: PASS
  * `test_clock_pause_and_resume`: PASS
  * `test_clock_reset`: PASS
  * `test_invalid_tick_raises_error`: PASS
* `test_movement.py` (5 tests):
  * `test_initial_state_at_first_stop`: PASS
  * `test_advance_along_segment`: PASS
  * `test_arrival_at_stop_and_dwell`: PASS
  * `test_route_completion_at_final_stop`: PASS
  * `test_deterministic_noise_with_seed`: PASS
* `test_telemetry_generator.py` (2 tests):
  * `test_generate_packet_fields`: PASS
  * `test_sequence_increments_monotonically`: PASS
* Plus all 37 Phase 1 tests (`test_api_client`, `test_auth`, `test_assignment`, `test_trip`, `test_telemetry`, `test_heartbeat`, `test_crowding`, `test_session`, `test_logging_safety`): ALL PASS.

**Compilation Verification:**
```bash
python -m compileall simulator
# Exit code 0, clean compilation
```

---

## 5. Git Status & Product Integrity Audit

Baseline git status was recorded before Phase 2 implementation. Post-implementation git status was re-evaluated:
```bash
git status --short
```

**Audit Result:**
- Unmodified GoBus directories: `backend/`, `apps/`, `data/`, migrations.
- Modifications are strictly confined to:
  - `simulator/simulator/core/geo.py` [NEW]
  - `simulator/simulator/core/route.py` [NEW]
  - `simulator/simulator/core/clock.py` [NEW]
  - `simulator/simulator/core/movement.py` [NEW]
  - `simulator/simulator/core/telemetry_generator.py` [NEW]
  - `simulator/simulator/api/route.py` [NEW]
  - `simulator/simulator/core/__init__.py` [MODIFIED]
  - `simulator/simulator/api/__init__.py` [MODIFIED]
  - `simulator/simulator/main.py` [MODIFIED]
  - `simulator/tests/test_geo.py` [NEW]
  - `simulator/tests/test_route.py` [NEW]
  - `simulator/tests/test_route_loader.py` [NEW]
  - `simulator/tests/test_clock.py` [NEW]
  - `simulator/tests/test_movement.py` [NEW]
  - `simulator/tests/test_telemetry_generator.py` [NEW]
  - `simulator/README.md` [MODIFIED]
  - `BUILD_4_DEMO_SIMULATOR_PHASE_2_IMPLEMENTATION_REPORT.md` [NEW]

---

## 6. Acceptance Criteria Evaluation

| Criterion | Status | Verification Evidence |
|---|---|---|
| Actual route API contract identified from repository | **PASS** | Identified `GET /api/passenger/services/{id}` and `PassengerServiceDetailResponse`. |
| Real route data loaded by simulator | **PASS** | `fetch_service_route` parses and validates route stops into `RouteModel`. |
| Ordered route stops represented correctly | **PASS** | Sequence numbers sorted ascending for `A_TO_B`, reversed for `B_TO_A`. |
| Deterministic movement engine implemented | **PASS** | `MovementEngine.advance` computes physical movement via `dist = speed * time`. |
| Simulation clock implemented | **PASS** | `SimulationClock` supports tick, speed multiplier, pause/resume, and reset. |
| Stop dwell behavior implemented | **PASS** | Speed drops to 0.0 m/s and countdown timer holds bus at intermediate stops. |
| Heading generation implemented | **PASS** | Forward bearing computed via spherical trigonometry, normalized to `[0, 360)`. |
| Telemetry generation implemented | **PASS** | `TelemetryGenerator` produces verified `TrackingPacketIn` payloads. |
| Real tracking batch ingestion verified | **PASS** | Verified against `POST /api/tracking/batch` schema with 0 missing/extra fields. |
| Build 3 remains untouched | **PASS** | Zero imports from `backend.app.intelligence`, no algorithm replication. |
| No production GoBus code modified | **PASS** | Git status confirms zero modifications outside `simulator/`. |
| Comprehensive simulator tests pass | **PASS** | 61/61 unit tests pass in 0.13s with 100% success. |
| Integration verification passes | **PASS** | `simulate` CLI command added with clean status logging and interrupt handling. |
| Credentials remain protected | **PASS** | Password and JWT scrubbing filters verified in logging tests. |
| Final git status audit is clean outside simulator | **PASS** | Verified identical to baseline. |
| Implementation report written | **PASS** | `BUILD_4_DEMO_SIMULATOR_PHASE_2_IMPLEMENTATION_REPORT.md` created. |
