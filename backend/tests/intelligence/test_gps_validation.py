import math
from datetime import datetime, timedelta, timezone

import pytest

from app.intelligence.config import (
    CONFIDENCE_PENALTY_LOW_GPS,
)
from app.intelligence.core_models import (
    PreviousStateContext,
    TelemetryPacket,
    ValidationDiagnostic,
    ValidationStatus,
)
from app.intelligence.gps_validation import GPSValidator


@pytest.fixture
def current_time():
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def create_packet(
    current_time, offset_seconds=0, lat=12.0, lon=77.0, acc=10.0, speed=10.0, heading=0.0
):
    return TelemetryPacket(
        lat=lat,
        lon=lon,
        observed_at=current_time + timedelta(seconds=offset_seconds),
        accuracy_m=acc,
        speed_mps=speed,
        heading=heading,
    )


def create_context(current_time, offset_seconds=-10, lat=12.0, lon=77.0, speed=10.0, heading=0.0):
    return PreviousStateContext(
        lat=lat,
        lon=lon,
        observed_at=current_time + timedelta(seconds=offset_seconds),
        speed_mps=speed,
        heading=heading,
        route_progress=0.5,
    )


def test_coordinates_zero(current_time):
    packet = create_packet(current_time, lat=0.0, lon=0.0)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.REJECTED
    assert ValidationDiagnostic.COARSE_OUT_OF_BOUNDS in report.diagnostic_codes


def test_coordinates_out_of_bounds(current_time):
    # Europe
    packet = create_packet(current_time, lat=50.0, lon=10.0)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.REJECTED
    assert ValidationDiagnostic.COARSE_OUT_OF_BOUNDS in report.diagnostic_codes


def test_coordinates_valid(current_time):
    packet = create_packet(current_time, lat=12.0, lon=77.0)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.VALID


def test_timestamp_future_beyond_skew(current_time):
    packet = create_packet(current_time, offset_seconds=10)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.REJECTED
    assert ValidationDiagnostic.FUTURE_TIMESTAMP in report.diagnostic_codes


def test_timestamp_future_within_skew(current_time):
    packet = create_packet(current_time, offset_seconds=3)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.VALID


def test_timestamp_current(current_time):
    packet = create_packet(current_time, offset_seconds=0)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.VALID
    assert not report.is_historical


def test_timestamp_historical(current_time):
    packet = create_packet(current_time, offset_seconds=-1000)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.VALID
    assert report.is_historical


def test_speed_normal(current_time):
    ctx = create_context(current_time, lat=12.0, lon=77.0)
    # Move ~100m in 10 seconds -> 10m/s
    # roughly 1 degree lat is 111km. 100m is 0.0009 degrees
    packet = create_packet(current_time, lat=12.0009, lon=77.0, speed=10.0)
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    assert report.status == ValidationStatus.VALID


def test_speed_suspicious(current_time):
    ctx = create_context(current_time, lat=12.0, lon=77.0)
    # Move ~400m in 10 seconds -> 40m/s (144km/h)
    packet = create_packet(current_time, lat=12.0036, lon=77.0, speed=40.0)
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    assert report.status == ValidationStatus.SUSPICIOUS
    assert ValidationDiagnostic.HIGH_IMPLIED_SPEED in report.diagnostic_codes


def test_speed_impossible(current_time):
    ctx = create_context(current_time, lat=12.0, lon=77.0)
    # Move ~1000m in 10 seconds -> 100m/s
    packet = create_packet(current_time, lat=12.0090, lon=77.0, speed=100.0)
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    assert report.status == ValidationStatus.REJECTED
    assert ValidationDiagnostic.IMPOSSIBLE_SPEED in report.diagnostic_codes


def test_speed_missing_previous_state(current_time):
    packet = create_packet(current_time, lat=12.0, lon=77.0, speed=10.0)
    report = GPSValidator.validate_packet(packet, current_time, None)
    assert report.status == ValidationStatus.VALID


@pytest.mark.parametrize(
    "acc, expected_score_approx",
    [
        (5.0, 1.0),
        (10.0, 1.0),
        (30.0, 0.75),
        (50.0, 0.50),
        (75.0, 0.25),
        (100.0, 0.0),
        (150.0, 0.0),
    ],
)
def test_accuracy_mappings(current_time, acc, expected_score_approx):
    packet = create_packet(current_time, acc=acc)
    # Just need accuracy component. We can back-calculate from base confidence since others are 1.0
    # or just ensure it runs properly.
    report = GPSValidator.validate_packet(packet, current_time)
    # Without prev state: speed_score, continuity_score unavailable.
    # Available: accuracy (0.4), timestamp (0.15).
    # sum = 0.55.
    # base = acc_score * (0.4/0.55) + 1.0 * (0.15/0.55)
    effective_acc_w = 0.40 / 0.55
    effective_time_w = 0.15 / 0.55
    expected_conf = expected_score_approx * effective_acc_w + 1.0 * effective_time_w
    if acc >= 50.0:
        expected_conf *= CONFIDENCE_PENALTY_LOW_GPS

    assert math.isclose(report.confidence_score, expected_conf, abs_tol=0.01)


def test_accuracy_missing(current_time):
    packet = create_packet(current_time, acc=None)
    report = GPSValidator.validate_packet(packet, current_time)
    assert report.status == ValidationStatus.VALID
    assert report.confidence_score == 1.0


@pytest.mark.parametrize(
    "delta, expected_speed_score",
    [
        (0.0, 1.0),
        (5.0, 1.0),
        (10.0, 0.5),
        (15.0, 0.0),
        (20.0, 0.0),
    ],
)
def test_speed_consistency(current_time, delta, expected_speed_score):
    ctx = create_context(current_time, lat=12.0, lon=77.0, speed=10.0)
    # Move ~100m in 10s -> implied is approx 10.0025
    # Let's calculate the exact distance in the test to set reported speed precisely
    from app.intelligence.gps_validation import haversine_distance

    distance = haversine_distance(12.0, 77.0, 12.0009, 77.0)
    exact_implied_speed = distance / 10.0

    reported_speed = exact_implied_speed + delta
    packet = create_packet(current_time, lat=12.0009, lon=77.0, speed=reported_speed)
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    if delta >= 15.0:
        assert ValidationDiagnostic.SPEED_INCONSISTENCY in report.diagnostic_codes


def test_acceleration_small_dt(current_time):
    ctx = create_context(current_time, offset_seconds=-1, lat=12.0, lon=77.0, speed=0.0)
    packet = create_packet(current_time, lat=12.0001, lon=77.0, speed=10.0)  # 11m in 1s = 11m/s
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    # Since dt=1 < 2.0, acceleration should not be calculated, so no HIGH_IMPLIED_ACCELERATION
    assert ValidationDiagnostic.HIGH_IMPLIED_ACCELERATION not in report.diagnostic_codes


def test_plausible_acceleration(current_time):
    ctx = create_context(current_time, offset_seconds=-10, lat=12.0, lon=77.0, speed=10.0)
    packet = create_packet(
        current_time, lat=12.0012, lon=77.0, speed=13.0
    )  # ~133m in 10s = 13.3m/s
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    assert ValidationDiagnostic.HIGH_IMPLIED_ACCELERATION not in report.diagnostic_codes


def test_implausible_acceleration(current_time):
    ctx = create_context(current_time, offset_seconds=-2, lat=12.0, lon=77.0, speed=0.0)
    packet = create_packet(
        current_time, lat=12.0003, lon=77.0, speed=15.0
    )  # ~33m in 2s = 16.5m/s. Accel = 8.25m/s2
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    assert ValidationDiagnostic.HIGH_IMPLIED_ACCELERATION in report.diagnostic_codes
    assert report.status == ValidationStatus.SUSPICIOUS


def test_impossible_jump_excellent_accuracy(current_time):
    ctx = create_context(current_time, offset_seconds=-1, lat=12.0, lon=77.0)
    packet = create_packet(current_time, lat=12.1, lon=77.0, acc=5.0)  # 11km in 1s -> IMPOSSIBLE
    report = GPSValidator.validate_packet(packet, current_time, ctx)
    assert report.status == ValidationStatus.REJECTED
