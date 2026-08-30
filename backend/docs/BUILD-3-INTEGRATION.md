# Build 3 Integration - End-to-End System

## Overview
This document outlines the final integration of the GoBus Phase 1-7 intelligence components into a synchronous, single-node end-to-end processing pipeline for Build 3.

## The End-to-End Chain
The integration achieves a complete lifecycle for transit telemetry, flowing synchronously from device ingestion to passenger API exposure.

### 1. Ingestion (Android Operator)
- **Source:** The Android Operator app POSTs a telemetry batch to `/api/operator/tracking/telemetry`.
- **Validation:** Basic payload validation ensures required fields are present.
- **Persistence:** Events are inserted into `tracking_events`.

### 2. The Intelligence Orchestrator (`IntelligenceOrchestrator`)
The orchestrator acts as the central coordinator, bypassing complex asynchronous queues (Celery/Kafka) to provide immediate, synchronous state generation for the prototype demo.

For each telemetry packet, the following sequence executes:

1. **GPS Validation:** `GPSValidator` inspects accuracy, time staleness, and logical bounds to mark the packet as VALID or REJECTED.
2. **Route Matching:** `RouteMatcher` projects the valid GPS point onto the scheduled route's topology, yielding `cross_track_distance_m` and `route_progress_m`.
3. **Direction Inference:** `DirectionEngine` analyzes progressive movement along the topology to deduce the current travel direction (A_TO_B or B_TO_A).
4. **Stop Progression:** `StopProgressionEngine` evaluates the vehicle's `route_progress_m` against known stop locations, determining if the bus is APPROACHING, AT_STOP, or has PASSED the stop.
5. **Dwell Detection:** `DwellEngine` calculates time spent stationary AT_STOP to yield a Dwell duration.
6. **Trip Inference:** `TripInferenceEngine` assesses overall progress against scheduled operating blocks, transitioning trips from PLANNED to ACTIVE to COMPLETED.
7. **Tracker Fusion:** The disparate intelligence results are merged into a cohesive `CanonicalStateContext`, resolving contradictions based on confidence scores.
8. **ETA Calculation:** `ETAEngine` leverages the canonical route progress, direction, and stop topology to compute estimated arrival times for downstream stops.
9. **State Persistence:** The finalized `CanonicalStateContext` is persisted to `bus_current_state`, overwriting previous states for that vehicle.

### 3. Passenger Endpoint
- **Source:** The passenger app GETs the vehicle state via `/api/passenger/vehicles/{vehicle_id}`.
- **Retrieval:** The API queries the `bus_current_state` table.
- **Crowding Fusion:** Real-time and historical crowding reports are aggregated synchronously by `CrowdingEngine.aggregate_vehicle_crowding` and composed into the response.
- **Result:** The passenger receives a comprehensive JSON payload detailing location, ETA, and crowding confidence.

## Prototype Constraints
- **Synchronous Execution:** Ensures immediate consistency for demo purposes but is blocking.
- **State Hydration:** Engine contexts are intentionally rehydrated/initialized per event rather than held in-memory across distributed workers.
- **Direct ORM Access:** The Orchestrator leverages raw SQLAlchemy queries to bypass repository circular dependencies.
