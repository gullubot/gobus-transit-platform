from typing import Optional, Tuple

from .config import (
    DIRECTION_CONFIRMATION_OBSERVATIONS,
    DIRECTION_MIN_PROGRESS_DELTA,
)
from .core_models import Direction, RouteMatchContext


class DirectionEngine:
    @staticmethod
    def infer_direction_state(
        current_progress: float,
        previous_context: Optional[RouteMatchContext],
    ) -> Tuple[Direction, int, int, float]:
        """
        Determines the current direction and state counters.
        Returns: (new_direction, direction_observations, opposite_observations, anchor_progress)
        """
        if not previous_context:
            return Direction.UNKNOWN, 1, 0, current_progress

        progress_delta = current_progress - previous_context.route_progress_m

        if abs(progress_delta) < DIRECTION_MIN_PROGRESS_DELTA:
            # Too small to be confident, keep state and KEEP the old anchor
            return (
                previous_context.direction,
                previous_context.direction_observations,
                previous_context.opposite_direction_observations,
                previous_context.route_progress_m,
            )

        implied_dir = Direction.A_TO_B if progress_delta > 0 else Direction.B_TO_A

        if previous_context.direction == Direction.UNKNOWN:
            return implied_dir, 1, 0, current_progress

        if implied_dir == previous_context.direction:
            return implied_dir, previous_context.direction_observations + 1, 0, current_progress

        # Opposite direction observed
        new_opp_count = previous_context.opposite_direction_observations + 1
        if new_opp_count >= DIRECTION_CONFIRMATION_OBSERVATIONS:
            # Flip!
            return implied_dir, 1, 0, current_progress

        # Keep previous, but record opposite observation, and UPDATE ANCHOR
        return (
            previous_context.direction,
            previous_context.direction_observations,
            new_opp_count,
            current_progress,
        )
