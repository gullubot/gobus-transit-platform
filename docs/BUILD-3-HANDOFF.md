# BUILD-3-HANDOFF

A fresh Antigravity account/session must treat this file as the primary Build 3 state checkpoint. It must inspect the repository and Git state before making any changes. Conversation history is not authoritative if it conflicts with the repository.

Do not assume any uncommitted modification is disposable. Inspect `git diff` before changing or reverting anything.

## 1. PROJECT IDENTITY

- **Project / Repository Name**: Transit Pulse
- **Local Repository Path**: `d:\GoBus\Transit Pulse\transit-platform`
- **Current Branch**: `master`
- **Current HEAD Commit**: `5dfc27f` (fix(intelligence): resolve Decimal TypeErrors during cross-batch engine context deserialization)
- **Current Git Status**: Working tree contains uncommitted modified files and untracked files generated throughout Build 3 integration testing.

## 2. BUILD STATUS

**BUILD 3 = COMPLETE / FROZEN**

- **Phase 7 Status**: Fully implemented. ETA Engine executes correctly internally.
- **System Integration Status**: End-to-end intelligence pipeline is seamlessly integrated and verified via integration tests.
- **Cross-Batch Persistence Status**: Fully operational. Engine contexts (`trip_ctx`, `stop_ctx`, `dwell_ctx`, `dir_ctx`) survive between telemetry batches without data loss or type errors.
- **Android Integration Status**: Operator app telemetry integrates cleanly into the backend tracker endpoints.
- **Physical Prototype Validation Status**: Successfully executed and validated in actual physical movement tests.

## 3. BUILD 3 ARCHITECTURE

The verified runtime intelligence chain:

1. **Android Operator**: Captures high-frequency GPS observations.
2. **GPS/location provider**: Mock-location or hardware sensors output coordinates.
3. **Local Telemetry Queue**: Buffers and batches events.
4. **Tracking API**: Backend endpoint receives POSTed batch.
5. **GPS Validation**: Evaluates HDOP/accuracy against physical realities (incorporates previous state).
6. **Route Matching**: Geometrically snaps validated points to routes.
7. **Direction**: Evaluates segment vectors and enforces hysteresis anchors.
8. **Stop Progression**: Calculates segment progress and distance (engine meters vs DB kilometers).
9. **Dwell**: Assesses movement velocity for stop vs. non-stop dwell conditions.
10. **Trip Inference**: Evaluates alignment with seeded schedules to dictate `NOT_ACTIVE`, `ACTIVE`, or `COMPLETED`.
11. **Tracker Fusion**: Aggregates all engine inputs into the `CanonicalState`.
12. **Canonical State**: Persisted strictly into `bus_current_state` table via PostgreSQL row locks.
13. **ETA Engine**: Computes historical and real-time mathematically-bounded ETAs for downstream stops.
14. **Passenger API**: Disseminates strictly authorized fields to the passenger view.

*Note: Persistent Database State (e.g. `BusCurrentState.state`) is distinctly separated from Transient Engine State (e.g. `BusCurrentState.engine_contexts`). Engines use the latter for real-time calculations.*

## 4. IMPORTANT IMPLEMENTATION CHANGES

- **cross-batch engine context persistence**: `backend/app/intelligence/serialization.py`, `backend/app/intelligence/orchestrator.py`, `backend/app/models/state.py`. Serializes intermediate engine states into `engine_contexts` JSONB to allow continuous hysteresis and progress accumulation across independent HTTP batches.
- **DirectionEngine high-frequency anchor correction**: `backend/app/intelligence/direction.py`. Prevents sub-threshold high-frequency (1s) Android telemetry from resetting the hysteresis anchor prematurely.
- **GPS provider bootstrap/hysteresis behavior**: `backend/app/intelligence/orchestrator.py`. Properly accommodates device cold-start coordinate drops via bootstrap bypass.
- **GPSValidator previous-state integration**: `backend/app/intelligence/validation.py`. Integrates chronological awareness to reject physically impossible jumps.
- **Decimal/Numeric → float normalization**: `backend/app/intelligence/core_models.py`. Resolves JSON serialization crashes caused by strict typing of SQLAlchemy DB types when deserialized into Pydantic.
- **telemetry duplicate sequence handling**: `backend/app/intelligence/orchestrator.py`. Safely ignores repeated or heavily delayed `device_sequence` IDs without crashing the pipeline.
- **stop distance km → m normalization**: `backend/app/intelligence/stop_progression.py`. Translates route stop kilometers from the database to strict meters matching the core engine requirements.
- **StopProgression context persistence**: `backend/app/intelligence/stop_progression.py`. Preserves the `StopProgressResult` across batches for robust state-machine transitions.
- **localTest Android variant**: `apps/android/app/build.gradle.kts`. Injects `http://10.0.2.2:8000` via build configs for local emulator development.
- **staging Android variant**: `apps/android/app/build.gradle.kts`. Injects HTTPS domain routing for remote cloud deployments.
- **staging signing configuration**: `apps/android/app/build.gradle.kts`. Adds dynamic placeholder keys to facilitate CI/CD APK generation without exposing secrets.

## 5. DATABASE / MIGRATIONS

- **Current Alembic Head**: `128fd62846cc`
- **Introduced Migrations**: `128fd62846cc_add_engine_contexts_to_buscurrentstate.py`
- **Purpose**: Added the `engine_contexts` JSONB column to the `bus_current_state` table to securely persist serialized internal engine states across independent HTTP requests.
- **Current Schema Expectations**: Must comply strictly with "BUILD 1: Schema only" principles.
- **`bus_current_state.engine_contexts` Purpose**: Securely persists serialized internal states of `TripInferenceEngine`, `DirectionEngine`, `DwellEngine`, and `StopProgressionEngine` across isolated network requests without leaking them into the Passenger API.
- **Important Canonical Constraints**: `upsert_canonical_state()` drops fields missing from the DB model (e.g. ETA properties). 

**Explicitly state that no Build 4 schema has been introduced.**

## 6. TEST RESULTS

- **Total Backend Tests**: 260
- **Phase 7 Matrix Result**: PASS
- **Cross-Batch Tests**: PASS
- **GPS Validation Integration Tests**: PASS
- **Stop Progression Integration Tests**: PASS
- **Direction High-Frequency Tests**: PASS
- **Full Backend Regression**: PASS
- **Ruff (linting)**: PASS
- **Ruff Format**: PASS
- **Android Unit Tests**: PASS (`testDebugUnitTest` / `testLocalTestUnitTest`)
- **Android Build(s)**: PASS (`assembleLocalTest`, `assembleStaging`)

## 7. FINAL PHYSICAL TEST

The final physical validation was completed successfully under strict real-world simulation conditions:

- **localTest APK was used**.
- **Physical Android device was used** (tethered via ADB).
- **GPS Emulator/mock-location setup** was configured to playback route segments.
- **Route executed**: CC → MG → KP → TP.
- **Trip schedule was aligned** to the active test window.
- **trip reached ACTIVE**.
- **direction became A_TO_B**.
- **route matching succeeded**.
- **stop progression reached KP → TP**.
- **canonical state was LIVE**.
- **ETAEngine executed**.
- **passenger ETA remained null intentionally** because Build 3 does not persist/expose ETA in the passenger schema/API.

*Distinction: "ETA was calculated internally" by the intelligence tier, but NOT "exposed to passengers" via the API.*

## 8. KNOWN DESIGN BOUNDARIES

- Passenger visual UI is not yet implemented.
- Passenger ETA persistence/API exposure is intentionally deferred.
- Remote staging deployment has NOT occurred.
- VPS/domain/Caddy production deployment has NOT occurred.
- Build 4 has NOT started.
- Second-device logic has NOT been introduced.
- No speculative ML/dispatch work has been introduced.

## 9. CURRENT ANDROID VARIANTS

- **debug**: Base variant for standard development. `BASE_URL` generally targets `10.0.2.2:8000`.
- **localTest**: Specifically designed for physical device tethered testing. `BASE_URL` targets `http://192.168.x.x:8000` (the developer's local machine IP). **This variant is used for local physical testing** to bypass strict localhost network constraints on actual hardware.
- **staging**: Designed for remote cloud QA. `BASE_URL` targets `https://staging.api.transitpulse.net`.
- **release**: Intended for production compilation.

## 10. CURRENT DEVELOPMENT TEST PROCEDURE

1. **PostgreSQL/Docker**: Start the database layer: `docker-compose up -d db`.
2. **Backend startup**: Start the local FastAPI server: `.venv\Scripts\uvicorn app.main:app --reload`.
3. **ADB device check**: Ensure the physical device is recognized: `adb devices`.
4. **adb reverse**: Bind ports (if necessary for 127.0.0.1 proxies): `adb reverse tcp:8000 tcp:8000`.
5. **localTest APK build/install**: Compile and push the binary: `.\gradlew.bat installLocalTest`.
6. **Android mock-location setting**: Enable "Developer Options" -> "Select mock location app" -> "GPS Emulator".
7. **GPS Emulator**: Open the app, search/pin the starting location (CC).
8. **trip preparation**: Use DB scripts or admin endpoints to ensure the `planned_start_at` aligns with the current wall-clock test window.
9. **tracking startup**: Launch the Transit Pulse Operator app, confirm the route/trip, and initiate tracking.
10. **GPS bootstrap window**: Allow the device a few seconds of stationary pinging to lock the validation window.
11. **route playback**: Initiate playback in GPS Emulator.
12. **passenger API checks**: Periodically query `/api/passenger/vehicles/{id}` to verify `LIVE` state and stop progressions.
13. **test completion**: Halt playback, stop tracking in the operator app, and review the final backend DB state.

## 11. CURRENT LIMITATIONS

No remaining intelligence or core tracking logic defects exist. Constraints are purely boundary-related (e.g. API exposure) as dictated by the Build 3 spec.

## 12. NEXT STEP

BUILD 3 IS FROZEN. The next engineering activity is Build 4 planning, not further Build 3 modification, unless a newly discovered reproducible Build 3 defect is demonstrated.

## 13. ACCOUNT SWITCH HANDOFF

A fresh Antigravity account/session must treat this file as the primary Build 3 state checkpoint. It must inspect the repository and Git state before making any changes. Conversation history is not authoritative if it conflicts with the repository.

Do not assume any uncommitted modification is disposable. Inspect `git diff` before changing or reverting anything.
