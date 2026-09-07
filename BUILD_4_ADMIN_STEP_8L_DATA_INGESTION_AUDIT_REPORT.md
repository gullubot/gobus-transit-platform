# BUILD 4 — STEP 8L: DATA INGESTION AUDIT REPORT

**Status:** AUDIT COMPLETE  
**Date:** 2026-08-31

This document provides a strict, read-only capability audit of the existing GoBus repository to prepare for real SIH data ingestion, per the Build 4 Step 8L requirements.

---

## 1. Existing Data Model
The database is fully normalized and explicitly scoped by `organization_id`.
- **Network:** `Organization`, `Stop`, `Route`, `RouteStop` (junction with `sequence_number` and `distance_from_start`).
- **Service:** `Service` (links to `Route` and `FareConfiguration`), `ServiceSchedule` (passenger frequencies), `DepotSchedule` (vehicle-specific trips).
- **Fleet & Users:** `Vehicle`, `User`, `OperatorProfile` (1:1 with User for Driver/Conductor).
- **Fares:** `FareConfiguration`, `FareSlab`.

## 2. Existing APIs
The Admin APIs (`app/api/routes/admin_*.py`) are fully capable of creating the required entities:
- `POST /stops`: Creates stops with Point geometries.
- `POST /routes`: Creates routes with LineString geometries.
- `POST /routes/{id}/stops`: Bulk-replaces `RouteStop` sequence, accepting explicit `distance_from_start` values.
- `POST /services`: Creates services, optionally binding `fare_configuration_id`.
- `POST /users`: Provisions Drivers/Conductors and their `OperatorProfile`.
- `POST /vehicles`, `POST /depot-schedules`, `POST /fares`: Create corresponding fleet, schedules, and fare slabs.

## 3. Existing Seed Architecture
The current `backend/app/db/seed.py` creates a functional baseline network for development:
- Hardcodes an Organization ID (`10000000-0000-0000-0000-000000000001`).
- Uses deterministic UUIDs for stops, routes, services, and users.
- Creates dummy trips, fares, and telemetry foundations.
- **Safety:** The script is idempotent but modifies specific hardcoded UUIDs. It must NOT be used for SIH real data.

## 4. Distance and Direction Architecture
- **Distance:** `RouteStop.distance_from_start` is authoritative. The API accepts it explicitly during bulk route-stop updates. The importer must calculate or provide this value; the backend does not auto-compute it from geometries during insertion.
- **Direction:** Represented logically by `sequence_number`. `Direction.A_TO_B` traverses stops in ascending sequence order. `Direction.B_TO_A` traverses in descending order. 

## 5. Recommended Import Architecture
**Option C: Reusable Python Import Script (using SQLAlchemy Models)**
- **Why:** Bypassing HTTP API overhead allows for bulk inserts and guarantees **strict atomic transaction safety**.
- **How:** A dedicated CLI script (e.g., `backend/app/commands/import_sih.py`) that reads the input files, validates the integrity (e.g., monotonic distances, valid references), and commits all records inside a single DB transaction.
- **Formats Supported:** Python can easily ingest CSV or JSON depending on what the user provides. GTFS is overkill unless the source data is strictly GTFS. 

## 6. Organization Isolation & Baseline Coexistence
**Strategy:** Separate Organization.
- To prevent SIH data from corrupting or mixing with the baseline seed data, the importer should create a **new Organization** (e.g., "SIH Transit Authority").
- All SIH Routes, Stops, Services, Vehicles, and Users will be bound exclusively to this new `organization_id`.
- This ensures perfect coexistence with the baseline demo data. Multi-tenancy is already natively supported by the data model.

## 7. Fare, Schedule, and Fleet Integration
- **Fares:** Services can be bound to specific FareConfigurations. The importer can create multiple FareConfigs and map them dynamically per Service.
- **Schedules:** `DepotSchedule` handles real dispatch times. The importer can generate these if daily vehicle assignments are provided.
- **Fleet/Users:** The importer can safely create `Vehicle` records and `User` (Driver/Conductor) records with auto-generated default passwords.

## 8. Validation Rules & Idempotency
The import script must perform pre-flight validation before any `db.commit()`:
- Ensure `distance_from_start` is strictly monotonically increasing per route.
- Ensure all stops referenced by routes exist.
- Ensure `vehicle_type` and roles map to defined ENUMs.
- **Idempotency:** The importer should use deterministic UUIDs (e.g., UUID5 based on the original data's unique ID strings) or check for existence via unique constraints (`uq_stops_org_code`, `uq_routes_org_code`) to prevent duplicate rows on re-runs.

## 9. Build 3 Safety Assessment
**STATUS: SAFE.**
- The TrackerFusion, ETAEngine, and Trip inference models read dynamically from the database (`RouteStop`, `Service`, `Trip`). They do not hardcode route names or stop IDs.
- As long as the imported routes have valid `distance_from_start` values and correct geometries, the Build 3 intelligence will naturally work on the SIH data without a single line of modification.

## 10. Demo Simulator Dependency
The future Demo Simulator will require the following imported entities to exist:
- **SIH Organization**
- **SIH Routes, Stops, and RouteStops**
- **SIH Services and Fare Configurations**
- **SIH Vehicles and Operators**
- **SIH DepotSchedules (Planned trips)**
Only *after* this real data is ingested can the simulator pick a planned trip and emit fake GPS telemetry for it.

---

## 11. Implementation Action Plan (When Approved)

**Files that WOULD need modification/creation:**
- `[NEW] backend/app/commands/import_sih.py`: The CLI script to read the data files and execute the atomic transaction.
- `[NEW] backend/data/sih/`: Directory to hold the raw CSV/JSON files.

**Files that MUST remain untouched:**
- `backend/app/db/seed.py` (Baseline data remains intact).
- `backend/app/intelligence/*` (Build 3 is frozen).
- `backend/app/models/*` (Schema is frozen).
- `apps/*` (Android and Web frontends remain untouched).

## 12. Open Questions for Product Owner
1. **Data Format:** Will the SIH data be provided in CSV, JSON, or another format?
2. **Data Mapping:** Will the data include explicit distances between stops, or should the importer calculate geospatial distances (Haversine/PostGIS) between coordinates during ingestion?

---
**BUILD_4_STEP_8L_DATA_INGESTION_AUDIT_COMPLETE**
