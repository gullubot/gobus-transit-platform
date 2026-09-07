# BUILD 4 - STEP 8M: DEMO SIMULATOR ARCHITECTURE AUDIT REPORT

## A. Existing Tracking Input Architecture
The backend tracking architecture relies on `/api/trips/{trip_id}/start`, `/api/trips/{trip_id}/end`, and `/api/tracking/batch` endpoints.
- `TrackingSession` must be established.
- Batches contain `TrackingEvent` packets with `latitude`, `longitude`, `speed_mps`, `heading`, `observed_at`.
- Immutable `TrackingEvent` records are saved and then synchronously handed to `IntelligenceOrchestrator`.

## B. Existing Operator API Compatibility
**Fully Compatible.** The simulator MUST act exactly like the Operator Android application.
- It will acquire a JWT by authenticating with standard Operator credentials via `/api/auth/operator/login`.
- It will hit the existing `/api/tracking/batch` endpoint.
- It will explicitly start and end trips using `/api/trips/{trip_id}/start` and `/api/trips/{trip_id}/end`.
There is absolutely no need to create a bypass or a simulator-only privileged endpoint.

## C. Authentication Method
The simulator will use standard `OAuth2PasswordRequestForm` against `/api/auth/operator/login`.
- **Token Handling**: The simulator will store the returned JWT `access_token` and attach it as `Authorization: Bearer <token>` on all requests. 
- **Refresh Strategy**: If a 401 Unauthorized occurs, the simulator must re-authenticate and acquire a fresh token.

## D. SD5 Database Discovery
The simulator can safely discover the SD5 metadata by calling the existing Passenger API (`GET /api/passenger/routes?route_code=SD5`), fetching the detailed sequence via `/api/passenger/routes/{route_id}`, and resolving the assigned vehicle/trip using the Operator's `/api/operator/me/assignment` endpoint.
No hardcoded JSON route definitions are needed inside the simulator code.

## E. Movement / GPS Strategy
The simulator will implement a deterministic interpolation engine:
1. Load the ordered `RouteStop` sequence coordinates for SD5.
2. Advance a simulated point along the `LINESTRING` between `Stop N` and `Stop N+1` based on a predefined speed (e.g., 5 m/s).
3. Compute heading via bearing mathematics between the two points.
4. Generate and append `TrackingBatchRequest` packets dynamically.
This perfectly mimics real continuous movement inputs.

## F. Time Acceleration
Because the `CrowdingReport` API explicitly rejects `observed_at` timestamps more than 5 minutes in the future (Future Timestamp Validation, `allowed_skew = 300`), the simulator **cannot accelerate time into the future**.
**Recommended Strategy**: To simulate a 1-hour trip in 6 minutes (10x speed), the simulator must initialize the simulation clock to `NOW - 1 hour`. As it generates events, the `observed_at` will be in the past (which is fully permitted by the tracking logic). It will progressively "catch up" to the real current time.

## G. Multi-Vehicle Architecture
The simulator should use Python's `asyncio` to spawn multiple asynchronous actor loops. Each actor maintains its own state:
- Vehicle ID
- JWT Token (or a shared token if simulating multiple trips under a depot admin, but strictly it should use distinct Operator accounts).
- Current coordinates
- Simulation clock
This natively allows running SD5 `Bus 1 (A_TO_B)` and `Bus 2 (B_TO_A)` concurrently from the laptop.

## H. Scenario Architecture
Scenarios should be implemented as strategy classes that mutate the movement physics and event payloads:
- **Normal**: Moves at constant expected velocity.
- **Delay**: Modifies the speed multiplier dynamically (e.g., reduces speed to 1 m/s) to trigger ETAEngine updates.
- **Offline/Stale**: Suspends the `POST /api/tracking/batch` loop temporarily while keeping the simulation running, triggering the `AlertEngine`.
- **Crowding**: Automatically injects a `CrowdingReportRequest` payload.

## I. Crowding Simulation Feasibility
**Fully Feasible.** The existing `/api/crowding/reports` API accepts operator-submitted crowding levels. The simulator simply needs to POST a payload containing `observed_at` and `level` while authenticated. The `CrowdingEngine` will naturally process this into a `CrowdingReport` which will feed the `InsightsService`.

## J. Delay Simulation Feasibility
**Fully Feasible.** By artificially reducing the movement step size between polling intervals (slower simulated speed) or introducing a long dwell time at a stop, the simulator will produce trailing `TrackingEvent` records. The `ETAEngine` natively computes delays from lagging spatial progression. We do not directly modify `ETAPrediction`.

## K. Alert Trigger Feasibility
**Fully Feasible.** To trigger a `STALE ALERT`, the simulator only needs to execute an `await asyncio.sleep(stale_threshold)` in its main loop without sending telemetry. The actual backend `LiveOperations` service will independently notice the gap and flag the session as offline.

## L. Insight Generation Feasibility
The Insights service requires historical data to generate recurring crowding predictions. The simulator can run an initialization phase where it submits crowding reports with `observed_at` set to `NOW - 24 hours` and `NOW - 48 hours` to seed the database prior to the live demonstration, enabling instant Insights dashboard functionality.

## M. Reset / Cleanup Strategy
Since the simulator is acting as a real client, all generated data is technically "real" operation data.
**Recommendation**: The Admin API should expose an endpoint (or a secure SQL script provided with the simulator) to `DELETE FROM tracking_events WHERE operator_id IN (demo_operators)` or cascade delete trips explicitly flagged as "SIMULATED". 

## N. Configuration Strategy
A YAML file `simulator/config.yaml` is recommended. It cleanly supports nested scenario definitions, target host URLs, speed multipliers, and the list of demo Operator credentials to utilize.

## O. Control Interface Recommendation
A terminal-based Dashboard using the Python `rich` library.
It provides a Live layout showing:
- Active scenarios
- Simulated coordinate status
- Last API HTTP status
- Simple CLI keystrokes (Press 'P' to pause, 'D' to inject delay, 'C' to inject crowd).

## P. Observability
The `rich` console will log every API interaction (HTTP 200, HTTP 429 Rate Limit, HTTP 403) and current simulation time vs real time, ensuring absolute clarity during a live presentation.

## Q. Security
Credentials will be read strictly from `config.yaml`. The simulator does not require direct database access, TLS bypassing, or hardcoded JWT secrets. It is just another client.

## R. Performance
By batching telemetry (sending 5 packets every 5 real seconds rather than 1 per second), the simulator will remain highly performant and network-efficient, mimicking real Operator Android batching logic.

## S. Testing Strategy
No integration tests for the backend are needed for this phase. The simulator itself can have unit tests verifying the Haversine interpolation math to ensure the bus smoothly follows the polyline without jumping.

## T. Exact Files That Would Need Creation
- `simulator/main.py`
- `simulator/config.yaml`
- `simulator/client.py`
- `simulator/physics.py`
- `simulator/scenarios.py`
- `simulator/requirements.txt`

## U. Exact Existing Files That Must Remain Untouched
All existing files in `backend/app/*` (Specifically `backend/app/intelligence/*` and `backend/app/api/*`). The simulator is fully external.

## V. Risks
- **Rate Limiting**: The crowding API has a strict rate limit (`Operator limit: 5 per 5 mins per vehicle`). The simulator must not spam crowding reports during time acceleration, or it will receive `HTTP 429` errors.
- **Time Skew Rejection**: Accidentally accelerating `observed_at` beyond `datetime.now()` will cause HTTP 400 errors.

## W. Open Questions
- Should the simulator create its own assigned Trips via the Admin API before starting, or should it assume the Admin Web UI has already dispatched a Trip to the demo operator? (Assumption: Simulator creates the trip automatically via admin credentials for seamless demos).

## X. Implementation Order
1. Scaffolding `simulator/` directory and CLI framework.
2. `client.py` (Authentication & Tracking API bindings).
3. `physics.py` (Polyline interpolation from SD5 route).
4. `scenarios.py` (Delay, Crowding, Stale logic).
5. `main.py` orchestrator.
