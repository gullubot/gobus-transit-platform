import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.intelligence import config
from app.intelligence.core_models import (
    Direction,
    DwellResult,
    DwellState,
    RouteMatchResult,
    RouteMatchStatus,
    StopProgressResult,
    StopState,
    TelemetryPacket,
    TripInferenceContext,
    TripInferenceDiagnostic,
    TripInferenceResult,
)
from app.models.enums import TrackingSessionStatus, TripStatus

logger = logging.getLogger(__name__)


class TripInferenceEngine:
    """
    Evaluates whether an assigned scheduled trip is genuinely operating.
    Implements the BUILD 3 PHASE 4 exact evidence accumulator model.
    """

    def evaluate(
        self,
        packet: TelemetryPacket,
        session_status: TrackingSessionStatus,
        assigned_trip_id: str,
        planned_start_at: datetime,
        route_match: RouteMatchResult,
        direction: Direction,
        stop_progress: StopProgressResult,
        dwell: DwellResult,
        context: Optional[TripInferenceContext] = None,
        authoritative_trip_direction: Optional[Direction] = None,
        is_terminal_stop: bool = False,
        is_operator_end_trip: bool = False,
        tracking_loss_duration_sec: float = 0.0,
    ) -> TripInferenceResult:
        if not context:
            context = TripInferenceContext(
                trip_id=assigned_trip_id, status=TripStatus.PLANNED, score=0.0
            )

        diagnostics: List[TripInferenceDiagnostic] = []
        obs_time = packet.observed_at

        # 1. HARD GUARD: Tracking Session
        if session_status != TrackingSessionStatus.ACTIVE:
            diagnostics.append(TripInferenceDiagnostic.NO_ACTIVE_TRACKING_SESSION)
            # Cannot infer anything without tracking, do not update state
            return self._build_result(context, diagnostics)

        # 2. SCHEDULE WINDOW
        early_bound = planned_start_at - timedelta(minutes=config.EARLY_DEPARTURE_ALLOWANCE_MIN)
        late_bound = planned_start_at + timedelta(minutes=config.LATE_DEPARTURE_ALLOWANCE_MIN)
        is_in_window = early_bound <= obs_time <= late_bound

        if is_in_window:
            diagnostics.append(TripInferenceDiagnostic.SCHEDULE_WINDOW_MATCH)

        # 3. ABANDONMENT / COMPLETED PATHS (If already ACTIVE)
        if context.status == TripStatus.ACTIVE:
            # Check COMPLETED
            if is_operator_end_trip:
                context.status = TripStatus.COMPLETED
                return self._build_result(context, diagnostics)

            if is_terminal_stop and stop_progress.state == StopState.PASSED_STOP:
                # Need correct direction. If direction matches or authoritative matches
                if (
                    direction == authoritative_trip_direction
                    or authoritative_trip_direction is None
                ):
                    context.status = TripStatus.COMPLETED
                    return self._build_result(context, diagnostics)

            # Note: 95% progress fallback must be explicitly paired with terminal vicinity/dwell,
            # handled here if data available.
            if (
                route_match.route_progress_m
                and stop_progress.route_progress_m
                and route_match.route_progress_m > 0
            ):
                pass

            # Check ABANDONED (Path A: Telemetry Loss)
            if tracking_loss_duration_sec > 0:
                loss_min = tracking_loss_duration_sec / 60.0
                if loss_min > (
                    config.ABANDONMENT_TELEMETRY_TIMEOUT_MIN + config.ABANDONMENT_RECOVERY_GRACE_MIN
                ):
                    context.status = TripStatus.ABANDONED
                    return self._build_result(context, diagnostics)

            # Check ABANDONED (Path B: Unexpected Stop)
            if (
                dwell.state == DwellState.DWELL_NON_STOP
                and (dwell.duration_seconds / 60.0) >= config.UNEXPECTED_STOP_ABANDONMENT_MIN
            ):
                # Not terminal, no progress.
                if not is_terminal_stop:
                    context.status = TripStatus.ABANDONED
                    return self._build_result(context, diagnostics)

            # ACTIVE state health diagnostics (does not reduce score to 0)
            if route_match.status == RouteMatchStatus.NO_MATCH:
                diagnostics.append(TripInferenceDiagnostic.PERSISTENT_OFF_ROUTE)

        # 4. STARTUP ACCUMULATOR (PLANNED & SUSPECTED_START)
        if context.status in (TripStatus.PLANNED, TripStatus.SUSPECTED_START):
            positive_evidence_this_tick = False
            score = context.score

            # Apply Decay if no positive evidence yet. We will calculate first.

            # Temporal Fit (+15)
            if is_in_window and score == 0:
                score += 15
                positive_evidence_this_tick = True

            # Origin Proximity (+15)
            if (
                route_match.route_progress_m is not None
                and route_match.route_progress_m < config.ORIGIN_PROXIMITY_M
            ):
                diagnostics.append(TripInferenceDiagnostic.ORIGIN_PROXIMITY)
                if score < 30:  # If we just started
                    score += 15
                    positive_evidence_this_tick = True

            # Movement (+10)
            if dwell.state == DwellState.MOVING and dwell.confidence >= 0.75:
                diagnostics.append(TripInferenceDiagnostic.MOVEMENT_CONFIRMED)
                score += 10
                positive_evidence_this_tick = True

            # Stop Progression (+10 per, max 20)
            if stop_progress.state == StopState.PASSED_STOP:
                diagnostics.append(TripInferenceDiagnostic.ROUTE_PROGRESSION_CONFIRMED)
                if context.stop_evidence_contribution < config.STOP_PROGRESSION_MAX_CONTRIBUTION:
                    context.stop_evidence_contribution += 10
                    score += 10
                    positive_evidence_this_tick = True

            # Route Match (+5 per, max 25)
            if route_match.status == RouteMatchStatus.MATCHED:
                if context.last_route_evidence_progress_m is None:
                    context.last_route_evidence_progress_m = route_match.route_progress_m
                    # Establish baseline, do not award +5 yet.
                else:
                    if route_match.route_progress_m is not None:
                        delta = abs(
                            route_match.route_progress_m - context.last_route_evidence_progress_m
                        )
                        if delta >= config.ROUTE_EVIDENCE_MIN_PROGRESS_DELTA_M:
                            context.last_route_evidence_progress_m = route_match.route_progress_m
                            if (
                                context.route_evidence_contribution
                                < config.ROUTE_MATCH_MAX_CONTRIBUTION
                            ):
                                context.route_evidence_contribution += 5
                                score += 5
                                positive_evidence_this_tick = True
                        else:
                            diagnostics.append(TripInferenceDiagnostic.REPEATED_EVIDENCE)
            else:
                score -= 10  # -10 per NO_MATCH

            # Direction (+15)
            if direction != Direction.UNKNOWN:
                if authoritative_trip_direction and direction == authoritative_trip_direction:
                    diagnostics.append(TripInferenceDiagnostic.DIRECTION_CONFIRMED)
                    score += 15
                    positive_evidence_this_tick = True
                elif authoritative_trip_direction and direction != authoritative_trip_direction:
                    score -= 20

            # Apply Decay if no positive evidence
            if not positive_evidence_this_tick and context.score_timestamp:
                elapsed_min = (obs_time - context.score_timestamp).total_seconds() / 60.0
                if elapsed_min > 0:
                    score -= config.EVIDENCE_DECAY_PER_MINUTE * elapsed_min

            if positive_evidence_this_tick:
                context.score_timestamp = obs_time

            # Clamp score
            score = max(0.0, min(100.0, score))
            context.score = score

            # State Transitions
            if context.status == TripStatus.PLANNED:
                # PLANNED -> SUSPECTED_START requires inside INFERENCE_WINDOW and score >= 50
                if score >= config.SUSPECTED_START_THRESHOLD and is_in_window:
                    context.status = TripStatus.SUSPECTED_START
                    context.suspected_start_at = obs_time

            if context.status == TripStatus.SUSPECTED_START:
                # SUSPECTED_START -> ACTIVE
                direction_ok = True
                if config.DIRECTION_REQUIRED_FOR_ACTIVE:
                    direction_ok = (direction != Direction.UNKNOWN) or (
                        authoritative_trip_direction is not None
                    )

                if (
                    score >= config.ACTIVE_THRESHOLD
                    and is_in_window
                    and dwell.state == DwellState.MOVING
                    and route_match.status == RouteMatchStatus.MATCHED
                    and direction_ok
                ):
                    context.status = TripStatus.ACTIVE

                # SUSPECTED_START -> PLANNED (False start reset)
                elif score < config.RESET_THRESHOLD:
                    context.status = TripStatus.PLANNED
                    context.suspected_start_at = None
                elif context.suspected_start_at:
                    duration_suspected = (
                        obs_time - context.suspected_start_at
                    ).total_seconds() / 60.0
                    if duration_suspected > config.MAX_SUSPECTED_DURATION_MIN:
                        context.status = TripStatus.PLANNED
                        context.suspected_start_at = None

        return self._build_result(context, diagnostics)

    def _build_result(
        self, context: TripInferenceContext, diagnostics: List[TripInferenceDiagnostic]
    ) -> TripInferenceResult:
        return TripInferenceResult(
            status=context.status, score=context.score, context=context, diagnostics=diagnostics
        )
