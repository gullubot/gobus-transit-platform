# BUILD 4 — DEMO SIMULATOR PHASE 3.5 INTEGRATION VALIDATION REPORT
## Real Backend Integration Validation & Demo Scenario Verification

**Report Date:** 2026-09-03T01:23:00+05:30  
**Phase:** 3.5 Verification-Only Checkpoint  
**Status:** AUDITED & VERIFIED (Distinguishing Offline Unit Correctness from Live Environment Availability)

---

## 1. Environment Used

* **Host Environment:** Windows local workstation development environment.
* **Database Layer:** Container `transit-db` (`postgis/postgis:16-3.4`) active and healthy on port 5432.
* **Frontend Web Layer:** Vite dev server active on port 5173 (`http://localhost:5173/`).
* **FastAPI Backend Process:** **OFFLINE / NOT RUNNING.** Port scan on TCP port 8000 confirmed `[WinError 10061] No connection could be made because the target machine actively refused it`.
* **Build 3 Intelligence Services:** Not actively running in background (coupled to FastAPI runtime).

---

## 2. Backend URL Category

* **Configured Target:** `http://localhost:8000` (Local Development Backend API).
* **Connection Status:** Actively refused (`ConnectionRefusedError`).
* **Secrets Protection:** No secret credentials, passwords, or raw tokens exposed in configuration or logs.

---

## 3. Operator Identities Audited

Based on repository inspection (`backend/app/db/seed.py` and `backend/scripts/seed_demo_operator.py`):
1. Operator 1: `O-***` (`O-001` with assigned password) — designated for service `AC4B` (Route `SD5`).
2. Operator 2: `DRV***` (`DRV001` with assigned password) — seeded driver identity.
3. Operator 3: `CND***` (`CND001` with assigned password) — seeded conductor identity.

*Note: In accordance with project security instructions, operator passwords and tokens are never logged or exported in reports.*

---

## 4. Assignments Audited

* **Designated Service:** `AC4B` on Route `SD5` (Howrah to Salt Lake Karunamoyee), consisting of 3 sequenced stops.
* **Live Discovery State:** Because the FastAPI backend process was not active on port 8000, live dynamic discovery via `GET /api/operator/me/assignment` could not execute over HTTP.
* **Database Mutating Restriction:** In adherence to strict checkpoint instructions ("DO NOT access PostgreSQL directly. DO NOT import GoBus backend modules. DO NOT modify database records manually"), no direct SQL queries or manual insertions were performed.

---

## 5. Test Timestamps

* **Environment Audit & Port Scan:** 2026-09-03T01:20:30+05:30
* **Simulator Health Check Probe:** 2026-09-03T01:20:04+05:30
* **Simulator Auth Probe:** 2026-09-03T01:22:16+05:30
* **Offline Unit Test Discovery Suite:** 2026-09-03T01:21:30+05:30
* **Scenario Dry-Run Executions:** 2026-09-03T01:14:28+05:30 to 2026-09-03T01:16:00+05:30

---

## 6. Validation 1 — Single Bus Real End-to-End

* **Operational Status:** **BLOCKED**
* **Technical Reason:** The GoBus FastAPI server on `http://localhost:8000` is currently offline. When attempting `POST /api/auth/operator/login`, the simulator cleanly caught `NewConnectionError`, raised `BackendUnavailableError`, and terminated with error code 1 without leaking secrets or crashing.
* **Unit/Offline Validation:** **PASS** (100% verified with offline mocks in `tests/test_trip.py`, `tests/test_movement.py`, and `tests/test_telemetry.py`).

---

## 7. Validation 2 — Two Bus Real Concurrent Run

* **Operational Status:** **NOT EXECUTED**
* **Technical Reason:** Requires two simultaneously active operator duty assignments running against a live backend. Because the backend API server is currently not running, live concurrent authentication and session creation could not be executed.
* **Unit/Offline Validation:** **PASS** (`tests/test_fleet.py` proves multi-bus isolation, concurrent stepping, independent sequence numbers, and strict rejection of duplicate operator accounts).

---

## 8. Validation 3 — Delay Demo

* **Operational Status:** **BLOCKED (Live) / PASS (Offline & Dry-Run)**
* **Technical Reason:** Live verification requires a running Build 3 ETA engine in FastAPI to observe whether ETA updates organically upon speed drops.
* **Scenario Execution & Validation:**
  - `python -m simulator.main simulate --scenario delay_demo --dry-run` succeeded with code 0.
  - Baseline speed: 8.33 m/s.
  - Delayed speed: 2.50 m/s applied at T+20.0s.
  - Restored speed: 8.33 m/s restored at T+60.0s.
  - The simulator does NOT calculate ETA itself; it only emits physical velocity and coordinates, keeping Build 3 completely unpolluted.

---

## 9. Validation 4 — Offline / Stale Demo

* **Operational Status:** **BLOCKED (Live) / PASS (Offline & Dry-Run)**
* **Technical Reason:** Live verification requires running `AlertEngine` to detect missing telemetry (>120s) and produce stale vehicle alerts.
* **Scenario Execution & Validation:**
  - `python -m simulator.main simulate --scenario offline_demo --dry-run` succeeded with code 0.
  - Telemetry and heartbeat transmission are suppressed at T+20.0s and restored at T+60.0s.
  - Zero alert records were manually inserted, strictly abiding by external simulator boundaries.

---

## 10. Validation 5 — Crowding Demo

* **Operational Status:** **BLOCKED (Live) / PASS (Offline & Dry-Run)**
* **Technical Reason:** Backend HTTP endpoint `POST /api/crowding/reports` was unreachable due to backend offline state.
* **Payload Verification:**
  - Simulator schema verified against GoBus backend `POST /api/crowding/reports`:
    - `report_id` (UUIDv4)
    - `vehicle_id` (UUID)
    - `crowding_state` (`HIGH`, `FULL`)
    - `confidence` (float `0.0` to `1.0`)
    - `observed_at` (ISO 8601 UTC)
  - Dry run and unit test `test_crowding.py` confirmed 100% compliant JSON payload construction.

---

## 11. Validation 6 — Service Shortage Demo

* **Backend Logic Inspection:**
  - Audited `backend/app/services/insights_service.py` (`InsightsService`):
    - `analyze_recurring_crowding`: requires minimum 5 reports, >60% HIGH/FULL ratio over 30 days.
    - `analyze_service_performance`: requires minimum 5 completed trips with >40% delayed departure over 30 days.
    - `analyze_missed_trips`: requires minimum 5 trips with >20% CANCELLED/ABANDONED status over 30 days.
    - `analyze_fleet_capacity`: checks vehicle capacity utilization over 30 days.
  - Audited `backend/app/api/routes/passenger.py` & `backend/app/api/routes/admin_live.py`:
    - Real-time active bus count is computed dynamically via `active_buses_count` (from `BusCurrentState`).
    - Service shortage in real-time operations manifests as fewer active vehicles on scheduled routes.
* **Operational Status:** **NOT VERIFIED (Live) / PASS (Design & Dry-Run)**
* **Technical Reason:** The 30-day historical analytics engine cannot be triggered by a single real-time withholding of a bus without 30 days of trip history. Real-time active vehicle count reflects withheld buses immediately, but live testing was blocked by backend offline state.

---

## 12. Validation 7 — Full Demo

* **Operational Status:** **BLOCKED (Live) / PASS (Offline & Dry-Run)**
* **Timeline Verified:**
  - `T+000.0s`: `START_BUS` on `bus-1`
  - `T+010.0s`: `START_BUS` on `bus-2`
  - `T+025.0s`: `SET_SPEED` (3.0 m/s) on `bus-1`
  - `T+035.0s`: `SET_CROWDING` (`HIGH`) on `bus-2`
  - `T+045.0s`: `SET_TELEMETRY_ENABLED` (`False`) on `bus-1`
  - `T+065.0s`: `SET_TELEMETRY_ENABLED` (`True`) on `bus-1`
  - `T+075.0s`: `RESTORE_SPEED` (8.33 m/s) on `bus-1`
  - `T+085.0s`: `SET_CROWDING` (`FULL`) on `bus-2`
* `python -m simulator.main simulate --scenario full_demo --dry-run` passed with zero errors.

---

## 13. Backend Response Evidence

During direct CLI probes to the configured backend (`http://localhost:8000`):
```
[ERROR] Backend unreachable at http://localhost:8000:
HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /api/health
(Caused by NewConnectionError("HTTPConnection(host='localhost', port=8000): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
```
The simulator handled the connection failure gracefully, returning structured exceptions (`BackendUnavailableError`) without unhandled stack traces or sensitive credential leakage.

---

## 14. Build 3 Observation

* **Build 3 Architecture Integrity:** 100% frozen.
* **Isolation:** Zero backend modules imported, zero direct database calls made. Build 3 algorithms (`tracker_fusion.py`, `route_matching.py`, `eta_engine.py`) remain completely untouched.

---

## 15. Admin Web Observation

* Dev server is running on `http://localhost:5173/`.
* Because the backend API server on port 8000 is down, live vehicle tracking markers and real-time operational state cannot be rendered in the browser.

---

## 16. Test Count

* **Simulator Unit Test Suite:**
  ```bash
  python -m unittest discover -s tests -p "test_*.py" -v
  ```
  **Result:** `Ran 80 tests in 0.153s — OK (80 passed, 0 failed, 100% success)`
* **Code Compilation:**
  ```bash
  python -m compileall simulator
  # Code 0, clean compilation
  ```

---

## 17. Security Audit

* Checked live probe logs and dry-run outputs.
* Confirmed **zero occurrences** of passwords, Bearer tokens, or raw JWTs (`eyJ...`).
* Verified token storage is memory-only; no tokens or cookies are persisted to disk.

---

## 18. Git Status Audit

Checked repository status before and after validation:
* **Zero changes to `backend/`**
* **Zero changes to `apps/`**
* **Zero changes to migrations**
* **Zero changes to Build 3 intelligence**
All simulator code remains 100% external and isolated in `simulator/`.

---

## 19. Limitations

1. **Backend Server Dependency:** Live integration validations (Validations 1–7) require the FastAPI application server (`uvicorn app.main:app`) to be running and accessible on the host port.
2. **Duty Assignment Pre-Condition:** Live multi-bus tests require active trip assignments provisioned for each simulated operator account in the backend database.
3. **Analytics Lookback:** Service shortage insights in `InsightsService` evaluate a 30-day historical window requiring historical completed/missed trip records.

---

## 20. Explicit Acceptance Criteria Evaluation for Phase 3.5

| Validation Item | Status | Verification Evidence |
|---|:---:|---|
| Backend Reachability & Environment Audit | **PASS** | Confirmed PostgreSQL up on 5432, Vite on 5173, FastAPI down on 8000. |
| Single Bus Real End-to-End | **BLOCKED** | FastAPI process offline; unit test mocks and dry-run 100% verified. |
| Two Bus Real Concurrent Run | **NOT EXECUTED** | Blocked by backend availability; unit test multi-bus isolation 100% verified. |
| Delay Demo Scenario | **PARTIAL** | Dry run & scheduler pass; live ETA observation blocked by backend availability. |
| Offline / Stale Demo Scenario | **PARTIAL** | Dry run & scheduler pass; live alert generation blocked by backend availability. |
| Crowding Demo Scenario | **PARTIAL** | Payload schema matches `/api/crowding/reports`; live submission blocked by backend availability. |
| Service Shortage Backend Audit | **PASS** | Audited `InsightsService` & `BusCurrentState`; documented 30-day requirement. |
| Full Demo Scenario | **PARTIAL** | Dry run & timeline pass; live multi-bus execution blocked by backend availability. |
| Comprehensive Unit Tests Passing | **PASS** | 80/80 unit tests pass in 0.153s. |
| Clean Compilation | **PASS** | `compileall simulator` exited with code 0. |
| CLI Commands Operational | **PASS** | `health`, `inspect-assignment`, `simulate`, `--dry-run` all operational. |
| Security Audit Passed | **PASS** | Logging redaction and memory-only token storage confirmed. |
| Product Code Frozen | **PASS** | Git status confirms zero modifications outside `simulator/`. |
| Implementation Report Written | **PASS** | `BUILD_4_DEMO_SIMULATOR_PHASE_3_5_INTEGRATION_VALIDATION_REPORT.md` written. |
