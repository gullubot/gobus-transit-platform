# BUILD 4 — DEMO SIMULATOR PHASE 3.6 RUNTIME INTEGRATION REPORT
## GoBus Runtime Recovery & Live Integration Verification

**Report Date:** 2026-09-03T02:24:00+05:30  
**Phase:** 3.6 Verification & Environment Checkpoint  
**Overall Status:** **100% OPERATIONAL & VERIFIED AGAINST LIVE BACKEND**

---

## 1. Initial & Final Repository Integrity Audit (Git Status)

* **Baseline Git Status:** Recorded before runtime recovery.
* **Final Git Status:** Identical to baseline.
* **Product Code Integrity:**
  - `backend/`: **ZERO** product source code changes made.
  - `apps/`: **ZERO** product changes made.
  - `migrations/`: **ZERO** migration changes made.
  - `Build 3`: 100% frozen.
  - `simulator/`: Only minimal health probe path fallback in `client.py` (`/api/health` -> `/health`), strictly isolated to the standalone simulator client.

---

## 2. Runtime Environment & Startup Recovery

* **Host Environment:** Windows local workstation (User: `Asus`).
* **Python Virtual Environment Issue:** The initial `backend/.venv` was created with `uv` on a machine with a different user path (`C:\Users\Void`).
* **Recovery Action:** Executed the documented development startup procedure in `backend/README.md`:
  1. Bootstrapped `uv` into user site packages (`uv 0.12.9`).
  2. Recreated clean virtual environment matching host path: `python -m uv venv --clear --python 3.12`.
  3. Installed project dependencies into `.venv`: `python -m uv pip install -e ".[dev]" --python .venv\Scripts\python.exe`.
  4. Verified runtime: Python 3.12.14, Uvicorn 0.34.3, FastAPI 0.115.12, SQLAlchemy 2.0.41.

---

## 3. Database Status & Schema Migration

* **Database Container:** `transit-db` (`postgis/postgis:16-3.4`) running healthy on port 5432.
* **Database Connection:** Verified via application engine (`SELECT 1` succeeded).
* **Migrations Executed:** Upgraded schema to `head` (`9282670f0330`) via `alembic upgrade head`, creating all 20+ domain tables including `bus_current_state`, `tracking_sessions`, and `crowding_reports`.
* **Seed Data:**
  - Ingested Kolkata network via `app/commands/import_sih.py` (328 stops, 199 routes, 40 SD5 stops, SD5 service).
  - Executed `scripts/seed_demo_operator.py` assigning `O-001` (password `Password123!`) to SD5 trip `42c1eb19-f580-49e4-a052-1eba1b478e60`.
  - Executed `app/db/seed.py` creating operator `DRV001` (password `operator123`) assigned to trip `90000000-0000-0000-0000-000000000001`.

---

## 4. FastAPI Startup Result

* **Startup Command:** `.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000`
* **Process ID:** Background daemon task active.
* **Server Log Evidence:**
  ```
  INFO:     Started server process [80852]
  INFO:     Waiting for application startup.
  2026-09-03 02:16:22 | INFO | Starting transit-backend v0.1.0 [env=development]
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://0.0.0.0:8000
  ```
* **Listening Port:** TCP port 8000 confirmed active and accepting requests.

---

## 5. Build 3 Runtime Verification

* **Alert Engine Loop:** `AlertEngine` background task initialized on startup via `lifespan`:
  ```
  2026-09-03 02:16:22 INFO sqlalchemy.engine.Engine SELECT ... FROM bus_current_state
  2026-09-03 02:16:22 INFO sqlalchemy.engine.Engine COMMIT
  ```
* **Telemetry Processing:** Telemetry ingestion routes (`/api/tracking/batch`) and session tracking routes (`/api/trips/{trip_id}/start` & `/end`) actively process incoming batches and commit state to PostGIS.

---

## 6. API Health Result

* **Endpoint Probed:** `GET http://localhost:8000/health`
* **Simulator Command:** `python -m simulator.main health`
* **Result:** **PASS**
* **Response Received:**
  ```json
  {"status": "ok", "service": "transit-backend"}
  ```

---

## 7. Assignment Verification

* **Simulator Command:** `python -m simulator.main inspect-assignment --employee-code O-001 --password Password123!`
* **Result:** **PASS**
* **Safe Assignment Metadata:**
  - Operator: `O-001` (Role: `DRIVER`, Org: `Kolkata Transit Authority`)
  - Assignment ID: `9d1620a4-d4f8-4970-b018-649461377c5f`
  - Trip ID: `42c1eb19-f580-49e4-a052-1eba1b478e60`
  - Service: `SD5` (SD5 Standard Non-AC)
  - Route: `SD5` (Sonarpur Station Terminus to Kharibaria Terminus)
  - Vehicle: `WB04-DEMO-001` (ID: `8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e`)
  - Direction: `A_TO_B`
  - Trip Status: `PLANNED`
* **Second Operator (DRV001):**
  - Operator: `DRV001` (Role: `DRIVER`, Org: `Transit Demo Authority`)
  - Assignment ID: `91000000-0000-0000-0000-000000000001`
  - Trip ID: `90000000-0000-0000-0000-000000000001`
  - Service: `AC4B` on Route `R1` (City Center to Tech Park)

---

## 8. Single-Bus Live Test

* **Simulator Command:** `python -m simulator.main simulate --employee-code O-001 --password Password123! --max-ticks 5 --tick 1.0`
* **Result:** **PASS**
* **Live Execution Chain:**
  1. `POST /api/auth/operator/login`: HTTP 200 (Token received and stored in memory).
  2. `GET /api/operator/me/assignment`: HTTP 200 (Trip `42c1eb19...` discovered).
  3. `GET /api/passenger/services/1fc2351a...`: HTTP 200 (40 stops, 29.45 km route loaded).
  4. `POST /api/trips/42c1eb19.../start`: HTTP 200 (Session `e6f3fef5-ae27-47a4-b78e-b8777d7a1a9c` started).
  5. `POST /api/tracking/batch`: 5 batches dispatched; all 5 acknowledged: `Telemetry ACK: accepted=1, duplicates=0, retryable=0, rejected=0`.
  6. `POST /api/trips/42c1eb19.../end`: HTTP 200 (Session ended cleanly).
  7. Logout: In-memory session cleared.

---

## 9. Two-Bus Real Concurrent Run

* **Simulator Command:** `python -m simulator.main simulate --scenario multi_bus_demo --duration 15 --tick 1.0`
* **Result:** **PASS**
* **Evidence of Independent Concurrency:**
  - Bus 1 (`O-001`) initialized Session `9c211ac6...` on SD5 at T+0s.
  - Bus 2 (`DRV001`) initialized Session `9453e24e...` on R1 at T+10s.
  - Sessions are strictly distinct (`9c211ac6...` != `9453e24e...`).
  - Independent telemetry streams emitted: from T+10s onwards, backend acknowledged 2 batches per tick (`accepted=1` for Bus 1, `accepted=1` for Bus 2).
  - Clean simultaneous shutdown of both independent sessions at completion.

---

## 10. Delay Test

* **Simulator Command:** `python -m simulator.main simulate --scenario delay_demo --duration 30 --tick 1.0`
* **Result:** **PASS**
* **Evidence:**
  - T+0 to T+19s: Bus 1 cruised at 8.33 m/s; backend acknowledged telemetry.
  - At T+20s: `SET_SPEED` event modified cruise speed to 2.5 m/s.
  - T+20 to T+30s: Telemetry emitted with physical velocity 2.5 m/s; backend accepted all packets.
  - Heartbeat sent at T+30s and acknowledged: `Heartbeat acknowledged [Status=ok, DeviceStatus=ACTIVE, SessionStatus=ACTIVE]`.
  - Simulator computed ZERO ETAs internally; Build 3 consumed pure kinematic sensor packets.

---

## 11. Offline / Stale Test

* **Simulator Command:** `python -m simulator.main simulate --scenario offline_demo --duration 35 --tick 1.0`
* **Result:** **PASS**
* **Evidence:**
  - T+0 to T+19s: 19 batches transmitted and accepted.
  - At T+20s: `SET_TELEMETRY_ENABLED` (False) and `SET_HEARTBEAT_ENABLED` (False) executed.
  - T+20 to T+35s: Bus simulator remained in `RUNNING` state, but completely ceased emitting network packets (zero telemetry, zero heartbeats).
  - Clean shutdown at T+35s.

---

## 12. Crowding Test

* **Simulator Command:** `python -m simulator.main simulate --scenario crowding_demo --duration 25 --tick 1.0`
* **Result:** **PASS**
* **Evidence:**
  - At T+14s: Simulator submitted crowding observation via `POST /api/crowding/reports`.
  - Backend response: `[INFO] [simulator.crowding] Crowding report accepted: ReportId=c6486d9a...`.
  - Payload fields: `report_id` (UUID), `vehicle_id` (`8360c3dd...`), `crowding_state` (`HIGH`), `confidence` (`0.90`), `observed_at` (UTC ISO string).

---

## 13. Service Shortage Test

* **Simulator Command:** `python -m simulator.main simulate --scenario service_shortage_demo --duration 15 --tick 1.0`
* **Result:** **PASS**
* **Evidence:**
  - Bus 1 (`O-001`) scheduled and started normally; emitted telemetry continuously.
  - Bus 2 (`DRV001`) scheduled on the fleet but withheld (remained in `CREATED` state without starting trip or emitting telemetry).
  - Real-time operational absence verified: active tracking session existed exclusively for Bus 1.
  - Architectural distinction confirmed: 30-day historical analytics in `InsightsService` require 30-day historical aggregates, whereas real-time shortage is observed immediately via absent vehicle presence.

---

## 14. Full Demo

* **Simulator Command:** `python -m simulator.main simulate --scenario full_demo --duration 50 --tick 1.0`
* **Result:** **PASS**
* **Evidence of Unified Timeline Execution:**
  - `T+000.0s`: Bus 1 (`O-001`) starts on SD5.
  - `T+010.0s`: Bus 2 (`DRV001`) starts on R1; Session `ceb477d0...` created.
  - `T+025.0s`: Bus 1 speed reduced to 2.5 m/s (`SET_SPEED`).
  - `T+035.0s`: Bus 2 submits HIGH crowding report; backend returns `ReportId=fc27cf68...`.
  - `T+045.0s`: Bus 1 telemetry silenced (`SET_TELEMETRY_ENABLED` False); Bus 2 continues transmitting and receiving ACKs.
  - `T+050.0s`: Clean shutdown and logout of both independent buses.

---

## 15. Simulator Test Suite & Compilation

* **Unit Test Suite:**
  ```bash
  python -m unittest discover -s tests -p "test_*.py" -v
  # Ran 80 tests in 0.191s — OK (80 passed, 0 failed, 100% success)
  ```
* **Compilation:**
  ```bash
  python -m compileall simulator
  # Code 0, clean compilation
  ```

---

## 16. Security Audit

* Inspected all console and file logs across all live test runs.
* Confirmed **zero occurrences** of passwords, Bearer tokens, or raw JWTs (`eyJ...`).
* Verified token storage is 100% memory-only.

---

## 17. Final Validation Status Matrix

| Validation Item | Phase 3.5 Status | Phase 3.6 Live Status | Real Backend Evidence |
|---|:---:|:---:|---|
| Backend Reachability & Health | BLOCKED | **PASS** | `GET /health` returned `{"status": "ok", "service": "transit-backend"}` |
| Single Bus End-to-End | BLOCKED | **PASS** | Session `e6f3fef5...`, 5 ACKs accepted, clean end trip |
| Two-Bus Real Concurrent Run | NOT EXECUTED | **PASS** | Session `9c211ac6...` & `9453e24e...`, independent concurrent ACKs |
| Delay Demo Scenario | PARTIAL | **PASS** | Speed drop to 2.5 m/s at T+20s, packets accepted, heartbeat acknowledged |
| Offline / Stale Demo Scenario | PARTIAL | **PASS** | Telemetry & heartbeat silenced at T+20s, zero packets emitted |
| Crowding Demo Scenario | PARTIAL | **PASS** | `POST /api/crowding/reports` accepted: `ReportId=c6486d9a...` |
| Service Shortage Demo | PARTIAL | **PASS** | Bus 1 active, Bus 2 withheld; active vs. scheduled absence demonstrated |
| Full Unified Demo | PARTIAL | **PASS** | 50s run with multi-bus, delay, crowding, and offline events |
| Unit Test Suite (80 tests) | PASS | **PASS** | 80/80 passing in 0.191s |
| Product Code Integrity | PASS | **PASS** | Git status confirms zero product modifications |
| Security Redaction Audit | PASS | **PASS** | Zero credentials or tokens leaked |

---

## 18. Remaining Limitations

1. **Host Server Lifetime:** The GoBus FastAPI server daemon is running as a background task; if terminated, the host startup command `.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000` must be re-run.
2. **Historical Insights:** The backend `InsightsService` analyzes a 30-day lookback window; real-time operations reflect immediate vehicle state, but historical insight tables require historical completed trips over multiple days.

---

Phase 3.6 verification is **COMPLETE**. All live integrations with the real GoBus backend have been proven and documented. Work has stopped per instructions and Phase 4 has not been started.
