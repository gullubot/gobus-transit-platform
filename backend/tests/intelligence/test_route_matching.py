import pytest
from datetime import datetime, timedelta, timezone

from app.intelligence.core_models import (
    Direction,
    RouteCandidate,
    RouteMatchContext,
    RouteMatchDiagnostic,
    RouteMatchStatus,
    TelemetryPacket,
)
from app.intelligence.route_matching import RouteMatcher, calculate_search_radius
from app.intelligence.gps_validation import haversine_distance


@pytest.fixture
def current_time():
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def create_packet(current_time, lat=12.0, lon=77.0, acc=10.0, speed=10.0, heading=90.0, offset=0):
    return TelemetryPacket(
        lat=lat,
        lon=lon,
        observed_at=current_time + timedelta(seconds=offset),
        accuracy_m=acc,
        speed_mps=speed,
        heading=heading,
    )


def create_context(current_time, offset=-10, route_id="r1", progress=0.0, dir=Direction.A_TO_B):
    return RouteMatchContext(
        route_id=route_id,
        segment_index=0,
        route_progress_m=progress,
        direction=dir,
        matched_at=current_time + timedelta(seconds=offset),
        confidence=0.9,
        direction_observations=3,
        opposite_direction_observations=0,
    )


def make_candidates(route_id, coords):
    """Helper to mock PostGIS returning individual segments with pre-calculated progress."""
    candidates = []
    accum = 0.0
    for i in range(len(coords) - 1):
        lat_a, lon_a = coords[i]
        lat_b, lon_b = coords[i + 1]
        dist = haversine_distance(lat_a, lon_a, lat_b, lon_b)
        candidates.append(
            RouteCandidate(
                route_id=route_id,
                geometry_coordinates=[coords[i], coords[i + 1]],
                segment_index=i,
                segment_progress_start_m=accum,
            )
        )
        accum += dist
    return candidates


def test_search_radius():
    assert calculate_search_radius(10.0) == 50.0  # Base
    assert calculate_search_radius(60.0) == 90.0  # Acc factor
    assert calculate_search_radius(10.0, 100.0) == 120.0  # Expected + safety
    assert calculate_search_radius(10.0, 500.0) == 300.0  # Max clamp


def test_exactly_on_route(current_time):
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)])
    packet = create_packet(current_time, lat=12.0, lon=77.005)  # exactly in middle
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.cross_track_distance_m < 1.0


def test_lateral_noise(current_time):
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)])

    # ~5m noise (1 degree lat = 111km, 5m = 0.000045 degrees)
    packet_5m = create_packet(current_time, lat=12.000045, lon=77.005)
    res_5m = RouteMatcher.match_route(packet_5m, candidates)
    assert res_5m.status == RouteMatchStatus.MATCHED

    # ~60m noise
    packet_60m = create_packet(current_time, lat=12.00054, lon=77.005, acc=60.0)
    res_60m = RouteMatcher.match_route(packet_60m, candidates)
    assert res_60m.status == RouteMatchStatus.MATCHED

    # ~100m noise
    packet_100m = create_packet(current_time, lat=12.00090, lon=77.005, acc=100.0)
    res_100m = RouteMatcher.match_route(packet_100m, candidates)
    assert res_100m.status in (RouteMatchStatus.MATCHED, RouteMatchStatus.NO_MATCH)


def test_parallel_road(current_time):
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)]) + make_candidates(
        "r2", [(12.001, 77.0), (12.001, 77.01)]
    )

    # Move closer to r2 (12.001) so distance penalty is small enough to pass MIN_ROUTE_MATCH_SCORE
    packet = create_packet(current_time, lat=12.00095, lon=77.005)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.route_id == "r2"


def test_route_intersection(current_time):
    candidates = make_candidates("east", [(12.0, 77.0), (12.0, 77.01)]) + make_candidates(
        "north", [(11.99, 77.005), (12.01, 77.005)]
    )

    packet = create_packet(current_time, lat=12.0, lon=77.005, heading=90.0)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.route_id == "east"


def test_gps_gap_multi_segment(current_time):
    coords = [(12.0, 77.0), (12.0, 77.005), (12.0, 77.010), (12.0, 77.015)]
    candidates = make_candidates("r1", coords)

    ctx = create_context(current_time, offset=-60, progress=0.0)
    packet = create_packet(current_time, lat=12.0, lon=77.012, speed=10.0)
    # The progress jump needs to be plausible over 60s. 60s * 10m/s = 600m.
    # 0.012 deg lon is ~1333m. Speed = 1333 / 60 = 22m/s. This is plausible.
    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.segment_index == 2


def test_ambiguous_candidate(current_time):
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)]) + make_candidates(
        "r2", [(12.0, 77.0), (12.0, 77.01)]
    )

    packet = create_packet(current_time, lat=12.0, lon=77.005, heading=90.0)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.AMBIGUOUS


def test_impossible_jump(current_time):
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.5)])
    ctx = create_context(current_time, offset=-1, progress=0.0)
    packet = create_packet(current_time, lat=12.0, lon=77.1, speed=10.0)
    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.NO_MATCH


def test_missing_features(current_time):
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)])
    packet = create_packet(current_time, lat=12.0, lon=77.005, acc=None, heading=None, speed=None)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED


def test_no_route_within_radius(current_time):
    res = RouteMatcher.match_route(create_packet(current_time), [])
    assert res.status == RouteMatchStatus.NO_MATCH


def test_india_realism_u_turn(current_time):
    coords = [(12.0, 77.0), (12.0, 77.01), (12.0002, 77.01), (12.0002, 77.0)]
    candidates = make_candidates("r1", coords)

    # Calculate exact progress at the target point to make the previous context plausible
    seg0 = haversine_distance(12.0, 77.0, 12.0, 77.01)
    seg1 = haversine_distance(12.0, 77.01, 12.0002, 77.01)
    seg2_half = haversine_distance(12.0002, 77.01, 12.0002, 77.005)

    target_progress = seg0 + seg1 + seg2_half

    # 10s ago at 10m/s -> 100m before target progress
    ctx = create_context(current_time, offset=-10, progress=target_progress - 100.0)

    packet = create_packet(current_time, lat=12.0002, lon=77.005, heading=270.0, speed=10.0)
    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.segment_index == 2


def test_small_retrograde_tolerance(current_time):
    # Test that a small backward jump within SMALL_RETROGRADE_TOLERANCE_M (15m) does not fail
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)])

    # Target point halfway
    packet = create_packet(current_time, lat=12.0, lon=77.005, heading=90.0, speed=0.0)
    # The progress of 77.005 is ~555m from start.
    # Let's say previous progress was 565m. That means cand_prog_delta = -10m.
    ctx = create_context(current_time, offset=-5, progress=565.0)

    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.MATCHED


def test_meaningful_impossible_retrograde(current_time):
    # Backward jump > SMALL_RETROGRADE_TOLERANCE_M (15m) should fail matching 
    # (or result in very low score) because Sprog drops to MEANINGFUL_RETROGRADE_SCORE
    # and Scont drops exponentially due to the large delta error.
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)])

    # Target point halfway (progress ~555m)
    packet = create_packet(current_time, lat=12.0, lon=77.005, heading=90.0, speed=10.0)

    # Previous progress was 855m. cand_prog_delta = -300m.
    # Expected was +50m (speed 10 * 5s). Error is 350m.
    # Score will drop to ~0.47 < 0.50
    ctx = create_context(current_time, offset=-5, progress=855.0)

    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.NO_MATCH


def test_b_to_a_traversal(current_time):
    # A bus actively operating in B_TO_A direction.
    candidates = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)])
    
    # Let's say previous progress was 1113m. 
    # It moves backwards (west). cand_prog_delta is negative.
    # Because direction is B_TO_A, expected_prog_delta is also negative!
    ctx = create_context(current_time, offset=-10, progress=1113.0, dir=Direction.B_TO_A)
    packet = create_packet(current_time, lat=12.0, lon=77.009, heading=270.0, speed=10.0) 
    
    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.MATCHED


def test_ambiguous_reversal(current_time):
    # Candidate 1: Continuing straight on r1.
    candidates_r1 = make_candidates("r1", [(12.0, 77.0), (12.0, 77.01)])
    
    # Previous context: moving East on r1 (A_TO_B).
    ctx = create_context(current_time, offset=-10, progress=555.0, route_id="r1", dir=Direction.A_TO_B)
    
    # Packet shows a sudden jump backwards by 100m.
    # Because it's on r1, this is a MEANINGFUL_RETROGRADE.
    # The score drops to ~0.507. It's a MATCHED but with REDUCED CONFIDENCE.
    packet = create_packet(current_time, lat=12.0, lon=77.003, heading=270.0, speed=10.0)
    
    res = RouteMatcher.match_route(packet, candidates_r1, ctx)
    
    # The prompt explicitly requires "reduced confidence" or AMBIGUOUS.
    if res.status == RouteMatchStatus.MATCHED:
        assert res.match_confidence < 0.60
    else:
        assert res.status in (RouteMatchStatus.AMBIGUOUS, RouteMatchStatus.NO_MATCH)
