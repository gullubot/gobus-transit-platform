import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.database import engine
from app.models.enums import OrganizationStatus, OrganizationType, RouteStatus, StopStatus
from app.models.historical import HistoricalRouteTravel, HistoricalSegmentTravel
from app.models.organization import Organization
from app.models.route import Route, Stop
from app.repositories.historical_eta import (
    HistoricalETARepository,
    calculate_median_with_mad_filtering,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def test_data(db):
    org_a = Organization(
        id=str(uuid.uuid4()),
        name=f"Org A {uuid.uuid4()}",
        type=OrganizationType.PRIVATE,
        status=OrganizationStatus.ACTIVE,
    )
    route_a = Route(
        id=str(uuid.uuid4()),
        organization_id=org_a.id,
        route_code=f"R1_{uuid.uuid4()}",
        route_name="Route A",
        geometry="SRID=4326;LINESTRING(0 0, 1 1)",
        status=RouteStatus.ACTIVE,
    )
    stop_1 = Stop(
        id=str(uuid.uuid4()),
        organization_id=org_a.id,
        stop_code=f"S1_{uuid.uuid4()}",
        name="Stop 1",
        latitude=1.0,
        longitude=1.0,
        location="SRID=4326;POINT(1 1)",
        status=StopStatus.ACTIVE,
    )
    stop_2 = Stop(
        id=str(uuid.uuid4()),
        organization_id=org_a.id,
        stop_code=f"S2_{uuid.uuid4()}",
        name="Stop 2",
        latitude=2.0,
        longitude=2.0,
        location="SRID=4326;POINT(2 2)",
        status=StopStatus.ACTIVE,
    )
    db.add_all([org_a, route_a, stop_1, stop_2])
    db.commit()

    return {"org_a": org_a, "route_a": route_a, "stop_1": stop_1, "stop_2": stop_2}


def test_mad_filtering_insufficient_samples():
    samples = [10.0] * 19
    # min samples is 20
    assert calculate_median_with_mad_filtering(samples) is None


def test_mad_filtering_removes_outliers():
    # 20 samples of 100
    samples = [100.0] * 20
    # Add 2 extreme outliers
    samples.extend([500.0, 10.0])

    # M_initial = 100
    # abs_devs = twenty 0s, 400, 90. MAD = 0. safe_MAD = 1.0.
    # threshold = 3 * 1.0 = 3.0
    # filtered removes 500 and 10.
    # M_final = 100
    res = calculate_median_with_mad_filtering(samples)
    assert res == 100.0


def test_repo_segment_lookup_empty(db, test_data):
    repo = HistoricalETARepository(db)
    res = repo.get_historical_segment_baseline(
        test_data["org_a"].id,
        test_data["route_a"].id,
        "A_TO_B",
        test_data["stop_1"].id,
        test_data["stop_2"].id,
        1,
        "08:00",
    )
    assert res is None


def test_repo_segment_lookup_success(db, test_data):
    # insert data
    h = HistoricalSegmentTravel(
        id=str(uuid.uuid4()),
        organization_id=test_data["org_a"].id,
        route_id=test_data["route_a"].id,
        direction="A_TO_B",
        from_stop_id=test_data["stop_1"].id,
        to_stop_id=test_data["stop_2"].id,
        time_of_day_bucket="08:00",
        day_of_week=1,
        median_travel_seconds=120,
        median_destination_stop_dwell_seconds=20,
        sample_count=25,
    )
    db.add(h)
    db.commit()

    repo = HistoricalETARepository(db)
    res = repo.get_historical_segment_baseline(
        test_data["org_a"].id,
        test_data["route_a"].id,
        "A_TO_B",
        test_data["stop_1"].id,
        test_data["stop_2"].id,
        1,
        "08:00",
    )
    assert res == (120, 20)


def test_repo_route_lookup_success(db, test_data):
    # insert data
    h = HistoricalRouteTravel(
        id=str(uuid.uuid4()),
        organization_id=test_data["org_a"].id,
        route_id=test_data["route_a"].id,
        direction="A_TO_B",
        time_of_day_bucket="08:00",
        day_of_week=1,
        median_travel_seconds=3600,
        sample_count=20,
    )
    db.add(h)
    db.commit()

    repo = HistoricalETARepository(db)
    res = repo.get_historical_route_baseline(
        test_data["org_a"].id, test_data["route_a"].id, "A_TO_B", 1, "08:00"
    )
    assert res == 3600
