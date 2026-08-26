# BUILD 2 — Operator Authentication, Device Validation, Telemetry Pipeline & Minimal Operator Experience

**Status:** PASS  
**Build Scope:** BUILD 2 ONLY (No BUILD 3+ intelligence, no schema migrations)  
**Authoritative Baseline:** CHECKPOINT 13 / BUILD 0 / BUILD 1  

---

## 1. Executive Summary
BUILD 2 delivers the complete end-to-end operational vertical slice for bus operator authentication, duty assignment retrieval, assignment-based device validation, and real-time telemetry ingestion with offline resilience.

The architecture enforces:
1. **Server-derived identity and authority:** Operator roles (`DRIVER`, `CONDUCTOR`) and organization context are extracted strictly from server-validated Argon2 hashes and signed JWT claims.
2. **Assignment-based device authorization:** Reuses the frozen BUILD 1 schema (`trip_assignments.device_id`) without requiring new pairing tables or unapproved database migrations.
3. **High-integrity telemetry ingestion:** Implements monotonic device sequence tracking, idempotent packet UUID deduplication, server-authoritative `received_at` timestamps, out-of-order tolerance, and packet-level ACK contracts (`accepted`, `duplicates`, `retryable`, `rejected`).
4. **Android foreground location tracking:** Uses an Android Foreground Location Service with persistent notification, Room local SQLite queue buffering, and network-aware background synchronization for seamless offline survival and automatic upload upon network restoration.

---

## 2. Toolchain & Dependencies

### Backend
- **Python:** 3.12.13
- **FastAPI:** 0.115.12
- **SQLAlchemy:** 2.0.41 (Synchronous engine with session scoping)
- **PyJWT:** 2.10.0 (JWT signing & verification with HS256)
- **pwdlib[argon2]:** 0.3.1 (Argon2 password hashing)
- **PostgreSQL / PostGIS:** 16+ with PostGIS extensions
- **Ruff:** 0.11.12 (Linting & Formatting clean)
- **Pytest:** 8.4.1 (31 tests passed in 11.69s)

### Android
- **Kotlin:** 2.1.0
- **Jetpack Compose:** 2024.12.01 BOM (Material 3)
- **Room SQLite:** 2.6.1 with KSP 2.1.0-1.0.29
- **OkHttp:** 4.12.0
- **Coroutines:** 1.9.0
- **Target SDK:** 35 / Min SDK: 26 / JVM Target: 17

---

## 3. Operator Authentication (`POST /api/auth/operator/login`)

Operators authenticate using their assigned employee credentials:
- **Request:** `{"employee_code": "DRV001", "password": "operator123"}`
- **Verification:** Argon2 hash verified via `pwdlib`.
- **Role Enforcement:** Server checks `User.role in (UserRole.DRIVER, UserRole.CONDUCTOR)`. Administrative roles (`FLEET_ADMIN`, `DEPOT_ADMIN`) are strictly rejected with HTTP 403.
- **Token Output:** Signed JWT containing `sub` (User UUID), `role`, `org_id`, `emp_code`, `exp` (24-hour expiration), and `iat`.

---

## 4. Assignment-Based Device Validation

As dictated by the Checkpoint 13 specification, no new pairing tables were created.
Device validation follows the frozen BUILD 1 schema:
```
AUTHENTICATED OPERATOR
        ↓
OPERATOR PROFILE
        ↓
TRIP ASSIGNMENT (trip_assignments)
        ↓
ASSIGNED DEVICE (trip_assignments.device_id -> devices)
        ↓
TRACKING SESSION (tracking_sessions)
        ↓
TRIP / VEHICLE
```

Validation rules enforced on session start (`POST /api/trips/{trip_id}/start`):
1. Authenticated operator has an active duty assignment for the specified trip.
2. Operator's role matches assignment role (`DRIVER` / `CONDUCTOR`).
3. Assigned device exists in `devices` table and has status `ACTIVE`.
4. Assigned device and trip belong to the operator's organization.
5. Trip status is eligible (`PLANNED` or `ACTIVE`).
6. Duplicate start calls are idempotent (returns existing active session ID).

---

## 5. Duty Assignment API (`GET /api/operator/me/assignment`)

Returns the current active/upcoming assignment:
- `trip_id`, `service_code` ("AC4B"), `service_name` ("City Center Express")
- `route_code` ("R1"), `route_name` ("City Center to Tech Park")
- `direction` ("A_TO_B"), `vehicle_number` ("PNB005234")
- `planned_start_at`, `operator_role`, `assignment_status`
- `assigned_device_status`, `active_tracking_session_id`

---

## 6. Telemetry Ingestion Pipeline (`POST /api/tracking/batch`)

### Ingestion Contract
```json
{
  "session_id": "...",
  "packets": [
    {
      "packet_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "latitude": 30.7333,
      "longitude": 76.7794,
      "accuracy_m": 5.0,
      "speed_mps": 8.5,
      "heading": 90.0,
      "observed_at": "2026-08-26T21:00:00.000Z",
      "device_sequence": 1,
      "battery_level": 95.0,
      "network_type": "4G",
      "gps_status": "AVAILABLE"
    }
  ]
}
```

### Acknowledgement Contract (Partial Success Supported)
```json
{
  "accepted": ["9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"],
  "duplicates": [],
  "retryable": [],
  "rejected": []
}
```

### Telemetry Pipeline Invariants
- **Authoritative Server Timestamp:** `received_at` is generated on the server using `datetime.now(timezone.utc)` and stored alongside the device's `observed_at`.
- **Packet Deduplication:** Global unique index on `packet_id` prevents duplicate insertions.
- **Sequence Deduplication:** Unique constraint on `(device_id, tracking_session_id, device_sequence)` ensures monotonic ordering without duplicate sequence collisions.
- **Out-of-Order Packets:** Packets arriving out of sequence are safely stored and indexed by their `observed_at` and `device_sequence`.

---

## 7. Device Heartbeat (`POST /api/tracking/heartbeat`)

Lightweight device telemetry ping reporting:
- `battery_level` (e.g. 88.0%)
- `network_type` ("CELLULAR" / "WIFI" / "OFFLINE")
- `gps_status` ("AVAILABLE" / "ACQUIRING" / "UNAVAILABLE")
- `app_version` ("0.1.0")
- Updates `devices.last_seen_at`, `devices.battery_level`, and `devices.network_status` in real-time.

---

## 8. Android Operator Experience

The Android application (`apps/android`) provides a minimal, high-contrast, low-cognitive-load experience for transit operators:
1. **Login Screen:** Employee credentials entry ("DRV001" / "operator123") with server URL configuration.
2. **Assignment Screen:** Clear "Today's Duty" card showing service, route, bus number, and departure time with a single primary [START TRACKING] button.
3. **Readiness Screen:** Comprehensive system health check:
   - Location Permission (Fine & Coarse)
   - GPS Hardware status
   - Foreground Service Notification permission
   - Network availability (Warning shown, but DOES NOT block tracking)
   - Battery level status
4. **Active Tracking Screen:**
   - Pulsing green "TRACKING ACTIVE" status banner
   - Route and bus identity
   - Dynamic offline notice when network is disconnected: *"Offline Mode — Location points are safely stored locally in Room queue & will sync automatically when network returns."*
   - Real-time telemetry counters (GPS Status, Network Sync, Packets Recorded, Local Room Buffer Count, Latest Coordinates, Speed, Accuracy)
   - [END TRIP TRACKING] button with confirmation.
5. **Foreground Location Service (`ForegroundTrackingService`):**
   - Implements continuous GPS location listening with `ServiceCompat.startForeground`.
   - Displays persistent notification: *"Transit Tracking Active · Service AC4B · Vehicle PNB005234"*.
   - Persists all observations to local Room SQLite queue prior to network transmission.
   - Periodic synchronization coroutine flushes batches to `/api/tracking/batch` every 3 seconds.
   - Evicts acknowledged `accepted` and `duplicates` packet IDs from Room DB upon ACK.

---

## 9. Offline Survival & Failure Resilience Test

1. **Online Telemetry:** Packets generated by GPS -> persisted to Room -> uploaded to server -> ACK received -> deleted from Room queue.
2. **Network Disconnection:** Mobile data / Wi-Fi disconnected -> Foreground service continues acquiring GPS fixes -> Packets accumulate in Room database -> UI transitions to `OFFLINE / QUEUED` -> Zero packet loss.
3. **Network Restoration:** Connectivity restored -> Synchronization loop detects active connection -> Room queue batch flushed to server -> Server acknowledges -> Room queue emptied -> UI transitions to `SYNCED`.
4. **Server Failure:** Server temporarily down -> Packets safely retained in Room database -> Server restored -> Batches re-sent and accepted.

---

## 10. Test Execution Results

### Backend Pytest Suite: 31 / 31 Passed (100%)
- `tests/unit/test_health.py`: 2 passed
- `tests/integration/test_db.py`: 2 passed
- `tests/integration/test_domain_schema.py`: 9 passed (BUILD 1 regression)
- `tests/api/test_auth.py`: 5 passed
- `tests/api/test_operator.py`: 5 passed
- `tests/api/test_tracking.py`: 8 passed

### Code Quality & Linting
- `ruff check .`: All checks passed (0 errors)
- `ruff format --check .`: 52 files formatted cleanly

---

## 11. Explicit BUILD 3+ Boundary Confirmation

BUILD 2 strictly adheres to the scope boundary. The following engines and features are **NOT IMPLEMENTED** in BUILD 2 and are deferred to BUILD 3+:
- [x] No trip inference engine
- [x] No route snapping / PostGIS map matching
- [x] No bus state determination from telemetry (`bus_current_state` untouched)
- [x] No ETA prediction computation
- [x] No crowding estimation / passenger search events
- [x] No passenger-facing APIs or WebSockets
- [x] No authority management dashboard

---

## 12. Overall Status: PASS

All BUILD 2 acceptance criteria are fully satisfied. The vertical slice is complete, verified, and ready for human review.
