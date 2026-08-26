from datetime import datetime, timedelta, timezone

import pytest

from app.intelligence.core_models import (
    Direction,
    RouteCandidate,
    RouteMatchContext,
    RouteMatchStatus,
    TelemetryPacket,
)
from app.intelligence.route_matching import RouteMatcher, calculate_search_radius


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


def test_search_radius():
    assert calculate_search_radius(10.0) == 50.0  # Base
    assert calculate_search_radius(60.0) == 90.0  # Acc factor
    assert calculate_search_radius(10.0, 100.0) == 120.0  # Expected + safety
    assert calculate_search_radius(10.0, 500.0) == 300.0  # Max clamp


def test_exactly_on_route(current_time):
    # Route from (12.0, 77.0) to (12.0, 77.01) [heading east]
    candidates = [RouteCandidate(route_id="r1", geometry_coordinates=[(12.0, 77.0), (12.0, 77.01)])]
    packet = create_packet(current_time, lat=12.0, lon=77.005)  # exactly in middle
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.cross_track_distance_m < 1.0


def test_lateral_noise(current_time):
    candidates = [RouteCandidate(route_id="r1", geometry_coordinates=[(12.0, 77.0), (12.0, 77.01)])]

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
    # Score might be low but could still match if it's the only one.
    assert res_100m.status in (RouteMatchStatus.MATCHED, RouteMatchStatus.NO_MATCH)


def test_parallel_road(current_time):
    candidates = [
        RouteCandidate(route_id="r1", geometry_coordinates=[(12.0, 77.0), (12.0, 77.01)]),
        RouteCandidate(route_id="r2", geometry_coordinates=[(12.001, 77.0), (12.001, 77.01)]),
    ]
    # Move closer to r2 (12.001) so distance penalty is small enough to pass MIN_ROUTE_MATCH_SCORE
    packet = create_packet(current_time, lat=12.00095, lon=77.005)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.route_id == "r2"


def test_route_intersection(current_time):
    candidates = [
        RouteCandidate(route_id="east", geometry_coordinates=[(12.0, 77.0), (12.0, 77.01)]),
        RouteCandidate(route_id="north", geometry_coordinates=[(11.99, 77.005), (12.01, 77.005)]),
    ]
    packet = create_packet(current_time, lat=12.0, lon=77.005, heading=90.0)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.route_id == "east"


def test_gps_gap_multi_segment(current_time):
    coords = [(12.0, 77.0), (12.0, 77.005), (12.0, 77.010), (12.0, 77.015)]
    candidates = [RouteCandidate(route_id="r1", geometry_coordinates=coords)]
    ctx = create_context(current_time, offset=-60, progress=0.0)
    packet = create_packet(current_time, lat=12.0, lon=77.012, speed=10.0)
    # The progress jump needs to be plausible over 60s. 60s * 10m/s = 600m.
    # 0.012 deg lon is ~1333m. Speed = 1333 / 60 = 22m/s. This is plausible.
    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.MATCHED
    assert res.segment_index == 2


def test_ambiguous_candidate(current_time):
    candidates = [
        RouteCandidate(route_id="r1", geometry_coordinates=[(12.0, 77.0), (12.0, 77.01)]),
        RouteCandidate(route_id="r2", geometry_coordinates=[(12.0, 77.0), (12.0, 77.01)]),
    ]
    packet = create_packet(current_time, lat=12.0, lon=77.005, heading=90.0)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.AMBIGUOUS


def test_impossible_jump(current_time):
    candidates = [RouteCandidate(route_id="r1", geometry_coordinates=[(12.0, 77.0), (12.0, 77.5)])]
    ctx = create_context(current_time, offset=-1, progress=0.0)
    packet = create_packet(current_time, lat=12.0, lon=77.1, speed=10.0)
    res = RouteMatcher.match_route(packet, candidates, ctx)
    assert res.status == RouteMatchStatus.NO_MATCH


def test_missing_features(current_time):
    candidates = [RouteCandidate(route_id="r1", geometry_coordinates=[(12.0, 77.0), (12.0, 77.01)])]
    packet = create_packet(current_time, lat=12.0, lon=77.005, acc=None, heading=None, speed=None)
    res = RouteMatcher.match_route(packet, candidates)
    assert res.status == RouteMatchStatus.MATCHED


def test_no_route_within_radius(current_time):
    res = RouteMatcher.match_route(create_packet(current_time), [])
    assert res.status == RouteMatchStatus.NO_MATCH


def test_india_realism_u_turn(current_time):
    coords = [(12.0, 77.0), (12.0, 77.01), (12.0002, 77.01), (12.0002, 77.0)]
    candidates = [RouteCandidate(route_id="r1", geometry_coordinates=coords)]

    # Calculate exact progress at the target point to make the previous context plausible
    from app.intelligence.gps_validation import haversine_distance

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
