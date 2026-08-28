from .config import (
    DWELL_EXIT_CONFIRMATION_OBSERVATIONS,
    DWELL_EXIT_SPEED_THRESHOLD_MPS,
    LARGE_PROGRESS_EXIT_M,
    NON_STOP_DWELL_CONFIRM_SECONDS,
    STOP_DWELL_CONFIRM_SECONDS,
    STOP_SPEED_THRESHOLD_MPS,
)
from .core_models import (
    DwellContext,
    DwellResult,
    DwellState,
    StopProgressResult,
    StopState,
    TelemetryPacket,
)


class DwellEngine:
    """
    Deterministically evaluates if a bus is moving or dwelling,
    separating bus-stop dwells from traffic-signal/non-stop dwells.
    """

    @staticmethod
    def evaluate_dwell(
        packet: TelemetryPacket,
        stop_result: StopProgressResult,
        context: DwellContext,
    ) -> DwellResult:
        if packet.speed_mps is None:
            return DwellResult(
                state=DwellState.UNKNOWN,
                duration_seconds=0.0,
                associated_stop_id=None,
                confidence=0.0,
                diagnostic_codes=["NO_SPEED_DATA"],
            )

        is_low_movement = packet.speed_mps <= STOP_SPEED_THRESHOLD_MPS

        # Handle Large Progress Exit first
        large_progress_jump = False
        if (
            stop_result.route_progress_m is not None
            and context.previous_route_progress_m is not None
        ):
            delta_prog = abs(stop_result.route_progress_m - context.previous_route_progress_m)
            if delta_prog >= LARGE_PROGRESS_EXIT_M and stop_result.progression_confidence >= 0.75:
                large_progress_jump = True

        context.previous_route_progress_m = stop_result.route_progress_m

        if not is_low_movement or large_progress_jump:
            # We observe movement
            if packet.speed_mps > DWELL_EXIT_SPEED_THRESHOLD_MPS or large_progress_jump:
                context.consecutive_movement_observations += 1
            else:
                # Modest speed, maybe noise.
                if context.previous_dwell_state != DwellState.MOVING:
                    # Still need strong movement to clear dwell
                    pass
                else:
                    context.consecutive_movement_observations = 1

            if (
                context.consecutive_movement_observations >= DWELL_EXIT_CONFIRMATION_OBSERVATIONS
                or large_progress_jump
            ):
                # Confirmed Moving
                context.stationary_since = None
                context.last_moving_at = packet.observed_at
                context.previous_dwell_state = DwellState.MOVING
                context.associated_stop_id = None
                context.last_observed_at = packet.observed_at

                return DwellResult(
                    state=DwellState.MOVING,
                    duration_seconds=0.0,
                    associated_stop_id=None,
                    confidence=1.0,
                    diagnostic_codes=[],
                )
            else:
                # Pending exit, maintain previous state (hysteresis)
                pass
        else:
            # Low movement detected
            context.consecutive_movement_observations = 0
            if context.stationary_since is None:
                context.stationary_since = packet.observed_at

        # We are stationary (or pending exit), calculate duration
        if context.stationary_since is not None:
            duration = (packet.observed_at - context.stationary_since).total_seconds()
        else:
            duration = 0.0

        # Evaluate states
        state = context.previous_dwell_state

        if duration >= STOP_DWELL_CONFIRM_SECONDS and stop_result.state == StopState.AT_STOP:
            state = DwellState.DWELL_AT_STOP
            context.associated_stop_id = stop_result.current_stop_id
        elif duration >= NON_STOP_DWELL_CONFIRM_SECONDS and stop_result.state in (
            StopState.BEFORE_STOP,
            StopState.PASSED_STOP,
        ):
            # Must NOT be UNKNOWN
            state = DwellState.DWELL_NON_STOP
            context.associated_stop_id = None
        elif stop_result.state == StopState.UNKNOWN:
            state = DwellState.UNKNOWN
            context.associated_stop_id = None

        # Update context
        context.previous_dwell_state = state
        context.last_observed_at = packet.observed_at

        return DwellResult(
            state=state,
            duration_seconds=max(0.0, duration),
            associated_stop_id=context.associated_stop_id,
            confidence=1.0 if state != DwellState.UNKNOWN else 0.0,
            diagnostic_codes=[],
        )
