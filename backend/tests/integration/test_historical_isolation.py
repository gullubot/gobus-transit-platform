import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import engine
from app.models.enums import OrganizationStatus, OrganizationType, RouteStatus, StopStatus
from app.models.historical import HistoricalSegmentTravel
from app.models.organization import Organization
from app.models.route import Route, Stop

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session


@pytest.fixture
def test_data(db):
    suffix = uuid.uuid4().hex[:6]

    org_a = Organization(
        id=uuid.uuid4(),
        name=f"Org A Iso {suffix}",
        type=OrganizationType.MUNICIPAL,
        status=OrganizationStatus.ACTIVE,
    )
    org_b = Organization(
        id=uuid.uuid4(),
        name=f"Org B Iso {suffix}",
        type=OrganizationType.MUNICIPAL,
        status=OrganizationStatus.ACTIVE,
    )
    db.add_all([org_a, org_b])
    db.commit()

    route_a = Route(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        route_code=f"RA_{suffix}",
        route_name="Route A",
        geometry="LINESTRING(0 0, 1 1)",
        status=RouteStatus.ACTIVE,
    )
    route_b = Route(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        route_code=f"RB_{suffix}",
        route_name="Route B",
        geometry="LINESTRING(0 0, 1 1)",
        status=RouteStatus.ACTIVE,
    )
    db.add_all([route_a, route_b])

    stop_a = Stop(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        stop_code=f"SA_{suffix}",
        name="Stop A",
        location="POINT(0 0)",
        status=StopStatus.ACTIVE,
    )
    stop_b = Stop(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        stop_code=f"SB_{suffix}",
        name="Stop B",
        location="POINT(1 1)",
        status=StopStatus.ACTIVE,
    )
    db.add_all([stop_a, stop_b])
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "route_a": route_a,
        "route_b": route_b,
        "stop_a": stop_a,
        "stop_b": stop_b,
    }


def _create_historical(org_id, route_id, stop_id):
    return HistoricalSegmentTravel(
        id=uuid.uuid4(),
        organization_id=org_id,
        route_id=route_id,
        from_stop_id=stop_id,
        to_stop_id=stop_id,  # just use same stop for both to simplify
        direction="A_TO_B",
        time_of_day_bucket="MORNING",
        day_of_week=1,
        median_travel_seconds=300,
        median_destination_stop_dwell_seconds=30,
        sample_count=20,
    )


def test_1_org_a_route_a_stop_a_success(db, test_data):
    # TEST 1: Org A + Route A + Stop A = SUCCESS
    h = _create_historical(test_data["org_a"].id, test_data["route_a"].id, test_data["stop_a"].id)
    db.add(h)
    db.commit()


def test_2_org_a_route_b_stop_a_reject(db, test_data):
    # TEST 2: Org A + Route B = REJECTED
    h = _create_historical(test_data["org_a"].id, test_data["route_b"].id, test_data["stop_a"].id)
    db.add(h)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_3_org_a_route_a_stop_a_success_redundant(db, test_data):
    # TEST 3: Org A + Stop A = SUCCESS
    # (already tested in 1, doing it again with different id to be sure)
    h = _create_historical(test_data["org_a"].id, test_data["route_a"].id, test_data["stop_a"].id)
    h.day_of_week = 2  # ensure unique constraint doesn't block it
    db.add(h)
    db.commit()


def test_4_org_a_route_a_stop_b_reject(db, test_data):
    # TEST 4: Org A + Stop B = REJECTED
    h = _create_historical(test_data["org_a"].id, test_data["route_a"].id, test_data["stop_b"].id)
    db.add(h)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_5_org_a_route_a_stop_b_reject_again(db, test_data):
    # TEST 5: Org A + Route A + Stop B = REJECTED
    h = _create_historical(test_data["org_a"].id, test_data["route_a"].id, test_data["stop_b"].id)
    db.add(h)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_6_org_b_route_b_stop_b_success(db, test_data):
    # TEST 6: Org B + Route B + Stop B = SUCCESS
    h = _create_historical(test_data["org_b"].id, test_data["route_b"].id, test_data["stop_b"].id)
    db.add(h)
    db.commit()
