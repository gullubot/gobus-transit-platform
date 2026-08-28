from datetime import datetime, timedelta, timezone

import pytest

from app.intelligence.core_models import (
    DwellContext,
    DwellState,
    StopProgressResult,
    StopState,
    TelemetryPacket,
)
from app.intelligence.dwell_detection import DwellEngine


@pytest.fixture
def current_time():
    return datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

def make_packet(time, speed):
    return TelemetryPacket(lat=12.0, lon=77.0, observed_at=time, accuracy_m=10.0, speed_mps=speed)

def test_moving(current_time):
    # 2 observations, speed > 0.55
    ctx = DwellContext()
    packet1 = make_packet(current_time, 10.0)
    res1 = DwellEngine.evaluate_dwell(packet1, StopProgressResult(StopState.BEFORE_STOP, None, "s1", None, 100.0, 0.9), ctx)
    assert res1.state == DwellState.UNKNOWN # need 2 observations, but wait, initial state is UNKNOWN

    # Actually, evaluate_dwell increments `consecutive_movement_observations`.
    # Let's say we started in MOVING.
    ctx = DwellContext(previous_dwell_state=DwellState.MOVING)
    packet2 = make_packet(current_time, 10.0)
    res2 = DwellEngine.evaluate_dwell(packet2, StopProgressResult(StopState.BEFORE_STOP, None, "s1", None, 120.0, 0.9), ctx)
    assert res2.state == DwellState.MOVING

def test_short_stop(current_time):
    # 5 seconds at a traffic light
    ctx = DwellContext(previous_dwell_state=DwellState.MOVING)
    p1 = make_packet(current_time, 0.0)
    DwellEngine.evaluate_dwell(p1, StopProgressResult(StopState.BEFORE_STOP, None, "s1", None, 100.0, 0.9), ctx)

    p2 = make_packet(current_time + timedelta(seconds=5), 0.0)
    res = DwellEngine.evaluate_dwell(p2, StopProgressResult(StopState.BEFORE_STOP, None, "s1", None, 100.0, 0.9), ctx)

    # Duration = 5s. threshold = 30s for non-stop. So state is still MOVING (waiting for dwell to confirm).
    # Wait, previous_dwell_state is what it returns until threshold is reached.
    assert res.state == DwellState.MOVING

def test_15s_stop(current_time):
    # 15s AT_STOP
    ctx = DwellContext(previous_dwell_state=DwellState.MOVING)
    p1 = make_packet(current_time, 0.0)
    DwellEngine.evaluate_dwell(p1, StopProgressResult(StopState.AT_STOP, "s1", "s2", None, 100.0, 0.9), ctx)

    p2 = make_packet(current_time + timedelta(seconds=15), 0.0)
    res = DwellEngine.evaluate_dwell(p2, StopProgressResult(StopState.AT_STOP, "s1", "s2", None, 100.0, 0.9), ctx)

    assert res.state == DwellState.DWELL_AT_STOP
    assert res.associated_stop_id == "s1"
    assert res.duration_seconds == 15.0

def test_30s_non_stop(current_time):
    # 30s BEFORE_STOP
    ctx = DwellContext(previous_dwell_state=DwellState.MOVING)
    p1 = make_packet(current_time, 0.0)
    DwellEngine.evaluate_dwell(p1, StopProgressResult(StopState.BEFORE_STOP, None, "s1", None, 100.0, 0.9), ctx)

    p2 = make_packet(current_time + timedelta(seconds=30), 0.0)
    res = DwellEngine.evaluate_dwell(p2, StopProgressResult(StopState.BEFORE_STOP, None, "s1", None, 100.0, 0.9), ctx)

    assert res.state == DwellState.DWELL_NON_STOP
    assert res.associated_stop_id is None

def test_large_progress_exit(current_time):
    # If progress jumps 30m, exit immediately
    ctx = DwellContext(
        previous_dwell_state=DwellState.DWELL_AT_STOP,
        stationary_since=current_time - timedelta(seconds=20),
        previous_route_progress_m=100.0
    )

    # Packet speed is 0.0! (noisy GPS while bus jumped)
    p = make_packet(current_time, 0.0)
    # But progress jumped to 135m! Conf is high.
    res = DwellEngine.evaluate_dwell(p, StopProgressResult(StopState.PASSED_STOP, None, "s2", "s1", 135.0, 0.9), ctx)

    assert res.state == DwellState.MOVING
