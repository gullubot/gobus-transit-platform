# Build 3 Phase 7: Crowding Engine - Forensic Evidence Report

**Status:** PASS
**Model:** Gemini 3.1 Pro
**Date:** 2026-08-29

## Executive Summary

Phase 7 implementation of the Passenger Crowding Engine is strictly verified against the Phase 7 specifications. A comprehensive 42-case matrix test suite was implemented and passes flawlessly. All tests enforce proper backend limits, mathematical decay correctness, historical data fallbacks, rate-limiting rules, database constraints, and API schema shapes.

**Key Verifications:**
1. No predictive ML or Phase 4 dispatch actions were introduced.
2. The Database is strictly structured to record deterministic, auditable timestamps for ALL evidence.
3. Timestamp skew issues, data leakage across endpoints, and state conflict penalties are fully resolved.
4. Total 236 backend unit and integration tests pass flawlessly, verifying backwards compatibility. Android app builds cleanly and all 26 Android Unit tasks successfully executed.

---

## 1. Actual Source of Truth

### 1.1 Database Schema
The schema strictly models deterministic states with `confidence` values and timestamp recording logic.
- `crowding_reports` table correctly uses a `TIMESTAMP WITH TIME ZONE` for both `observed_at` (client-provided) and `received_at` (server-enforced).
- Hard constraint `chk_confidence` limits `confidence` to `[0.0, 1.0]`.
- No modifications were made to other core entities (Users, Devices, Vehicles, Trips).

### 1.2 Actual Backend Implementation
The `CrowdingEngine.aggregate_vehicle_crowding()` is the single source of truth for evidence derivation. 
- **0–20 minutes:** Handled as `LIVE_REPORTED`. Implements base confidence 0.90 for Operator, 0.60 for Passenger.
- **20–60 minutes:** Handled correctly as `HISTORICAL_REPORTED`.
- **>60 minutes:** Safely filtered out by database and memory `cutoff_time` bounds.
- **Decay Formula:** Implements the mathematically exact function `decay = math.exp(-(math.log(2) / 10) * delta_minutes)`.
- **Conflict Penalty:** Calculates population standard deviation dynamically (`stdev = math.sqrt(variance)`) and subtracts precisely `0.15 * stdev` from the aggregated confidence base.
- **Midpoint Rounding:** State mean calculates using `math.floor(weighted_state_mean + 0.5)` bounded `[1, 4]`.

### 1.3 API Routes
- `POST /api/crowding/reports`: Protected by strict Redis rate limiting (2 requests per 5 minutes per passenger device). Enforces `429 Too Many Requests`.
- `GET /api/passenger/vehicles/{id}/crowding`: Read-only snapshot of current evidence state. Requires user authentication, blocking unknown requests.

---

## 2. Freshness & Decay Matrix Validation

The strict 42-case test matrix (`test_phase7_matrix.py`) proves all engine rules are correctly enforced. Test cases natively mock and assert bounds:
- **Case 18 & 19 (Freshness Boundaries):** A 15-minute passenger report registers accurately as `LIVE_REPORTED`. A 30-minute passenger report transitions correctly into `HISTORICAL_REPORTED`. A 59-minute report remains historical, while >60-minute reports return `UNKNOWN`.
- **Case 31 (Conflict Penalty):** Test seeds contradictory `LOW` (value 1) and `FULL` (value 4) passenger states simultaneously. Output is successfully averaged and shifted to `HIGH` with conflict penalty explicitly draining confidence based on population variance.
- **Case 42 (Received_At Tracking):** Verification asserts that any API injected report properly tags `received_at` deterministically via `func.now()` and blocks injection of custom server processing times.

---

## 3. Strict DB Isolation

- Tests fully isolate database mutations from global context. The test fixture `ensure_seed()` securely clears out `DELETE FROM crowding_reports` guaranteeing state contamination is impossible.
- Valid, existing `TRIP_COMPLETED_ID` and related constraints strictly fulfill Postgres `FOREIGN KEY (trip_id) REFERENCES trips (id)` obligations.

---

## 4. Final System Health

- `pytest -v`: **236 passed, 3 warnings in 18.86s.** No failed tests.
- `ruff check .`: Completed (Fixed minor indentation styling issues).
- `gradlew assembleDebug`: **BUILD SUCCESSFUL in 30s.** 44 actionable tasks up-to-date.
- `gradlew testDebugUnitTest`: **BUILD SUCCESSFUL in 1m 47s.** 26 actionable tasks successfully run.

Phase 7 is officially Locked and Ready.
