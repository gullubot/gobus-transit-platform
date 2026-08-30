from datetime import datetime, timezone

from app.intelligence.core_models import Direction, RouteMatchContext
from app.intelligence.direction import DirectionEngine


def create_context(direction=Direction.UNKNOWN, progress=0.0, d_obs=1, opp_obs=0):
    return RouteMatchContext(
        route_id="r1",
        segment_index=0,
        route_progress_m=progress,
        direction=direction,
        matched_at=datetime.now(timezone.utc),
        confidence=0.9,
        direction_observations=d_obs,
        opposite_direction_observations=opp_obs,
    )


def test_direction_no_previous_context():
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(100.0, None)
    assert d == Direction.UNKNOWN
    assert d_obs == 1
    assert anchor == 100.0


def test_direction_a_to_b():
    ctx = create_context(Direction.UNKNOWN, 0.0)
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(50.0, ctx)
    assert d == Direction.A_TO_B
    assert d_obs == 1
    assert anchor == 50.0


def test_direction_b_to_a():
    ctx = create_context(Direction.UNKNOWN, 100.0)
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(50.0, ctx)
    assert d == Direction.B_TO_A
    assert d_obs == 1
    assert anchor == 50.0


def test_direction_hysteresis_small_delta():
    ctx = create_context(Direction.A_TO_B, 100.0, d_obs=5)
    # Move back by 5m (less than MIN_PROGRESS_DELTA = 15.0)
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(95.0, ctx)
    assert d == Direction.A_TO_B
    assert d_obs == 5  # Unchanged counters
    assert anchor == 100.0


def test_direction_single_noisy_reversal():
    ctx = create_context(Direction.A_TO_B, 100.0, d_obs=5)
    # Move back by 20m -> opposite observation
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(80.0, ctx)
    assert d == Direction.A_TO_B  # Should not flip immediately
    assert d_obs == 5
    assert opp == 1
    assert anchor == 80.0


def test_direction_multiple_consistent_reversal():
    # 2 opposite observations already
    ctx = create_context(Direction.A_TO_B, 100.0, d_obs=5, opp_obs=2)
    # 3rd opposite observation -> FLIP
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(80.0, ctx)
    assert d == Direction.B_TO_A
    assert d_obs == 1
    assert opp == 0
    assert anchor == 80.0


def test_direction_high_frequency_accumulation():
    """
    Test that high-frequency Android telemetry (e.g. 1 second interval, 10m delta)
    does not overwrite the anchor until the cumulative distance breaches 15m.
    """
    ctx = create_context(Direction.UNKNOWN, 0.0, d_obs=0)

    # Ping 1: 10m (sub-threshold). Anchor should NOT move.
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(10.0, ctx)
    assert d == Direction.UNKNOWN
    assert d_obs == 0
    assert anchor == 0.0

    # Update context with results (simulate orchestrator)
    ctx.direction = d
    ctx.direction_observations = d_obs
    ctx.opposite_direction_observations = opp
    ctx.route_progress_m = anchor

    # Ping 2: 20m (cumulative 20m > 15m). Anchor SHOULD move, observation recorded.
    d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(20.0, ctx)
    assert d == Direction.A_TO_B
    assert d_obs == 1
    assert anchor == 20.0

    ctx.direction = d
    ctx.direction_observations = d_obs
    ctx.opposite_direction_observations = opp
    ctx.route_progress_m = anchor

    # Simulate next pings to get a lock
    for progress in [30.0, 40.0, 50.0, 60.0]:
        d, d_obs, opp, anchor = DirectionEngine.infer_direction_state(progress, ctx)
        ctx.direction = d
        ctx.direction_observations = d_obs
        ctx.opposite_direction_observations = opp
        ctx.route_progress_m = anchor

    # By the end, we moved well over 3*15m, it should be locked
    assert d == Direction.A_TO_B
    assert d_obs >= 3
