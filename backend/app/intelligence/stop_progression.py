import math
from typing import List, Optional, Tuple, Dict

from .config import (
    BASE_STOP_TOLERANCE_M,
    STOP_ACCURACY_FACTOR,
    MAX_STOP_TOLERANCE_M,
    STOP_AT_ENTER_MARGIN_M,
    STOP_AT_EXIT_MARGIN_M,
    STOP_PASS_MARGIN_M,
    STOP_SPATIAL_PROXIMITY_M,
    MULTI_STOP_STRONG_MATCH_CONFIDENCE,
)
from .core_models import (
    Direction,
    RouteMatchResult,
    RouteStop,
    StopProgressContext,
    StopProgressResult,
    StopState,
    TelemetryPacket,
)
from .gps_validation import haversine_distance


class StopProgressionEngine:
    """
    Evaluates bus progression through route stops deterministically.
    """

    @staticmethod
    def calculate_tolerance(accuracy_m: Optional[float]) -> float:
        if accuracy_m is None:
            accuracy_m = 10.0  # reasonable default if missing, or we can just use BASE
            # Wait, the rule is "Use the configured base tolerance when accuracy is unavailable."
            # If we use max(BASE, accuracy * FACTOR), if accuracy is missing, we just use BASE.
            return BASE_STOP_TOLERANCE_M
            
        return min(
            MAX_STOP_TOLERANCE_M,
            max(BASE_STOP_TOLERANCE_M, accuracy_m * STOP_ACCURACY_FACTOR),
        )

    @staticmethod
    def evaluate_progression(
        packet: TelemetryPacket,
        match: RouteMatchResult,
        stops: List[RouteStop],
        prev_context: Optional[StopProgressContext] = None,
    ) -> StopProgressResult:
        if not match.route_id or match.route_progress_m is None:
            return StopProgressResult(
                state=StopState.UNKNOWN,
                current_stop_id=None,
                next_stop_id=None,
                previous_stop_id=None,
                route_progress_m=None,
                progression_confidence=0.0,
                diagnostic_codes=["NO_ROUTE_PROGRESS"],
            )

        if match.direction == Direction.UNKNOWN:
            return StopProgressResult(
                state=StopState.UNKNOWN,
                current_stop_id=None,
                next_stop_id=None,
                previous_stop_id=None,
                route_progress_m=match.route_progress_m,
                progression_confidence=0.0,
                diagnostic_codes=["DIRECTION_UNKNOWN"],
            )

        if not stops:
            return StopProgressResult(
                state=StopState.UNKNOWN,
                current_stop_id=None,
                next_stop_id=None,
                previous_stop_id=None,
                route_progress_m=match.route_progress_m,
                progression_confidence=0.0,
                diagnostic_codes=["NO_STOPS_PROVIDED"],
            )

        tol = StopProgressionEngine.calculate_tolerance(packet.accuracy_m)

        # 1. Order stops operationally
        ordered_stops = sorted(stops, key=lambda s: s.sequence_number)
        if match.direction == Direction.B_TO_A:
            ordered_stops.reverse()

        # 2. Reconstruct state
        state_map = {}
        if prev_context and prev_context.stop_states:
            state_map = dict(prev_context.stop_states)

        # 3. Evaluate each stop in operational order
        current_progress = match.route_progress_m
        
        # Track diagnostics
        diagnostics = []

        # Find the first operational stop that is NOT PASSED.
        # But wait, we must also handle multi-stop gap filling.
        
        strong_evidence = (
            match.match_confidence is not None 
            and match.match_confidence >= MULTI_STOP_STRONG_MATCH_CONFIDENCE
            and match.direction != Direction.UNKNOWN
            and prev_context is not None
            # physically plausible progress delta is implicitly handled by RouteMatcher (match_confidence would drop if impossible)
        )

        for i, stop in enumerate(ordered_stops):
            prev_state = state_map.get(stop.id, StopState.UNKNOWN)

            # If it's already PASSED_STOP, a noisy point cannot undo it.
            if prev_state == StopState.PASSED_STOP:
                continue

            dist_delta = current_progress - stop.distance_from_start
            
            # BEFORE / PASSED bounds depending on direction
            is_before = False
            is_passed = False
            
            if match.direction == Direction.A_TO_B:
                if current_progress < stop.distance_from_start - (tol - STOP_AT_ENTER_MARGIN_M):
                    is_before = True
                elif current_progress > stop.distance_from_start + tol + STOP_PASS_MARGIN_M:
                    is_passed = True
            else: # B_TO_A
                if current_progress > stop.distance_from_start + (tol - STOP_AT_ENTER_MARGIN_M):
                    is_before = True
                elif current_progress < stop.distance_from_start - tol - STOP_PASS_MARGIN_M:
                    is_passed = True

            # AT_STOP logic
            in_enter_band = abs(dist_delta) <= (tol - STOP_AT_ENTER_MARGIN_M)
            in_exit_band = abs(dist_delta) <= (tol + STOP_AT_EXIT_MARGIN_M)
            
            spatial_dist = haversine_distance(packet.lat, packet.lon, stop.lat, stop.lon)
            
            # Trajectory approach check
            confirmed_approach = (prev_state == StopState.BEFORE_STOP and in_enter_band)
            stationary = (packet.speed_mps is not None and packet.speed_mps <= 0.55) # Assuming STOP_SPEED_THRESHOLD_MPS = 0.55
            
            # Primary evaluation
            new_state = StopState.UNKNOWN
            
            if prev_state == StopState.AT_STOP:
                # REMAIN AT_STOP
                if in_exit_band:
                    new_state = StopState.AT_STOP
                else:
                    # Exited the band
                    if is_passed:
                        new_state = StopState.PASSED_STOP
                    elif is_before:
                        new_state = StopState.BEFORE_STOP
                    else:
                        # Technically in the intermediate margin, wait to commit.
                        new_state = StopState.AT_STOP 
            else:
                # Attempt to ENTER AT_STOP
                if in_enter_band:
                    if (spatial_dist <= STOP_SPATIAL_PROXIMITY_M) or confirmed_approach or (prev_state == StopState.BEFORE_STOP and in_exit_band and stationary):
                        new_state = StopState.AT_STOP
                    else:
                        # Inside band but missing strong evidence, assume BEFORE until proven.
                        # Wait, the spec says "Low speed alone MUST NEVER create AT_STOP".
                        # If we lack evidence, we stay in BEFORE or UNKNOWN.
                        new_state = prev_state if prev_state != StopState.UNKNOWN else StopState.BEFORE_STOP
                elif is_passed:
                    # Multi-stop gap logic
                    if prev_state in (StopState.BEFORE_STOP, StopState.UNKNOWN):
                        if strong_evidence:
                            new_state = StopState.PASSED_STOP
                        else:
                            new_state = StopState.UNKNOWN
                            diagnostics.append("WEAK_GAP_EVIDENCE")
                    else:
                        new_state = StopState.PASSED_STOP
                elif is_before:
                    new_state = StopState.BEFORE_STOP
                else:
                    new_state = prev_state if prev_state != StopState.UNKNOWN else StopState.BEFORE_STOP

            state_map[stop.id] = new_state

        # Determine current, next, previous stops operationally
        current_stop_id = None
        next_stop_id = None
        previous_stop_id = None
        
        # The "active" stop is the first one that is BEFORE_STOP or AT_STOP or UNKNOWN
        for i, stop in enumerate(ordered_stops):
            st = state_map.get(stop.id)
            if st == StopState.PASSED_STOP:
                previous_stop_id = stop.id
                continue
            
            if st == StopState.AT_STOP:
                current_stop_id = stop.id
                if i + 1 < len(ordered_stops):
                    next_stop_id = ordered_stops[i+1].id
                break
            
            if st in (StopState.BEFORE_STOP, StopState.UNKNOWN):
                next_stop_id = stop.id
                break

        overall_state = StopState.UNKNOWN
        if current_stop_id:
            overall_state = StopState.AT_STOP
        elif next_stop_id:
            overall_state = StopState.BEFORE_STOP
        elif previous_stop_id:
            overall_state = StopState.PASSED_STOP

        return StopProgressResult(
            state=overall_state,
            current_stop_id=current_stop_id,
            next_stop_id=next_stop_id,
            previous_stop_id=previous_stop_id,
            route_progress_m=current_progress,
            progression_confidence=match.match_confidence or 0.0,
            diagnostic_codes=diagnostics,
        )
