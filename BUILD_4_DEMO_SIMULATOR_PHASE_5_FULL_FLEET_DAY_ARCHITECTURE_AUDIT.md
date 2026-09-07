# BUILD 4 — DEMO SIMULATOR PHASE 5 ARCHITECTURE AUDIT
## Full-Fleet Full-Day Transit Simulation

**Audit Date:** 2026-09-03T05:20:00+05:30  
**Phase:** Phase 5 Architecture & Repository Audit Checkpoint  
**Status:** **AUDIT ONLY — IMPLEMENTATION FROZEN**  
**Repository State:** Verified against live GoBus backend, PostgreSQL/PostGIS database, and Phase 1–4 simulator codebase.

---

## 1. Executive Summary & Objective

The objective of Phase 5 is to elevate the GoBus Demo Simulator from short, scripted demo scenarios (e.g. 60-second golden demos) to an autonomous, full-scale **Full-Fleet Full-Day Transit Simulation**.

Under this paradigm, the simulator will model an entire transit operating day (e.g., 05:00 to 22:30 IST) across the real transit network, executing sequential vehicle duties, dispatching scheduled trips, simulating realistic passenger crowding dynamics and traffic delays, and pumping high-fidelity telemetry into the real GoBus backend.

This audit inspects the real GoBus backend repository, active database entities, API contracts, intelligence engines, alert/insight services, and the Phase 1–4 simulator codebase to determine the feasibility, scale, constraints, and architecture of a full-day simulation.

```
       REAL GOBUS NETWORK & SCHEDULE DATA (Stops, Routes, Headways)
                                   ↓
                   SERVICE-DAY TIMELINE ORCHESTRATOR
                                   ↓
                       VEHICLE DUTY ENGINE
          (Sequential Trips, Terminus Layovers, Staggered Starts)
                                   ↓
                    CONCURRENT OPERATOR CLIENT POOL
             (Isolated HTTP Clients, Distinct Driver Sessions)
                                   ↓
                     REAL-TIME MOVEMENT & SENSORS
        (Route Geometry, Dwell Timers, GPS Noise, Battery Decay)
                                   ↓
                       STANDALONE CONTROL PANEL
                 (Full-Day HUD, Duty Matrix, Replay)
                                   ↓
                       REAL GOBUS FASTAPI BACKEND
             (Batch Ingestion, PostGIS Map Matching, Fusion)
                                   ↓
                  REAL BUILD 3 INTELLIGENCE & APIS
            (Admin HUD, Passenger Live, Alerts, Insights)
```

---

## 2. Current Verified Foundation (Phases 1–4)

The existing simulator foundation is complete, verified, and passing 96/96 automated tests:

* **Phase 1 (Foundation & API Adapter):** Authenticated operator client (`GoBusHttpClient`, `OperatorSession`), assignment discovery (`/api/operator/me/assignment`), trip lifecycle (`/api/trips/{id}/start`, `/api/trips/{id}/end`), batch telemetry (`/api/tracking/batch`), heartbeat (`/api/tracking/heartbeat`), crowding reports (`/api/crowding/reports`).
* **Phase 2 (Route-Driven Bus Movement):** Route ingestion (`/api/passenger/services/{id}/route`), Vincenty geodesic distance & forward azimuth bearing, linear segment interpolation, stop arrival & dwell state machine, deterministic Gaussian noise, and monotonic telemetry generation.
* **Phase 3 (Multi-Bus & Deterministic Scenario Engine):** Isolated multi-bus sessions via `FleetManager`, priority queue event scheduling via `ScenarioScheduler`, and 7 built-in scenario profiles.
* **Phase 3.6 (Live Backend Integration):** 100% verified against running GoBus FastAPI on port 8000 and PostGIS on port 5432.
* **Phase 4 (Mission Control Dashboard):** Zero-dependency `ThreadingHTTPServer` binding to `127.0.0.1:8080`, thread-safe `SimulationController`, safe state projection (`GET /api/status`), reset confirmation safety, and dark transit HUD.

**Invariant:** All Phase 1–4 modules remain the core runtime engine. Phase 5 builds strictly on top of these abstractions.

---

## 3. GoBus Network & Database Inventory Audit

A direct audit of the active GoBus database and models reveals the exact operational assets available:

### A. Organizations
| Organization ID | Name | Type | Status | Timezone Model |
|---|---|---|---|---|
| `10000000-0000-0000-0000-000000000001` | Transit Demo Authority | Government | ACTIVE | UTC in DB; IST (+05:30) local ops |
| `8ff4c19f-fbdb-5815-bd6d-746203b3865c` | Kolkata Transit Authority | Municipal | ACTIVE | UTC in DB; IST (+05:30) local ops |

### B. Fleet Inventory (Vehicles)
Total vehicles in database: **4** (all assigned to active status).
| Vehicle ID | Registration | Vehicle Number | Type | Status | Organization |
|---|---|---|---|---|---|
| `50000000-0000-0000-0000-000000000001` | PB01AB1234 | PNB005234 | BUS | ACTIVE | Transit Demo Authority |
| `50000000-0000-0000-0000-000000000002` | PB01CD5678 | PNB005781 | BUS | ACTIVE | Transit Demo Authority |
| `50000000-0000-0000-0000-000000000003` | PB01EF9012 | PNB006421 | MINI_BUS | ACTIVE | Transit Demo Authority |
| `8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e` | WB04-DEMO | WB04-DEMO-001 | AC_BUS | ACTIVE | Kolkata Transit Authority |

*Note on Capacity:* Vehicle physical passenger capacities are not stored in the `vehicles` table, but `InsightsService` defines logical capacity tiers based on `vehicle_type` (`MINI_BUS` = LOWER_CAPACITY; `BUS` / `AC_BUS` / `DOUBLE_DECKER` = HIGHER_CAPACITY).

### C. Services & Schedules
Total services: **3** across the two organizations.
| Service ID | Code | Name | Route ID | Direction Schedules |
|---|---|---|---|---|
| `40000000-0000-0000-0000-000000000001` | AC4B | AC4B City Center Express | `20000000...0001` (R1) | 1 schedule (`A_TO_B`, 00:00–23:59, 15m interval, Mon–Sat) |
| `40000000-0000-0000-0000-000000000002` | SD5 | SD5 Airport Shuttle | `20000000...0002` (R2) | 0 schedules (inactive demo service) |
| `1fc2351a-2902-570c-a664-632414aa46ac` | SD5 | SD5 Standard Non-AC | `fefc79a0...3c6c` (SD5) | 2 schedules (`A_TO_B` & `B_TO_A`, 05:00–20:30, 30m interval, 7 days/week) |

### D. Route Topologies
| Route Code | Route Name | Stops Count | Distance | Coordinates / Geometry |
|---|---|---|---|---|
| **SD5** | Sonarpur Station Terminus to Kharibaria Terminus | **40 stops** | **29.45 km** | High-precision Linestring GeoJSON + 40 sequenced stops |
| **R1** | City Center to Tech Park | **4 stops** | **5.20 km** | 4 sequenced stops |
| **R2** | Airport to Railway Station | **4 stops** | **4.80 km** | 4 sequenced stops |
| Other 198 Routes | Kolkata transit network routes (1, 1A, 3B, etc.) | 0 stops | None | Metadata only; stops unseeded |

### E. Operator Identities in Database
Total users with `DRIVER` or `CONDUCTOR` role: **3**.
| User ID | Name | Role | Employee Code | Status | Verification |
|---|---|---|---|---|---|
| `60000000-0000-0000-0000-000000000001` | Demo Driver | DRIVER | `DRV001` | ACTIVE | VERIFIED |
| `60000000-0000-0000-0000-000000000002` | Demo Conductor | CONDUCTOR | `CND001` | ACTIVE | VERIFIED |
| `ff68477b-d0ee-4ccb-8f14-17348f31411c` | Demo Operator 1 | DRIVER | `O-001` | ACTIVE | VERIFIED |

**Critical Observation:** There are currently only **2 verified DRIVER accounts** in the entire system (`DRV001` and `O-001`).

---

## 4. API Coverage & Operational Gaps Audit

We audited all external HTTP API routes to determine whether an external simulator can discover and drive a full service day exclusively through HTTP:

| Transit Domain | Available External HTTP Endpoints | Capability / Scope | Missing API Capabilities |
|---|---|---|---|
| **Organization** | `GET /api/passenger/organizations` | Public list of active organizations | No endpoint for operating hours or org timezone |
| **Fleet / Vehicles** | `GET /api/admin/fleet/vehicles`<br>`POST /api/admin/fleet/vehicles`<br>`PUT /api/admin/fleet/vehicles/{id}` | Full CRUD for Admin; includes registration, type, status | **No public endpoint** for vehicles; passenger API only sees vehicles currently in `BusCurrentState` |
| **Services & Routes** | `GET /api/passenger/services`<br>`GET /api/passenger/services/{id}`<br>`GET /api/passenger/services/{id}/route` | Public discovery of all services, route metadata, ordered stops, and GeoJSON geometries | None. Service and Route discovery is **100% complete and public**. |
| **Schedules** | `GET /api/passenger/services/{id}` (nested schedules)<br>`GET /api/admin/network/{id}/schedules`<br>`GET /api/admin/fleet/depot-schedules` | Service headways (e.g. 30m) and planned vehicle depot dispatch times | **No endpoint lists pre-generated scheduled trips** for a service day |
| **Trips** | `POST /api/trips/{id}/start`<br>`POST /api/trips/{id}/end` | Operator start and end tracking session | **CRITICAL GAP:** **Zero endpoints exist to create a Trip row** (`POST /api/trips` does NOT exist in GoBus) |
| **Operator Assignment** | `GET /api/operator/me/assignment` | Operator retrieves current assigned trip and vehicle | **CRITICAL GAP:** **Zero endpoints exist to assign an operator to a trip** (`POST /api/admin/assignments` does NOT exist) |
| **Operator Accounts** | `GET /api/admin/users/`<br>`POST /api/admin/users/` | Admin can create new users with `role: DRIVER` and `OperatorProfile` | Operator credentials must be manually tracked by the simulator |
| **Live Tracking** | `POST /api/tracking/batch`<br>`POST /api/tracking/heartbeat`<br>`POST /api/crowding/reports` | Full telemetry and crowding ingestion | 100% complete |
| **Live Operations HUD** | `GET /api/admin/live/operations/live` | Admin sees real-time vehicle positions, speed, stop progress, dwell, and confidence | 100% complete |

---

## 5. The Operator Identity & Assignment Constraint

### The Architectural Invariant
1. **One Operator = One Simultaneous Vehicle:** GoBus strictly enforces this constraint:
   - `TrackingSession.operator_id == user.id`
   - `get_active_session_for_operator` verifies that only one non-ended `TrackingSession` can exist for an operator.
   - Any attempt by the same operator to start a second simultaneous trip results in session conflict or overwrites.
2. **Maximum Simultaneous Fleet Size:**
   - Because the database currently contains only **2 verified driver accounts** (`O-001` and `DRV001`), the maximum simultaneous fleet size that can be simulated right now without creating accounts is **2 buses**.
   - If admin API `POST /api/admin/users/` is used to provision new driver accounts, the maximum simultaneous fleet is bounded by the number of vehicles (**4 vehicles** in the current database).

### Sequential Trips vs. Reassignment Gaps
Can one operator execute sequential trips throughout a simulated day?
* **Database Model Support:** `TripAssignment` represents *trip-level participation*, not permanent vehicle staffing. An operator can have multiple sequential rows in `trip_assignments` with distinct `assigned_at` timestamps.
* **Assignment Resolution Logic:** `get_operator_assignment` orders by `TripAssignment.assigned_at.desc()` and filters for `status.in_([ASSIGNED, ACTIVE])`.
* **The "Trip End" Trap:** When an operator calls `POST /api/trips/{trip_id}/end`, `end_trip_tracking` sets the `TrackingSession.status = ENDED`. **Crucially, it does NOT alter `TripAssignment.status`!** The assignment remains in `ACTIVE` status in the database.
* **The Reassignment Defect:** Because the previous assignment remains `ACTIVE`, a subsequent call to `GET /api/operator/me/assignment` will continue returning the *old* trip unless:
  1. A new assignment exists with a strictly newer `assigned_at` timestamp, OR
  2. The previous assignment status is transitioned to `UNASSIGNED` or `COMPLETED`.
* **No External Assignment API:** Because there is no HTTP API to create `Trip` or `TripAssignment` records, **the simulator cannot dynamically assign trips via HTTP during the day**.
* **Authoritative Conclusion:** A full-day simulation with multiple sequential trips per bus requires that **all trips and trip assignments for the service day be pre-generated in the database** (via seed script or administrative migration) prior to launching the simulation run.

---

## 6. Service-Day Operational Schedule Model

Based on the actual `ServiceSchedule` data discovered for Route **SD5** (`05:00:00` to `20:30:00`, 30-minute typical interval, 7 days/week), we model the real GoBus service day:

### Real Service Day Timeline (Route SD5 & AC4B)
* **05:00–06:00: Pre-Service & Depot Dispatch**
  - First vehicles depart depot; initialize operator logins and verify assignments.
* **06:00–09:30: Morning Peak Service**
  - Full vehicle deployment; tight 30-minute staggered headways; high passenger demand; crowding reports elevate to `HIGH`/`FULL`.
* **09:30–16:00: Midday Off-Peak Service**
  - Regular cadence; intermediate terminus layovers (15–20 minutes); passenger crowding drops to `SEATS_AVAILABLE`/`STANDING_ROOM`.
* **16:00–19:30: Evening Peak Service**
  - Second high-demand window; minor traffic slowdowns simulated on corridor bottlenecks; crowding reports elevate.
* **19:30–20:30: Late Evening Service**
  - Final trips for the day; low crowding; buses complete final terminal arrivals.
* **20:30+: End-of-Day Shutdown**
  - Final trips call `POST /api/trips/{trip_id}/end`; tracking sessions close cleanly; operators log out.

### Vehicle Duty Abstraction
To simulate realistic transit operations where a single bus performs sequential trips back-and-forth along a corridor:

$$\text{ServiceDay} \longrightarrow \text{VehicleDuty} \longrightarrow [ \text{Trip}_1 \xrightarrow{\text{Layover}} \text{Trip}_2 \xrightarrow{\text{Layover}} \dots \xrightarrow{\text{Layover}} \text{Trip}_N ]$$

Example Duty Cycle for Bus 1 (Vehicle `WB04-DEMO-001`, Driver `O-001`):
1. **Trip 1 (A_TO_B):** Sonarpur $\rightarrow$ Kharibaria (29.45 km)
   - Planned Start: `05:30` | Planned End: `06:35`
2. **Terminus Layover 1:** Kharibaria Terminus (15 minutes idle / dwelling)
   - Time: `06:35` to `06:50`
3. **Trip 2 (B_TO_A):** Kharibaria $\rightarrow$ Sonarpur (29.45 km, reversed stop sequence)
   - Planned Start: `06:50` | Planned End: `07:55`
4. **Terminus Layover 2:** Sonarpur Station Terminus (20 minutes)
   - Time: `07:55` to `08:15`
5. *(Repeats across morning peak, midday, and evening peak until 20:30)*

*Deadheading Rule:* Because GoBus has no depot-to-terminus route geometry or deadhead tracking API, vehicles must begin and end their operational trips strictly at designated route terminus stops.

---

## 7. Timestamp & Simulation Clock Constraints

### The Backend Timestamp Sanity Guard
A critical architectural constraint was uncovered during this audit in `backend/app/intelligence/gps_validation.py` and `backend/app/intelligence/config.py`:

```python
# From app/intelligence/config.py
ALLOWED_CLOCK_SKEW_SECONDS = 5.0
HISTORICAL_CLASSIFICATION_HORIZON_SECONDS = 900.0  # 15 minutes
MAX_IMPOSSIBLE_SPEED_MPS = 50.0                    # 180 km/h

# From GPSValidator.validate_packet()
time_diff = (packet.observed_at - current_time).total_seconds()
if time_diff > ALLOWED_CLOCK_SKEW_SECONDS:
    diagnostics.append(ValidationDiagnostic.FUTURE_TIMESTAMP)
    return ValidationReport(ValidationStatus.REJECTED, None, is_historical, diagnostics)
```

Where `current_time = event.received_at = datetime.now(timezone.utc)`.

### Implications for Simulation Acceleration
1. **Future Timestamps are REJECTED:** If a simulator tries to accelerate time by generating `observed_at` timestamps that run ahead of the server's real wall-clock time by more than **5.0 seconds**, the GoBus backend **instantly rejects the telemetry with `FUTURE_TIMESTAMP`**!
2. **Implied Speed Thresholds:** The backend calculates speed between successive observations:
   $$\text{implied\_speed} = \frac{\Delta \text{distance}}{\Delta t}$$
   If a simulator jumps a bus 600 meters in 1 wall-clock second to represent $60\times$ speed, $\text{implied\_speed} = 600\text{ m/s} > 50\text{ m/s}$, causing the packet to be rejected as `IMPOSSIBLE_SPEED`!
3. **Historical Timestamps:** If `time_diff < -900` seconds (more than 15 minutes in the past), the backend marks the packet as `is_historical = True` and penalizes tracking confidence.

### The Authoritative Timestamp Strategy for Full-Day Simulation
To ensure 100% acceptance by the real GoBus backend without modifying product code, the simulator must operate under one of two approved modes:

* **Mode A — Real-Time Operational Day (1.0x Multiplier):**
  - Simulator runs concurrently with wall-clock time (e.g. starting at 06:00 AM wall-clock).
  - All `observed_at` timestamps match `datetime.now(timezone.utc)`.
  - Packets are emitted at standard 1.0s–5.0s intervals.
  - Zero clock skew; zero speed rejections.
  - *Best for long-duration background reliability testing.*
* **Mode B — Accelerated Real-Time Service Day (Condensed Day, e.g. 5x–10x):**
  - In accelerated mode, the simulator **must NOT fabricate future timestamps**.
  - Instead, the simulator maintains `observed_at = datetime.now(timezone.utc)` (current server time), but adjusts physical route advancement and dispatch timelines into a condensed demonstration window (e.g. a 15-hour service day compressed into 2 hours of real-time execution).
  - Cruise speeds must remain bounded under $33\text{ m/s}$ ($120\text{ km/h}$) to prevent triggering `IMPOSSIBLE_SPEED` or `HIGH_SPEED` penalties in the intelligence engine.

---

## 8. Real Alert & Insight Accumulation Audit

A crucial question for Phase 5 is: *Does a full-day simulation naturally trigger GoBus alerts and insights?*

We audited the exact mathematical evaluation criteria in `AlertEngine` (`backend/app/services/alert_engine.py`) and `InsightsService` (`backend/app/services/insights_service.py`):

### AlertEngine Evaluation Rules (Live Alerts)
| Alert Type | Evaluation Logic | Threshold / Lookback Window | Can Full-Day Simulator Trigger Naturally? |
|---|---|---|:---:|
| `VEHICLE_TRACKING_STALE` | `BusCurrentState.last_observed_at < now - 2m` | 2 minutes of telemetry silence | **YES** (by simulating bus offline/stale period) |
| `LOW_TRACKING_CONFIDENCE` | `BusCurrentState.confidence == Confidence.LOW` | GPS jitter, high speed, or poor route match | **YES** (by injecting GPS inaccuracy or high speed) |
| `UNEXPECTED_MAINTENANCE` | `Vehicle.status == MAINTENANCE` & `DepotSchedule.date == today` | Checked against today's depot schedules | **YES** (if vehicle status toggled during scheduled day) |
| `VEHICLE_OFFLINE_SCHEDULED`| `DepotSchedule.date == today` & no telemetry for $>15$m | 15 minutes offline while scheduled | **YES** (by withholding dispatch of a scheduled bus) |
| `SERVICE_CROWDING_PATTERN`| $\ge 4$ reports in same 2-hour window over past 7 days with $>60\%$ `HIGH`/`FULL` | 7-day lookback, $\ge 4$ reports, $>60\%$ ratio | **YES** (if $\ge 4$ crowding reports submitted in peak window) |

### InsightsService Evaluation Rules (Strategic Insights)
| Insight Type | Evaluation Logic | Threshold / Lookback Window | Can Full-Day Simulator Trigger Naturally? |
|---|---|---|:---:|
| `CROWDING` | Service-level crowding reports grouped by hour of `observed_at` | $\ge 5$ reports on service; $>60\%$ `HIGH`/`FULL` over 30 days | **YES** (if $\ge 5$ crowding reports submitted on service) |
| `PERFORMANCE` (Departure Delays) | Trips where `actual_start_at > planned_start_at + 10m` | $\ge 5$ completed trips on service; $>40\%$ delayed over 30 days | **CONDITIONAL** (Requires $\ge 5$ completed trips in day) |
| `MISSED_TRIPS` | Trips with status `CANCELLED` or `ABANDONED` | $\ge 10$ trips on service; $>20\%$ missed over 30 days | **NO** (Unless $\ge 10$ trips pre-seeded and failed) |
| `CAPACITY` | Chronic crowding on lower-capacity vehicle types (`MINI_BUS`) | $\ge 5$ crowding reports on service with MINI_BUS | **YES** (if MINI_BUS vehicle assigned to crowded service) |

**Key Finding:** `AlertEngine` will fire real-time alerts within **2 to 15 minutes** of simulated anomalies. `InsightsService` requires **at least 5 completed trips** or **at least 5 crowding reports** to pass statistical significance thresholds.

---

## 9. Full-Fleet Scale & Concurrency Analysis

### Practical Scale Metrics (Real Database Entities)
* **Total Fleet Size:** 4 vehicles
* **Available Verified Drivers:** 2 drivers (expandable to 4 if accounts provisioned)
* **Active Services:** 2 services (SD5 and AC4B)
* **Maximum Simultaneous Active Buses:** **2 buses** (current credentials) / **4 buses** (with 2 additional driver accounts)
* **Service Day Duration:** 15.5 hours (`05:00` to `20:30` IST)
* **Trips per Vehicle per Day:** ~10 sequential trips (5 outbound A_TO_B, 5 inbound B_TO_A)
* **Total Daily Trips:** ~20–40 trips across the fleet

### Telemetry Packet Volume & Bandwidth
* **Packet Ingestion Rate:** 1 packet every 1.0s per active bus.
* **Peak Simultaneous Generation:** 4 packets/second (with 4 buses active).
* **Batching Strategy:** 5 packets batched every 5.0 seconds per bus.
* **HTTP Request Rate:** 4 HTTP requests every 5 seconds = **0.8 requests/second**.
* **Daily Telemetry Total:**
  $$4 \text{ buses} \times 15.5 \text{ hours} \times 3600 \text{ s/hr} = 223,200 \text{ telemetry events/day}$$
* **PostgreSQL Storage Impact:** ~223k rows in `tracking_events` $\approx 35 \text{ MB}$ of table data. Easily handled by PostgreSQL on standard development hardware.

### Concurrency Architecture: Central Scheduler vs. Per-Bus Workers
* **Benchmark Evaluation:**
  - *Per-Bus Threading:* Spawning 4 to 10 independent threads with blocking HTTP calls creates thread contention, uncoordinated clock drift, and non-deterministic event sequencing.
  - *Deterministic Central Scheduler:* Single master worker thread running a high-precision tick loop ($1.0\text{s}$ tick). Advances all active bus kinematic states in memory, collects telemetry batches, and dispatches HTTP requests via a bounded thread pool or asynchronous executor.
* **Verdict:** The **Central Scheduler** pattern (proven in Phase 3) must be retained and scaled. It guarantees deterministic replay, unified clock synchronization, and controlled resource consumption.

---

## 10. Proposed Phase 5 Architecture

```
                               ┌────────────────────────┐
                               │  Phase 5 Service-Day   │
                               │      Orchestrator      │
                               └───────────┬────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
       ┌────────────────────────┐                    ┌────────────────────────┐
       │   Duty Plan Manager    │                    │    ServiceDay Clock    │
       │ (Sequential Trip Table)│                    │ (Timezone, Multiplier) │
       └────────────┬───────────┘                    └────────────┬───────────┘
                    │                                             │
                    └──────────────────────┬──────────────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │ Central Tick Scheduler │
                               │  (Deterministic Event  │
                               │   Dispatch & Sensors)  │
                               └───────────┬────────────┘
                                           │
             ┌─────────────────────────────┼─────────────────────────────┐
             ▼                             ▼                             ▼
   ┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
   │ Virtual Operator  │         │ Virtual Operator  │         │ Virtual Operator  │
   │ Bus 1 (O-001)     │         │ Bus 2 (DRV001)    │         │ Bus 3 (DRV002)    │
   │ [WB04-DEMO-001]   │         │ [PB01AB1234]      │         │ [PB01CD5678]      │
   └─────────┬─────────┘         └─────────┬─────────┘         └─────────┬─────────┘
             │                             │                             │
             └─────────────────────────────┼─────────────────────────────┘
                                           │ HTTP Adapters
                                           ▼
                               ┌────────────────────────┐
                               │   GoBus Real Backend   │
                               │    (FastAPI :8000)     │
                               └────────────────────────┘
```

### Core Proposed Modules (To Be Implemented in Phase 5)

1. **`DutyPlan` & `ServiceDayPlan` (`simulator/core/duty_plan.py`):**
   - Represents the complete operational day: list of vehicle duties, sequence of planned trips, departure times, directions, terminus layover windows, and assigned operator codes.
2. **`ServiceDayClock` (`simulator/core/service_day_clock.py`):**
   - Tracks simulated date, time-of-day in IST, time-multiplier, pause/resume, and real wall-clock elapsed time. Enforces that `observed_at` timestamps sent to backend never violate the 5-second future clock skew rule.
3. **`FleetDutyOrchestrator` (`simulator/core/duty_orchestrator.py`):**
   - Monitors the `ServiceDayClock`. Automatically triggers trip start at planned departure, drives route progression, triggers dwell at stops, triggers terminus layovers, ends trips on arrival, logs out operators, and transitions vehicles to their next sequential trip.
4. **`ServiceDayMissionControl` Extension (`simulator/server/`):**
   - Extends the Phase 4 dashboard with a dedicated Service-Day HUD:
     - Digital Service-Day Clock (e.g. `08:42:15 IST`, `Progress: 31%`)
     - Fleet Duty Matrix (showing sequential trips per bus, completed vs remaining)
     - Real-time Alert Accumulator (showing active backend alerts triggered by simulation)
     - Replay & Reset safety controls.

---

## 11. Full-Fleet Reset & Failure Recovery Design

### Reset Procedure (Safe Backend Cleanup)
Resetting a full-day simulation involving multiple sequential trips must leave both the simulator and backend in a pristine state:
1. **Simulator Shutdown:** Signal worker thread to stop; pause all internal clocks.
2. **Active Session Cleanup:** Iterate through all buses in `FleetManager`. For any bus in `RUNNING` or `PAUSED` state, issue `POST /api/trips/{trip_id}/end` to cleanly close backend tracking sessions.
3. **Operator Logout:** Issue `POST /api/auth/operator/logout` for all authenticated operators to invalidate active JWT tokens.
4. **Local State Purge:** Clear duty queues, event logs, and kinematic trackers. Reset clock to `00:00:00`.
5. **Database Trip State:** Any planned trips that were executed are marked completed on the backend; the simulator does NOT manually alter PostgreSQL rows.

### Failure Recovery & Resilience
* **Network / HTTP Disconnect:** If the backend becomes temporarily unreachable, individual buses buffer up to 100 packets in local memory and retry with exponential backoff rather than crashing the orchestrator.
* **Operator Login Failure:** If an operator credential fails authentication, that specific bus duty is marked `FAILED_AUTH` and withheld, allowing remaining buses to continue their service day.
* **Trip Start Rejection:** If a trip start returns HTTP 400 (e.g. status conflict), the orchestrator logs the error, skips the affected trip, and waits for the next scheduled duty cycle.
* **Isolated Crash Domain:** An exception in one bus movement engine is captured and reported in the event log without terminating other active buses.

---

## 12. Full-Day Replay & Determinism

To guarantee reproducible demonstrations for evaluators and automated benchmarks:
* **Deterministic Seeds:** Random Gaussian GPS noise and passenger crowding fluctuations must be keyed to `(bus_id, trip_id, stop_index, random_seed)`.
* **Reproducible Day Run:** Given the same `service_day_date`, `fleet_config.json`, and `random_seed`, the simulator will execute the identical timeline of speeds, stop dwell times, and packet sequences.
* **Separation of Concerns:**
  - *Simulator-Deterministic:* Packet coordinates, timestamps, heading, speed, stop dwell duration, crowding states.
  - *Backend-Dynamic:* Database row IDs, tracking session UUIDs, Map-matching candidate scores, ETA inference output.

---

## 13. Exact Limitations & Architectural Blockers

The following explicit constraints and limitations must be formally recorded:

1. **BLOCKER 1: No HTTP API for Trip Generation or Assignment.**
   - *Impact:* The simulator cannot dynamically generate new trips or change operator duty assignments via HTTP APIs during the simulation day.
   - *Resolution:* All trips and assignments for the simulated service day must be pre-seeded in the database (or created prior to running the simulator).
2. **BLOCKER 2: Driver Account Scarcity.**
   - *Impact:* Only 2 driver accounts (`O-001` and `DRV001`) currently exist in the database. Simultaneous fleet size is strictly capped at 2 buses unless additional driver accounts are created via `POST /api/admin/users/` or database seeding.
3. **BLOCKER 3: Clock Skew Constraint (`ALLOWED_CLOCK_SKEW_SECONDS = 5.0`).**
   - *Impact:* Telemetry cannot be timestamped into the future. High simulation multipliers ($60\times$) cannot jump timestamps ahead of server wall-clock time without backend rejection.
   - *Resolution:* Multipliers must be achieved via condensed physical duty timelines or real-time simulation runs.
4. **BLOCKER 4: Terminus Layover vs. Deadheading.**
   - *Impact:* GoBus has no deadhead routing engine. Vehicles cannot deadhead between disparate depots and terminus stops; sequential trips must begin where the previous trip ended.

---

## 14. Phase 5 Implementation Breakdown (Proposed Work Packages)

Upon review and approval of this audit, Phase 5 implementation should proceed in four structured sub-phases:

* **Phase 5.1 — Service Day Schedule Pre-Seeder & Duty Plan Model:**
  - Build `ServiceDayPlan` parser and pre-seed script for full-day SD5 & AC4B trips.
  - Provision 2 additional driver accounts (`DRV002`, `DRV003`) to enable full 4-bus concurrency.
* **Phase 5.2 — Sequential Vehicle Duty Engine & Service-Day Clock:**
  - Implement `ServiceDayClock` with strict skew guard.
  - Implement sequential trip transitions (Trip A $\rightarrow$ Terminus Layover $\rightarrow$ Trip B).
* **Phase 5.3 — Full-Day Scenario Timeline (Peaks, Lulls, Delays, Crowding):**
  - Model morning peak (06:00–09:00), midday lull, evening peak (16:00–19:00).
  - Verify `AlertEngine` and `InsightsService` statistical thresholds.
* **Phase 5.4 — Mission Control Service-Day Dashboard & Live E2E Verification:**
  - Extend Mission Control with Service-Day HUD, Duty Matrix, and Alert feed.
  - Execute complete multi-hour service day test against real GoBus backend.

---

## 15. Repository & Product Code Integrity Confirmation

* **Zero modifications** were made to `backend/`, `apps/`, `migrations/`, or Build 3 during this audit.
* **Zero modifications** were made to the existing Phase 1–4 simulator codebase.
* All 96 unit tests continue to pass with 100% OK status.
* Build 3 remains 100% frozen.

---

**AUDIT COMPLETE — AWAITING REVIEW & APPROVAL BEFORE COMMENCING PHASE 5 IMPLEMENTATION.**
