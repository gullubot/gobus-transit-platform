# BUILD 3 PHASE 3: STOP PROGRESSION AND DWELL DETECTION

## Overview
Phase 3 implements the `stop_progression.py` and `dwell_detection.py` intelligence modules. It accurately models a bus's progression through canonical route stops using deterministic, physical distance comparisons, multi-stop gap handling, stateful hysteresis, and Dwell-state transition mapping. 

It is designed to strictly run as a pure logic evaluation, disconnected from REST APIs and database mutations.

## 1. Stop Progression (`stop_progression.py`)
- **Route-Progress Semantics:** Relies purely on mapping canonical structural line distances against dynamic route progress. In `A_TO_B`, progression increases. In `B_TO_A`, progression explicitly decreases while checking against the canonical `distance_from_start`.
- **Adaptive Tolerance:** Scales tolerance between 30m and 100m linearly off GPS accuracy.
- **Hysteresis Bands:** Defines `ENTER_AT`, `EXIT_AT`, and `PASSED` thresholds explicitly to prevent jitter.
- **BEFORE_STOP:** Requires vehicle position to structurally precede the stop bounds given directional context.
- **AT_STOP:** Requires spatial proximity / trajectory evidence alongside strict progress bounds. Low-speed alone cannot fabricate an AT_STOP.
- **PASSED_STOP:** Prevents noise regression once a stop is successfully passed.
- **Multi-Stop Gaps:** Skips over missed stops explicitly asserting `PASSED_STOP` *only* if the underlying match confidence ($\ge 0.75$) and context are incredibly strong. Otherwise, the gap stops are left as `UNKNOWN`.

## 2. Dwell Detection (`dwell_detection.py`)
- **DwellContext:** Persists internal state (`stationary_since`, `consecutive_movement_observations`). Uses absolute telemetry time (`packet.observed_at`) to assert durations, protecting the system from network ingestion latencies (`received_at`).
- **MOVING:** Restores immediately on massive positional jumps (`LARGE_PROGRESS_EXIT_M`), or smoothly through 2 consecutive strong movement observations.
- **DWELL_AT_STOP:** Detects stationary buses specifically nested inside a confidently asserted `AT_STOP` state for at least 15 seconds.
- **DWELL_NON_STOP:** Explicitly delineates buses held at traffic signals or congestion by asserting they are confidently stationary in a `BEFORE_STOP` or `PASSED_STOP` state for at least 30 seconds.
- **UNKNOWN:** Never fabricates states under ambiguity.

## Configuration
```python
# Stop Progression
BASE_STOP_TOLERANCE_M = 30.0
STOP_ACCURACY_FACTOR = 1.2
MAX_STOP_TOLERANCE_M = 100.0

STOP_AT_ENTER_MARGIN_M = 10.0
STOP_AT_EXIT_MARGIN_M = 10.0
STOP_PASS_MARGIN_M = 15.0
STOP_SPATIAL_PROXIMITY_M = 40.0

MULTI_STOP_STRONG_MATCH_CONFIDENCE = 0.75

# Dwell
STOP_SPEED_THRESHOLD_MPS = 0.55
STOP_DWELL_CONFIRM_SECONDS = 15.0
NON_STOP_DWELL_CONFIRM_SECONDS = 30.0

DWELL_EXIT_SPEED_THRESHOLD_MPS = 1.38
MOVEMENT_CONFIRMATION_OBSERVATIONS = 2
DWELL_EXIT_CONFIRMATION_OBSERVATIONS = 2
LARGE_PROGRESS_EXIT_M = 30.0
```

## Testing & Regression
- The matrix implemented 15 scenarios for stops and 13 for dwells, perfectly mapping the requested criteria.
- **Test Result:** 96 passing tests (Full Integration & Unit Regression).
- **Ruff Check:** Clean.
- **Ruff Format:** Clean.
- **Alembic:** `0001 (head)`.

## Database and API Status
- **Database:** Zero changes.
- **API:** Zero changes.

## Git Checkpoint
- **Commit:** `BUILD 3 - phase 3 stop progression and dwell`

## Known Issues
- None.

## Deviations
- None. System strictly adheres to the requested mathematical limits.
