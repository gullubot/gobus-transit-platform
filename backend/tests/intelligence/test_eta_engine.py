import math
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.intelligence.core_models import (
    CanonicalState,
    CanonicalStateContext,
    Direction,
    DwellState,
    ETAStatus,
    RouteStop,
)
from app.intelligence.eta_engine import ETAEngine
from app.repositories.historical_eta import HistoricalETARepository


@pytest.fixture
def mock_repo():
    return Mock(spec=HistoricalETARepository)


@pytest.fixture
def engine(mock_repo):
    return ETAEngine(repo=mock_repo)


@pytest.fixture
def base_time():
    return datetime.now(timezone.utc)


@pytest.fixture
def route_topology():
    return [
        RouteStop(
            id="s1",
            sequence_number=1,
            distance_from_start=0.0,
            nominal_travel_time_seconds=0,
            lat=1.0,
            lon=1.0,
        ),
        RouteStop(
            id="s2",
            sequence_number=2,
            distance_from_start=500.0,
            nominal_travel_time_seconds=60,
            lat=2.0,
            lon=2.0,
        ),
        RouteStop(
            id="s3",
            sequence_number=3,
            distance_from_start=1200.0,
            nominal_travel_time_seconds=150,
            lat=3.0,
            lon=3.0,
        ),
    ]


def _build_canonical(
    state: CanonicalState = CanonicalState.LIVE,
    direction: Direction = Direction.A_TO_B,
    speed_mps: float = 10.0,
    progress: float = 100.0,
    dwell: DwellState = DwellState.MOVING,
    conf: str = "HIGH",
    observed: datetime = None,
    trip_status: str = None,
) -> CanonicalStateContext:
    return CanonicalStateContext(
        organization_id="org1",
        vehicle_id="v1",
        route_id="r1",
        direction=direction.value,
        lat=1.1,
        lon=1.1,
        speed_mps=speed_mps,
        route_progress_m=progress,
        dwell_state=dwell,
        state=state,
        confidence=conf,
        last_observed_at=observed or datetime.now(timezone.utc),
        trip_status=trip_status,
    )


def test_01_next_stop_live(engine, route_topology, mock_repo, base_time):
    # progress=100. next stop s2 at 500. dist=400. speed=10.
    c = _build_canonical(progress=100.0, speed_mps=10.0, observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = None

    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    assert res.target_stop_id == "s2"
    assert res.status == ETAStatus.LIVE
    assert res.eta_seconds == 40  # 400 / 10
    assert res.fallback_level == 1  # no history -> LEVEL 1


def test_02_zero_speed_uses_hierarchy(engine, route_topology, mock_repo, base_time):
    # speed 0 -> falls back to history.
    c = _build_canonical(progress=100.0, speed_mps=0.0, observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = (
        100,
        15,
    )  # 100s travel time, 15s dwell

    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    assert res.status == ETAStatus.FALLBACK
    assert res.fallback_level == 2
    # dist = 400. hist speed = 400 / 100 = 4. eta = 400/4 = 100s
    assert res.eta_seconds == 100


def test_03_zero_speed_no_history_produces_unavailable(
    engine, route_topology, mock_repo, base_time
):
    c = _build_canonical(progress=100.0, speed_mps=0.0, observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = None
    mock_repo.get_historical_route_baseline.return_value = None

    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)
    assert res.status == ETAStatus.UNAVAILABLE
    assert res.fallback_level == 5
    assert "NO_USABLE_SPEED" in res.reason_codes


def test_04_target_passed(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(progress=600.0, speed_mps=10.0, observed=base_time)
    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    assert res.status == ETAStatus.UNAVAILABLE
    assert "TARGET_ALREADY_PASSED" in res.reason_codes


def test_05_intermediate_dwell_included_destination_excluded(
    engine, route_topology, mock_repo, base_time
):
    c = _build_canonical(progress=100.0, speed_mps=10.0, observed=base_time)

    def side_effect(*args):
        # args[4] is to_stop_id
        if args[4] == "s2":
            return (40, 20)  # 40s travel, 20s dwell
        elif args[4] == "s3":
            return (70, 30)  # 70s travel, 30s dwell
        return None

    mock_repo.get_historical_segment_baseline.side_effect = side_effect

    # 400m to s2, 700m from s2 to s3
    res = engine.calculate_eta(c, route_topology, "s3", 1200.0, "08:00", 1)

    # Segment 1 (curr to s2): 400m. hist speed = 400/40 = 10. Blend: 0.85*10 + 0.15*10 = 10. Time = 40s.
    # Intermediate dwell at s2 = 20s.
    # Segment 2 (s2 to s3): 700m. hist speed = 700/70 = 10. Blend: 10. Time = 70s.
    # Destination dwell at s3 (30s) is EXCLUDED.
    # Total ETA = 40 + 20 + 70 = 130
    assert res.eta_seconds == 130


def test_06_non_stop_dwell_widens_uncertainty(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(
        progress=100.0, speed_mps=10.0, dwell=DwellState.DWELL_NON_STOP, observed=base_time
    )
    mock_repo.get_historical_segment_baseline.return_value = None

    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    assert res.eta_seconds == 40
    # Base variance normally = (1 - conf)*eta.
    # Conf = 0.85 * 1.0 * 0.7 (dwell) * 0.9 (level 1) = 0.5355
    # low = 18 * 0.5 = 9. up = 18 * 1.5 = 27
    # + NON STOP DWELL = max(0.4 * 40, 300) = 300. up = 327.
    assert res.upper_bound_seconds >= 300
    assert "DWELL_NON_STOP" in res.reason_codes


def test_07_route_fallback(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(progress=600.0, speed_mps=0.0, observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = None
    mock_repo.get_historical_route_baseline.return_value = 3600  # 1 hour for whole route

    res = engine.calculate_eta(c, route_topology, "s3", 1200.0, "08:00", 1)

    # Progress = 600/1200 = 0.5
    # Target = 1200/1200 = 1.0
    # Remaining fraction = 0.5
    # ETA = 0.5 * 3600 = 1800
    assert res.status == ETAStatus.FALLBACK
    assert res.fallback_level == 3
    assert res.eta_seconds == 1800


def test_08_stale_never_live(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(
        state=CanonicalState.STALE, progress=100.0, speed_mps=10.0, observed=base_time
    )
    mock_repo.get_historical_segment_baseline.return_value = (100, 15)

    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    assert res.status == ETAStatus.FALLBACK
    # stale uses only history
    # 400m / (400/100 = 4) = 100s
    assert res.eta_seconds == 100


def test_09_degraded_blends_and_widens(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(
        state=CanonicalState.DEGRADED, progress=100.0, speed_mps=10.0, observed=base_time
    )
    # hist = 200s travel time for 400m -> 2m/s
    mock_repo.get_historical_segment_baseline.return_value = (200, 0)

    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    assert res.status == ETAStatus.DEGRADED
    # blend degraded: 0.4*10 + 0.6*2 = 4 + 1.2 = 5.2 m/s
    # 400 / 5.2 = 76s
    assert abs(res.eta_seconds - 76) <= 1
    # Degraded uncertainty min 120 added to upper
    assert res.upper_bound_seconds >= 120


def test_10_negative_and_nan_protections(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(progress=100.0, speed_mps=math.nan, observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = (100, 0)

    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)
    assert not math.isnan(res.eta_seconds)
    assert not math.isnan(res.upper_bound_seconds)
    assert res.eta_seconds >= 0


def test_11_terminal_completion(engine, route_topology, mock_repo, base_time):
    # progress=1190. target s3 at 1200. remaining=10m. DWELL_AT_STOP.
    c = _build_canonical(
        progress=1190.0,
        speed_mps=0.0,
        dwell=DwellState.DWELL_AT_STOP,
        observed=base_time,
        trip_status="COMPLETED",
    )
    c.current_stop_id = "s3"

    res = engine.calculate_eta(c, route_topology, "s3", 1200.0, "08:00", 1)

    assert res.eta_seconds == 0
    assert "AT_TARGET" in res.reason_codes


def test_11b_terminal_near_but_not_completed(engine, route_topology, mock_repo, base_time):
    # AT_STOP near terminal, but NOT COMPLETED. ETA MUST NOT BE 0.
    c = _build_canonical(
        progress=1190.0,
        speed_mps=0.0,
        dwell=DwellState.DWELL_AT_STOP,
        observed=base_time,
        trip_status="NOT_COMPLETED",
    )
    c.current_stop_id = "s3"
    mock_repo.get_historical_segment_baseline.return_value = (100, 10)
    res = engine.calculate_eta(c, route_topology, "s3", 1200.0, "08:00", 1)
    assert res.eta_seconds > 0


def test_12_direction_b_to_a(engine, route_topology, mock_repo, base_time):
    # Route in B_TO_A
    c = _build_canonical(
        direction=Direction.B_TO_A, progress=1200.0, speed_mps=10.0, observed=base_time
    )
    mock_repo.get_historical_segment_baseline.return_value = None
    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)
    # wait, B_TO_A means distance decreases! But my route_topology has distance_from_start ascending.
    # Actually, ETAEngine uses `target_stop.distance_from_start - canonical.route_progress_m`.
    # For B_TO_A, it uses `canonical.route_progress_m - target_stop.distance_from_start`.
    assert res.status == ETAStatus.LIVE
    assert res.eta_seconds == 70  # (1200 - 500) / 10


def test_13_missing_speed(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(progress=100.0, speed_mps=None, observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = (100, 10)
    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)
    assert res.status == ETAStatus.FALLBACK
    assert res.fallback_level == 2


def test_14_ewma_updates(engine, route_topology, mock_repo, base_time):
    mock_repo.get_historical_segment_baseline.return_value = (100, 10)
    # First call sets EWMA
    c1 = _build_canonical(progress=100.0, speed_mps=20.0, observed=base_time)
    engine.calculate_eta(c1, route_topology, "s2", 1200.0, "08:00", 1)

    # Second call updates EWMA
    c2 = _build_canonical(progress=200.0, speed_mps=10.0, observed=base_time)
    res = engine.calculate_eta(c2, route_topology, "s2", 1200.0, "08:00", 1)

    # EWMA = 0.35 * 10 + 0.65 * 20 = 16.5
    # Hist = 5. Blend = 0.85*16.5 + 0.15*5 = 14.775
    # Dist = 300. ETA = 300 / 14.775 = 20.3 -> 20s
    assert res.eta_seconds == 20


def test_15_offline_never_live(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(
        state=CanonicalState.OFFLINE, progress=100.0, speed_mps=10.0, observed=base_time
    )
    mock_repo.get_historical_segment_baseline.return_value = (100, 10)
    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)
    assert res.status == ETAStatus.FALLBACK
    assert res.fallback_level == 2


def test_16_abandoned_trip(engine, route_topology, mock_repo, base_time):
    c = _build_canonical(
        state=CanonicalState.NOT_ACTIVE, progress=100.0, speed_mps=10.0, observed=base_time
    )
    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)
    assert res.status == ETAStatus.UNAVAILABLE


def test_17_exact_uncertainty_formula(engine, route_topology, mock_repo, base_time):
    # progress=100. target=s2 (dist 400m). speed=10m/s. eta=40s.
    c = _build_canonical(progress=100.0, speed_mps=10.0, conf="MEDIUM", observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = (100, 10)  # Provides fallback_level 0
    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    # Blend speed = 0.85*10 + 0.15*4 = 9.1 m/s
    # Dist = 400m. ETA = 400 / 9.1 = 43.9s -> 43s
    # MEDIUM = 0.60
    # base = (1 - 0.60) * 43 = 17.2
    # low_unc = 17.2 * 0.5 = 8.6
    # up_unc = 17.2 * 1.5 = 25.8
    assert res.eta_seconds == 43
    assert res.confidence_score == 0.60
    assert res.lower_bound_seconds == int(43 - 8.6)
    assert res.upper_bound_seconds == int(43 + 25.8)


def test_18_zero_speed_does_not_fabricate_movement(engine, route_topology, mock_repo, base_time):
    # zero speed must not be set to 1.0 m/s
    c = _build_canonical(progress=100.0, speed_mps=0.0, observed=base_time)
    mock_repo.get_historical_segment_baseline.return_value = (200, 20)  # 200s travel time
    res = engine.calculate_eta(c, route_topology, "s2", 1200.0, "08:00", 1)

    # if zero speed was overridden to 1 m/s, ETA would blend.
    # since it's zero, it's skipped. fallback used!
    assert res.fallback_level == 2
    assert res.eta_seconds == 200  # entirely from historical segment
