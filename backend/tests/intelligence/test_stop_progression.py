from datetime import datetime, timezone

import pytest

from app.intelligence.core_models import (
    Direction,
    RouteMatchResult,
    RouteMatchStatus,
    RouteStop,
    StopProgressContext,
    StopState,
    TelemetryPacket,
)
from app.intelligence.stop_progression import StopProgressionEngine


@pytest.fixture
def current_time():
    return datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def make_stops():
    return [
        RouteStop("s1", 1, 100.0, 60, 12.0, 77.0),
        RouteStop("s2", 2, 500.0, 120, 12.004, 77.0),
        RouteStop("s3", 3, 1000.0, 180, 12.008, 77.0),
    ]


def make_packet(lat, lon, speed, acc=10.0):
    return TelemetryPacket(
        lat=lat,
        lon=lon,
        observed_at=datetime.now(timezone.utc),
        accuracy_m=acc,
        speed_mps=speed,
        heading=0.0,
    )


def make_match(progress, dir=Direction.A_TO_B, conf=0.9):
    return RouteMatchResult(
        status=RouteMatchStatus.MATCHED,
        route_id="r1",
        segment_index=0,
        projected_lat=0.0,
        projected_lon=0.0,
        cross_track_distance_m=0.0,
        route_progress_m=progress,
        match_confidence=conf,
        direction=dir,
    )


def test_approaching_stop():
    stops = make_stops()
    # Tol = 30m. Enter margin = 10m.
    # We enter AT_STOP when diff <= 20m.
    # At 70m progress, diff is 30m > 20m. So BEFORE_STOP.
    packet = make_packet(12.0, 77.0, 10.0)
    match = make_match(70.0)
    res = StopProgressionEngine.evaluate_progression(packet, match, stops)
    assert res.state == StopState.BEFORE_STOP
    assert res.next_stop_id == "s1"


def test_exact_stop():
    stops = make_stops()
    packet = make_packet(12.0, 77.0, 0.0)  # low speed
    match = make_match(100.0)

    # Needs confirmed arrival or spatial proximity.
    # The spatial proximity is 0.0 (exact lat/lon match with s1).
    res = StopProgressionEngine.evaluate_progression(packet, match, stops)
    assert res.state == StopState.AT_STOP
    assert res.current_stop_id == "s1"


def test_passing_stop():
    stops = make_stops()
    packet = make_packet(12.0, 77.0, 10.0)
    # Passed requires diff > tol + pass_margin (30 + 15 = 45m).
    # Progress = 146m. Diff = +46m > 45m.
    match = make_match(146.0)

    ctx = StopProgressContext(stop_states={"s1": StopState.AT_STOP})
    res = StopProgressionEngine.evaluate_progression(packet, match, stops, ctx)
    assert res.state == StopState.BEFORE_STOP  # for s2
    assert res.previous_stop_id == "s1"
    assert res.next_stop_id == "s2"


def test_enter_exit_hysteresis():
    stops = make_stops()
    packet = make_packet(12.0, 77.0, 0.0)
    # Inside EXIT band, but outside ENTER band
    # tol = 30. EXIT band = 30 + 10 = 40m.
    # Diff = 35m.
    match = make_match(135.0)

    # If previously BEFORE, it shouldn't enter AT yet because 35m > 20m.
    ctx = StopProgressContext(stop_states={"s1": StopState.BEFORE_STOP})
    res1 = StopProgressionEngine.evaluate_progression(packet, match, stops, ctx)
    assert res1.state == StopState.BEFORE_STOP

    # If previously AT, it should remain AT because 35m <= 40m.
    ctx2 = StopProgressContext(stop_states={"s1": StopState.AT_STOP})
    res2 = StopProgressionEngine.evaluate_progression(packet, match, stops, ctx2)
    assert res2.state == StopState.AT_STOP


def test_b_to_a_direction():
    stops = make_stops()
    # In B_TO_A, stop distances are exactly the same.
    # Progress decreases.
    # We are at 1050m (before s3 at 1000m).
    packet = make_packet(12.0, 77.0, 10.0)
    match = make_match(1050.0, dir=Direction.B_TO_A)

    res = StopProgressionEngine.evaluate_progression(packet, match, stops)
    # Stop 3 is 1000m. 1050m is > 1000m + (30 - 10) -> BEFORE_STOP for B_TO_A
    assert res.state == StopState.BEFORE_STOP
    assert res.next_stop_id == "s3"

    # Progress 950m is passed s3.
    # Passed: current < stop - tol - margin = 1000 - 30 - 15 = 955m.
    # 950m < 955m, so passed.
    match2 = make_match(950.0, dir=Direction.B_TO_A)
    ctx = StopProgressContext(stop_states={"s3": StopState.AT_STOP})
    res2 = StopProgressionEngine.evaluate_progression(packet, match2, stops, ctx)
    assert res2.state == StopState.BEFORE_STOP  # for s2
    assert res2.previous_stop_id == "s3"
    assert res2.next_stop_id == "s2"


def test_multi_stop_gap_strong_evidence():
    stops = make_stops()
    packet = make_packet(12.0, 77.0, 10.0)
    match = make_match(1100.0, conf=0.9)
    # Jumped from s1 (progress ~100m) straight to after s3.
    ctx = StopProgressContext(
        stop_states={
            "s1": StopState.PASSED_STOP,
            "s2": StopState.BEFORE_STOP,
            "s3": StopState.BEFORE_STOP,
        }
    )

    res = StopProgressionEngine.evaluate_progression(packet, match, stops, ctx)
    assert res.state == StopState.PASSED_STOP
    assert res.previous_stop_id == "s3"


def test_multi_stop_gap_weak_evidence():
    stops = make_stops()
    packet = make_packet(12.0, 77.0, 10.0)
    # Weak match confidence (0.4)
    match = make_match(1100.0, conf=0.4)
    ctx = StopProgressContext(
        stop_states={
            "s1": StopState.PASSED_STOP,
            "s2": StopState.BEFORE_STOP,
            "s3": StopState.BEFORE_STOP,
        }
    )

    res = StopProgressionEngine.evaluate_progression(packet, match, stops, ctx)
    # Should not fabricate PASSED_STOP for s2 and s3. Will return UNKNOWN.
    # The current state will be UNKNOWN because of the gap ambiguity.
    assert "WEAK_GAP_EVIDENCE" in res.diagnostic_codes


def test_confirmed_passage_backward_noise():
    stops = make_stops()
    packet = make_packet(12.0, 77.0, 10.0)
    # Previously passed s1. Now noise pulls us back to 90m.
    match = make_match(90.0)
    ctx = StopProgressContext(stop_states={"s1": StopState.PASSED_STOP})

    res = StopProgressionEngine.evaluate_progression(packet, match, stops, ctx)
    # Must NOT revert to BEFORE_STOP for s1.
    assert res.previous_stop_id == "s1"
    assert res.state == StopState.BEFORE_STOP  # for s2!
    assert res.next_stop_id == "s2"
