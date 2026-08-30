import json
from datetime import datetime
from typing import Dict, Optional

from app.intelligence.core_models import (
    Direction,
    DwellContext,
    DwellState,
    RouteMatchContext,
    StopProgressContext,
    StopState,
    TrackerState,
    TripInferenceContext,
)


def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def deserialize_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(dt_str) if dt_str else None


def serialize_contexts(
    trip_ctx: Optional[TripInferenceContext],
    stop_ctx: Optional[StopProgressContext],
    dwell_ctx: Optional[DwellContext],
    dir_ctx: Optional[RouteMatchContext],
    trackers: Dict[str, TrackerState],
) -> dict:
    result = {}

    if trip_ctx:
        result["trip_ctx"] = {
            "trip_id": trip_ctx.trip_id,
            "status": trip_ctx.status,
            "score": trip_ctx.score,
            "score_timestamp": serialize_datetime(trip_ctx.score_timestamp),
            "suspected_start_at": serialize_datetime(trip_ctx.suspected_start_at),
            "last_route_evidence_progress_m": trip_ctx.last_route_evidence_progress_m,
            "route_evidence_contribution": trip_ctx.route_evidence_contribution,
            "stop_evidence_contribution": trip_ctx.stop_evidence_contribution,
            "tracking_lost_since": serialize_datetime(trip_ctx.tracking_lost_since),
        }

    if stop_ctx:
        result["stop_ctx"] = {
            "stop_states": {k: v.value for k, v in stop_ctx.stop_states.items()},
            "current_stop_id": stop_ctx.current_stop_id,
            "next_stop_id": stop_ctx.next_stop_id,
            "previous_stop_id": stop_ctx.previous_stop_id,
        }

    if dwell_ctx:
        result["dwell_ctx"] = {
            "stationary_since": serialize_datetime(dwell_ctx.stationary_since),
            "last_moving_at": serialize_datetime(dwell_ctx.last_moving_at),
            "last_observed_at": serialize_datetime(dwell_ctx.last_observed_at),
            "previous_dwell_state": dwell_ctx.previous_dwell_state.value,
            "associated_stop_id": dwell_ctx.associated_stop_id,
            "consecutive_movement_observations": dwell_ctx.consecutive_movement_observations,
            "previous_route_progress_m": dwell_ctx.previous_route_progress_m,
        }

    if dir_ctx:
        result["dir_ctx"] = {
            "route_id": dir_ctx.route_id,
            "segment_index": dir_ctx.segment_index,
            "route_progress_m": dir_ctx.route_progress_m,
            "direction": dir_ctx.direction.value,
            "matched_at": serialize_datetime(dir_ctx.matched_at),
            "confidence": dir_ctx.confidence,
            "direction_observations": dir_ctx.direction_observations,
            "opposite_direction_observations": dir_ctx.opposite_direction_observations,
        }

    if trackers:
        result["trackers"] = {}
        for src_id, t_state in trackers.items():
            result["trackers"][src_id] = {
                "source_id": t_state.source_id,
                "last_packet_id": t_state.last_packet_id,
                "last_observed_at": serialize_datetime(t_state.last_observed_at),
                "last_reliability": t_state.last_reliability,
                "consecutive_valid_observations": t_state.consecutive_valid_observations,
                "consecutive_recovery_observations": t_state.consecutive_recovery_observations,
                "is_trusted": t_state.is_trusted,
            }

    # Convert any lingering UUIDs or Enums to primitives (str)
    return json.loads(json.dumps(result, default=str))


def deserialize_contexts(data: Optional[dict], current_trip_id: str) -> tuple:
    # Returns (trip_ctx, stop_ctx, dwell_ctx, dir_ctx, trackers)
    if not data:
        return None, None, None, None, {}

    trip_ctx = None
    stop_ctx = None
    dwell_ctx = None
    dir_ctx = None
    trackers = {}

    try:
        if "trip_ctx" in data:
            tc = data["trip_ctx"]
            # Scoped isolation: only load if trip_id matches
            if tc.get("trip_id") == current_trip_id:
                trip_ctx = TripInferenceContext(
                    trip_id=tc["trip_id"],
                    status=tc["status"],
                    score=tc.get("score", 0.0),
                    score_timestamp=deserialize_datetime(tc.get("score_timestamp")),
                    suspected_start_at=deserialize_datetime(tc.get("suspected_start_at")),
                    last_route_evidence_progress_m=tc.get("last_route_evidence_progress_m"),
                    route_evidence_contribution=tc.get("route_evidence_contribution", 0.0),
                    stop_evidence_contribution=tc.get("stop_evidence_contribution", 0.0),
                    tracking_lost_since=deserialize_datetime(tc.get("tracking_lost_since")),
                )

                # Load corresponding route contexts only if trip matched (temporal continuity)
                if "stop_ctx" in data:
                    sc = data["stop_ctx"]
                    stop_ctx = StopProgressContext(
                        stop_states={k: StopState(v) for k, v in sc.get("stop_states", {}).items()},
                        current_stop_id=sc.get("current_stop_id"),
                        next_stop_id=sc.get("next_stop_id"),
                        previous_stop_id=sc.get("previous_stop_id"),
                    )

                if "dwell_ctx" in data:
                    dc = data["dwell_ctx"]
                    dwell_ctx = DwellContext(
                        stationary_since=deserialize_datetime(dc.get("stationary_since")),
                        last_moving_at=deserialize_datetime(dc.get("last_moving_at")),
                        last_observed_at=deserialize_datetime(dc.get("last_observed_at")),
                        previous_dwell_state=DwellState(dc.get("previous_dwell_state", "UNKNOWN")),
                        associated_stop_id=dc.get("associated_stop_id"),
                        consecutive_movement_observations=dc.get(
                            "consecutive_movement_observations", 0
                        ),
                        previous_route_progress_m=dc.get("previous_route_progress_m"),
                    )

                if "dir_ctx" in data:
                    dirc = data["dir_ctx"]
                    dir_ctx = RouteMatchContext(
                        route_id=dirc["route_id"],
                        segment_index=dirc["segment_index"],
                        route_progress_m=dirc["route_progress_m"],
                        direction=Direction(dirc.get("direction", "UNKNOWN")),
                        matched_at=deserialize_datetime(dirc.get("matched_at")),
                        confidence=dirc.get("confidence", 0.0),
                        direction_observations=dirc.get("direction_observations", 1),
                        opposite_direction_observations=dirc.get(
                            "opposite_direction_observations", 0
                        ),
                    )

        # Trackers are scoped by device/source, so load them independently of trip
        if "trackers" in data:
            for src_id, ts in data["trackers"].items():
                trackers[src_id] = TrackerState(
                    source_id=ts["source_id"],
                    last_packet_id=ts.get("last_packet_id"),
                    last_observed_at=deserialize_datetime(ts.get("last_observed_at")),
                    last_reliability=ts.get("last_reliability", 0.0),
                    consecutive_valid_observations=ts.get("consecutive_valid_observations", 0),
                    consecutive_recovery_observations=ts.get(
                        "consecutive_recovery_observations", 0
                    ),
                    is_trusted=ts.get("is_trusted", False),
                )
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to deserialize contexts: {e}")

    return trip_ctx, stop_ctx, dwell_ctx, dir_ctx, trackers
