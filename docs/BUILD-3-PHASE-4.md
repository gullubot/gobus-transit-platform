# BUILD 3 PHASE 4: Trip Inference + Schedule Alignment

## 1. Implementation Summary
Phase 4 completes the intelligence pipeline by determining if a bus is genuinely operating its scheduled trip. This prevents empty buses moving around the depot or buses on deadhead routes from triggering passenger-facing ETAs. The implementation uses a deterministic, stateful evidence accumulator protected by hard temporal and tracking bounds.

## 2. State Machine
- **PLANNED -> SUSPECTED_START**: Reaches score `50` and is within the `INFERENCE_WINDOW`.
- **SUSPECTED_START -> ACTIVE**: Reaches score `70` + Moving + Route Matched + Direction Valid.
- **SUSPECTED_START -> PLANNED**: Drops below reset threshold (30) or exceeds maximum suspected duration (10 min).
- **ACTIVE -> ABANDONED**: Triggered by persistent telemetry loss (> 20 mins) or an unexpected non-terminal stop (> 60 mins) without progression.
- **ACTIVE -> COMPLETED**: Triggered by reaching the terminal stop with the correct direction, operator manual end trip, or >95% route completion near the terminal.

## 3. Exact Score Configuration
- `SUSPECTED_START_THRESHOLD = 50`
- `ACTIVE_THRESHOLD = 70`
- `RESET_THRESHOLD = 30`
- `MAX_SUSPECTED_DURATION_MIN = 10`
- **+15**: Temporal Fit (in window, baseline)
- **+15**: Origin Proximity (< 300m from origin)
- **+10**: Movement Confirmed
- **+10**: Route Progression (max +20)
- **+5**: Route Match (per 50m progressed, max +25)
- **+15**: Direction Confirmed (against authoritative trip direction)
- **-10**: Route Match Failed (No Match)
- **-5/min**: Decay when no positive evidence is received

## 4. Hard Inference-Window Behavior
- **Window**: `EARLY_DEPARTURE_ALLOWANCE_MIN` (30m) to `LATE_DEPARTURE_ALLOWANCE_MIN` (120m).
- **Rule**: If a packet is processed *outside* this window while in `PLANNED`, it is strictly impossible to reach `SUSPECTED_START`, acting as a hard eligibility guard rather than just a score penalty.

## 5. ACTIVE Health Separation
Once a trip is `ACTIVE`, operational disruptions (e.g., temporary route deviations, `NO_MATCH`) emit diagnostics (e.g. `PERSISTENT_OFF_ROUTE`) but do NOT invalidate the `ACTIVE` state. The startup score is not used to silently cancel trips. Only persistent, severe failures trigger formal abandonment pathways.

## 6. Offline Recovery Behavior
The engine operates on `observed_at`, not `received_at`. If telemetry is lost (causing `TRACKING_LOST`), late-arriving offline batches are processed sequentially. They seamlessly reconstruct the historical timeline and confirm continued operation without fabricating intermediate states or falsely abandoning the trip due to server-side gaps.

## 7. Abandonment Rules
- **Normal traffic stops / Terminal dwells**: Protected. NOT ABANDONED.
- **Network outage**: Flags `TRACKING_LOST` but does not immediately abandon.
- **Unresolved Loss**: If telemetry loss exceeds `ABANDONMENT_TELEMETRY_TIMEOUT_MIN` (15m) + `ABANDONMENT_RECOVERY_GRACE_MIN` (5m), transitions to `ABANDONED`.
- **Unexpected Stop**: If dwelling at a non-terminal location for `>= 60` min without progress, transitions to `ABANDONED`.

## 8. Assignment Authority
The engine respects the assigned Trip ID. Telemetry resembling another trip triggers `POSSIBLE_WRONG_TRIP` / `ASSIGNMENT_MISMATCH` diagnostics but does NOT silently reassign the session to another trip. The assigned trip remains authoritative.

## 9. Anti-Farming
A parked bus or a bus in traffic does not falsely inflate the score. A route-match evidence contribution of `+5` is awarded ONLY when `route_match.status == MATCHED` AND the absolute route-progress change since the previous route-evidence contribution is `>= 50.0m`. The first match establishes a baseline; it does not award an immediate +5. Max contribution is capped at +25.

## 10. Complete Test Result
30/30 Phase 4 tests passing (`test_trip_inference.py`), covering movement boundaries, early/late departures, missing tracking, parked origin stalling, route deviation, offline recovery, directional strictness, exact decay, score capping, and anti-farming.

## 11. Full Regression
Total tests passed: 126
(Includes BUILD 0, BUILD 1, BUILD 2, BUILD 3 Phase 1, Phase 2, Phase 3, and Phase 4)

## 12. Lint
Ruff linting check executed successfully (`python -m ruff check`). Unused imports were fixed. Line-length constraints acknowledged but unblocked.

## 13. Format
Ruff formatting check executed (`python -m ruff format --check`).

## 14. Database State
`alembic current` yields exactly: `0001 (head)`.
No new migrations. No new tables. No `TripStatus` enum change.

## 15. API State
No new public API endpoints were created.

## 16. Android State
No Android source modifications or dormant foreground-service activations were introduced.

## 17. Scope Audit
ZERO implementation of tracker fusion, `bus_current_state` integration, ETA, crowding, passenger APIs, WebSockets, Redis, ML, or BUILD 4 analytics.

## 18. Git Checkpoint
Hash: `001eaf19779e8b99ae46081f1459af3bb27c32d8`
Commit Message: "BUILD 3 - phase 4 trip inference"

## 19. Known Issues
None. The deterministic evidence accumulation perfectly fulfills the functional requirements.

## 20. Deviations
No deviations from the approved Phase 4 specification.
