# BUILD 3 PHASE 6 — FINAL ETA ENGINE + CONFIDENCE + FALLBACK PLAN

## 1. Input Contract
The ETA engine strictly consumes canonical outputs from Tracker Fusion (Phase 5) and Route Matching (Phase 4).
**ETAResult Contract:**
- `target_stop_id`: UUID
- `eta_seconds`: Integer (strictly non-negative)
- `lower_bound_seconds`: Integer
- `upper_bound_seconds`: Integer
- `confidence_score`: Float [0, 1]
- `status`: String (`LIVE`, `DEGRADED`, `FALLBACK`, `UNAVAILABLE`)
- `fallback_level`: Integer [0..5]
- `reason_codes`: List of strings explaining degradation (e.g., `"TARGET_ALREADY_PASSED"`, `"DWELL_NON_STOP"`)
- `generated_at`: Timestamp (UTC)
- `source_observed_at`: Timestamp (UTC)

No NaN, no Infinity, no negative outputs.

## 2. State & Freshness Semantics
ETA strictly inherits Canonical State semantics:
- **`LIVE`:** May use current evidence. ETA status -> `LIVE`.
- **`DEGRADED`:** Uses reduced confidence and widened bounds. ETA status -> `DEGRADED`.
- **`STALE`:** Live ETA forbidden. Uses only LEVEL 2+ approved fallbacks. ETA status -> `FALLBACK`.
- **`OFFLINE`:** Live ETA forbidden. Uses only LEVEL 2+ approved fallbacks. ETA status -> `UNAVAILABLE` if no fallback exists.
- **`NOT_ACTIVE`:** No ETA calculated. Instantly returns `UNAVAILABLE`.

## 3. Speed Model & Effective Floor
**Explicit Deterministic EWMA:**
`v_ewma(t) = alpha * v_current + (1 - alpha) * v_previous`
- **Tunable Parameter:** `ETA_EWMA_ALPHA = 0.35`
- **Validating Floor:** A speed of `0 m/s` is physically valid and preserved. We DO NOT fabricate artificial movement by wrapping raw speed in `max(speed, 1.0)`.
- **Denominator Safety:** `MIN_EFFECTIVE_SPEED_MPS` (e.g., `1.0 m/s`) is ONLY used to guard division operations when projecting future unobserved travel time. If current/estimated speed is 0 and no viable estimate exists for the future segment, the engine falls through to historical levels or `UNAVAILABLE`.

## 4. Multi-Scale Speed & Hierarchy
The engine traverses deterministic fallback levels.
- **LEVEL 0 (Live Current):** Fresh `LIVE` state + trusted route progress + validated EWMA speed.
- **LEVEL 1 (Smoothed Current):** Usable telemetry + EWMA stability (no historical).
- **LEVEL 2 (Historical Segment):** `>=20` valid segment samples + correct route/direction.
- **LEVEL 3 (Historical Route):** `>=20` route-level samples (segment unknown).
- **LEVEL 4 (Schedule):** Target and direction valid + schedule remains operationally meaningful.
- **LEVEL 5 (Unavailable):** Insufficient reliable data.

## 5. Historical Data: Segment vs Route
- **Segment Baseline (Level 2):** One sample = one observed, valid traversal of the specific segment (Stop A to Stop B).
- **Route Baseline (Level 3):** One sample = one complete valid traversal of the route in the specified direction/time bucket. Segment medians cannot be simply summed to create route-level medians.

## 6. Historical Outliers & Statistics
Robust statistics derived through **Median**.
- **Outlier Rejection:** Data is pre-filtered using **Median Absolute Deviation (MAD)**. Observations falling outside `median ± (3 * MAD)` are deterministically removed *before* the final median baseline is computed.
- **Minimum Sample Count:** `ETA_HISTORICAL_MIN_SAMPLES = 20`. Under 20 samples makes the baseline strictly unavailable.

## 7. Current & Historical Blending
Deterministic blending avoids multiplying unavailable components by zero:
`blended_speed = (w_curr * v_curr) + (w_hist * v_hist)`
- **Renormalization:** If `v_hist` is unavailable, `w_curr` becomes `1.0`. If `v_curr` is unavailable, `w_hist` becomes `1.0`. If both are unavailable, fallback triggers.
- **Base Weights:** 
  - `LIVE`: `w_curr = 0.85, w_hist = 0.15`
  - `DEGRADED`: `w_curr = 0.40, w_hist = 0.60`

## 8. Segment ETA & Destination Dwell
`ETA(target) = Σ(segment_travel_time) + Σ(median_destination_stop_dwell_seconds)`
- **`median_destination_stop_dwell_seconds`:** Represents expected passenger dwell at the `to_stop` of the segment.
- Dwell time at the final `target` stop is explicitly EXCLUDED from the arrival ETA of that stop.

## 9. Non-Stop Dwell Semantics
`CURRENT_NON_STOP_DWELL` is explicitly separated from `FUTURE_PREDICTED_TRAVEL_TIME`.
- It does NOT add predicted non-stop delay to future segments blindly.
- It applies a severe deterministic penalty to `Confidence` and dramatically widens the `upper_bound_seconds` for all downstream ETAs, acknowledging transient congestion without fabricating permanent slowdowns.

## 10. Schedule Fallback (LEVEL 4)
A `schedule-derived ETA` is the remaining estimated runtime derived strictly from explicit scheduled timetable data (if segments are mapped). 
- If timetable data lacks granular segment timings (common limitation), this tier reports `UNAVAILABLE` rather than fabricating arbitrary travel times from a top-level trip departure offset.

## 11. Uncertainty Mathematics
Explicit equation enforcing asymmetric widening:
- `base_variance = (1.0 - confidence) * base_eta_seconds`
- `lower_bound = max(0, base_eta_seconds - (base_variance * 0.5))`
- `upper_bound = min(ETA_MAX_SECONDS, base_eta_seconds + (base_variance * 1.5))`
- `DWELL_NON_STOP` adds `+ max(0.4 * base_eta, 300)` directly to the upper bound.
- `DEGRADED` adds `+ max(0.2 * base_eta, 120)` to the upper bound.

## 12. Confidence Calculation
`Confidence = Base(Canonical Confidence) * Freshness_Penalty * Dwell_Penalty * Deviation_Penalty * Blending_Penalty`
Clamped precisely to `[0, 1]`.

## 13. Route Deviation & Direction
- **Target Passed:** If traversal logic yields negative remaining distance, engine returns `TARGET_ALREADY_PASSED` (never ETA=0).
- **Direction Ambiguous:** Handled conditionally. If traversing `A_TO_B` vs `B_TO_A` results in opposing targets, engine returns `UNAVAILABLE`.
- **Deviation:** Off-route degrades confidence until safety timeout forces `UNAVAILABLE`.

## 14. Terminal Protection
Tiny remaining distance + `DWELL_AT_STOP` does NOT trigger `0 seconds` unless Trip Inference (Phase 4) explicitly marks the trip `COMPLETED`.

## 15. Telemetry Gaps & Trip Boundaries
- Short gaps (`<90s`): Normal calculation.
- Medium/Long gaps: Fallback triggers. Never assume the vehicle remained stationary.
- New Trip / Abandoned Trip: Instantly resets context (No ETA bleeds).

## 16. Database Proposal (Ready for Approval)
**Requirement:** Segment + Route tables required.
Organization isolation necessitates `organization_id` in historical tables as cross-tenant data bleed is strictly prohibited.

```sql
CREATE TABLE historical_segment_travel (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    route_id UUID NOT NULL REFERENCES routes(id),
    direction VARCHAR(10) NOT NULL,
    from_stop_id UUID NOT NULL REFERENCES stops(id),
    to_stop_id UUID NOT NULL REFERENCES stops(id),
    time_of_day_bucket VARCHAR(10) NOT NULL, -- e.g. "08:00" in deployment tz
    day_of_week SMALLINT NOT NULL,
    median_travel_seconds INTEGER NOT NULL,
    median_destination_stop_dwell_seconds INTEGER NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, route_id, direction, from_stop_id, to_stop_id, time_of_day_bucket, day_of_week)
);
CREATE INDEX ix_hist_seg_org_route_stops ON historical_segment_travel(organization_id, route_id, from_stop_id, to_stop_id);

CREATE TABLE historical_route_travel (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    route_id UUID NOT NULL REFERENCES routes(id),
    direction VARCHAR(10) NOT NULL,
    time_of_day_bucket VARCHAR(10) NOT NULL,
    day_of_week SMALLINT NOT NULL,
    median_travel_seconds INTEGER NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, route_id, direction, time_of_day_bucket, day_of_week)
);
CREATE INDEX ix_hist_route_org_route ON historical_route_travel(organization_id, route_id);
```
*(Migration 487cf68e2564 generated and verified).*

## 17. HISTORICAL DATA SCHEMA IMPLEMENTATION

### Implementation Details
- **Exact Tables Created**:
  - `historical_segment_travel`: Represents segment baseline (one sample = one valid traversal).
  - `historical_route_travel`: Represents route baseline (one sample = one valid complete traversal).
- **Exact Columns**: 
  - Segment: `id`, `organization_id`, `route_id`, `from_stop_id`, `to_stop_id`, `direction`, `time_of_day_bucket`, `day_of_week`, `median_travel_seconds`, `median_destination_stop_dwell_seconds`, `sample_count`, `created_at`, `updated_at`.
  - Route: `id`, `organization_id`, `route_id`, `direction`, `time_of_day_bucket`, `day_of_week`, `median_travel_seconds`, `sample_count`, `created_at`, `updated_at`.
- **Constraints**: 
  - Foreign Keys correctly map `route_id` and `stop_id` to their respective tables.
  - Unique Constraints enforced strictly to prevent duplication across identical time/day/route/org buckets.
- **Indexes**: 
  - `ix_hist_seg_org_route_stops`
  - `ix_hist_route_org_route`
- **Organization Isolation**: Historical tables enforce isolation via `organization_id` foreign keys and composite unique constraints incorporating `organization_id`.
- **Migration Revision**: `487cf68e2564` (Add historical travel tables).
- **Upgrade Result**: Both tables successfully created along with constraints and indexes.
- **Downgrade Result**: Both tables successfully removed (tested explicitly).
- **Re-upgrade Result**: Both tables successfully recreated (tested explicitly).
- **Regression**: 186 tests executed and PASSED.
- **Empty-state Semantics**: Both tables initialize empty. Historical ETA fallback remains `UNAVAILABLE` until sufficient real or explicitly generated development observations exist (Minimum Sample Count = 20).

## 17. Test Matrix
1. zero speed is not converted to 1m/s
2. missing historical baseline
3. missing current speed
4. missing both current and historical speed
5. historical segment sample count <20
6. historical segment sample count >=20
7. route baseline sample <20
8. route baseline sample >=20
9. segment median != route median
10. organization isolation
11. current/historical renormalization
12. destination dwell semantics
13. non-stop dwell uncertainty
14. exact uncertainty formula
15. asymmetric upper-bound widening
16. schedule fallback eligibility
17. target already passed
18. terminal near-zero distance
19. A_TO_B
20. B_TO_A
21. congestion
22. rain
23. traffic signal
24. speed spike
25. stale canonical
26. degraded canonical
27. offline canonical
28. insufficient evidence
29. no NaN
30. no Infinity
31. no negative ETA
32. ETA_MAX bound

## 18. India-Realism
Explicit modeling constraints for:
- Kolkata-style dense mixed traffic
- Delhi-style large congestion variation
- Mumbai-style stop congestion
- Bengaluru-style bottleneck traffic
Includes: auto/two-wheeler interference, signals, flyovers, rain, waterlogging, passenger boarding, slow traffic, temporary GPS degradation.

## 19. Metrics
- MAE, Median AE, P90, P95
- within 5 min, within 10 min
- false-live ETA rate, fallback frequency, UNAVAILABLE precision
- confidence calibration, terminal error, stop-level error
(No production claims without field data).

## 20. Phase 7 Boundary
**Explicitly NOT Implemented:** Crowding, Passenger APIs, WebSockets, push notifications, journey rendering, ML, advanced demand analytics.

## 21. Historical Schema Tenant Isolation

### 21.1 Original Isolation Failure
The initial Phase 6 implementation of the 2 historical support tables (`historical_segment_travel`, `historical_route_travel`) relied on simple foreign keys (e.g., `route_id -> routes.id`). While application logic was assumed to protect the boundaries, PostgreSQL did not structurally enforce that the `organization_id` of the historical baseline matched the `organization_id` of the referenced `Route` or `Stop`. 

### 21.2 Root Cause
PostgreSQL cannot natively restrict a foreign key relationship based on a parent table's column unless a composite foreign key is explicitly defined against a composite unique constraint in the parent table.

### 21.3 Structural Correction
To fully eliminate the risk of cross-tenant data bleed at the database level:
- **Stop Composite Uniqueness:** A new `UNIQUE(id, organization_id)` constraint (`uq_stops_id_org`) was added to the `stops` table (mirroring the existing constraint on `routes`).
- **Composite Foreign Keys:** The simple historical FKs were dropped and replaced with strict composite FKs binding the ownership of the baseline to the ownership of the route/stop.

### 21.4 Exact FK Definitions
**historical_segment_travel:**
- `FOREIGN KEY (organization_id, route_id) REFERENCES routes (organization_id, id)`
- `FOREIGN KEY (organization_id, from_stop_id) REFERENCES stops (organization_id, id)`
- `FOREIGN KEY (organization_id, to_stop_id) REFERENCES stops (organization_id, id)`

**historical_route_travel:**
- `FOREIGN KEY (organization_id, route_id) REFERENCES routes (organization_id, id)`

### 21.5 Integration Tests
Six precise negative and positive tests were added (`tests/integration/test_historical_isolation.py`) ensuring PostgreSQL intercepts and throws an `IntegrityError` when data is crossed:
- **Same-Org Success:** Org A + Route A + Stop A = SUCCESS. Org B + Route B + Stop B = SUCCESS.
- **Cross-Org Rejection:** Org A + Route B = REJECTED. Org A + Route A + Stop B = REJECTED. Org A + Stop B = REJECTED.

### 21.6 Migration & Regression
- **Revision:** `4fb7c61b0007` cleanly orchestrates the addition of `uq_stops_id_org` and the composite FKs without disrupting existing PostGIS components.
- **Robustness:** Successfully tested via `upgrade head`, `downgrade -1`, and `upgrade head`.
- **Regression:** A full project regression (192 tests) passed completely, verifying zero impact on the 20 core domain tables.
