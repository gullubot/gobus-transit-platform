import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.db.database import engine
from app.intelligence.crowding_engine import CrowdingEngine
from app.models.crowding import CrowdingReport
from app.models.enums import CrowdingSource, CrowdingState, Direction, TripStatus
from app.models.organization import Organization
from app.models.route import Route
from app.models.service import Service
from app.models.trip import Trip
from app.models.vehicle import Vehicle


@pytest.fixture(scope="function")
def session():
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="function")
def setup_test_data(session):
    org = Organization(name=f"Org A {uuid.uuid4()}")
    session.add(org)
    session.commit()
    route = Route(
        organization_id=org.id,
        route_code=f"R-{uuid.uuid4()}",
        route_name="Route",
        geometry="SRID=4326;LINESTRING(0 0, 1 1)",
    )
    session.add(route)
    session.commit()
    service = Service(
        organization_id=org.id,
        route_id=route.id,
        service_code=f"S-{uuid.uuid4()}",
        service_name="Service",
    )
    session.add(service)
    session.commit()
    vehicle = Vehicle(
        organization_id=org.id, vehicle_number=f"V-{uuid.uuid4()}", vehicle_type="BUS"
    )
    session.add(vehicle)
    session.commit()
    trip = Trip(
        organization_id=org.id,
        service_id=service.id,
        vehicle_id=vehicle.id,
        route_id=route.id,
        direction=Direction.A_TO_B,
        operating_date=datetime.now(timezone.utc).date(),
        planned_start_at=datetime.now(timezone.utc),
        status=TripStatus.ACTIVE,
    )
    session.add(trip)
    session.commit()

    return {"organization_id": org.id, "vehicle_id": vehicle.id, "trip_id": trip.id}


def test_aggregation_unknown_when_empty(session, setup_test_data):
    vehicle_id = setup_test_data["vehicle_id"]
    res = CrowdingEngine.aggregate_vehicle_crowding(session, vehicle_id)
    assert res.state == CrowdingState.UNKNOWN
    assert res.confidence == 0.0
    assert res.stale is True


def test_operator_authority_precedence(session, setup_test_data):
    vehicle_id = setup_test_data["vehicle_id"]
    org_id = setup_test_data["organization_id"]
    trip_id = setup_test_data["trip_id"]

    now = datetime.now(timezone.utc)

    # Insert passenger report
    r1 = CrowdingReport(
        report_id=uuid.uuid4(),
        organization_id=org_id,
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        crowding_state=CrowdingState.FULL,
        confidence=0.9,
        observed_at=now - timedelta(minutes=5),
        source_type=CrowdingSource.PASSENGER,
    )
    session.add(r1)

    # Insert operator report
    r2 = CrowdingReport(
        report_id=uuid.uuid4(),
        organization_id=org_id,
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        crowding_state=CrowdingState.LOW,
        confidence=0.9,
        observed_at=now - timedelta(minutes=2),
        source_type=CrowdingSource.OPERATOR,
    )
    session.add(r2)
    session.commit()

    res = CrowdingEngine.aggregate_vehicle_crowding(session, vehicle_id, reference_time=now)
    assert res.state == CrowdingState.LOW
    assert res.evidence_type == "LIVE_REPORTED"


def test_operator_authority_expiration(session, setup_test_data):
    vehicle_id = setup_test_data["vehicle_id"]
    org_id = setup_test_data["organization_id"]
    trip_id = setup_test_data["trip_id"]

    now = datetime.now(timezone.utc)

    # Operator report 15 mins ago (expired)
    r2 = CrowdingReport(
        report_id=uuid.uuid4(),
        organization_id=org_id,
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        crowding_state=CrowdingState.LOW,
        confidence=0.9,
        observed_at=now - timedelta(minutes=15),
        source_type=CrowdingSource.OPERATOR,
    )
    session.add(r2)

    # Passenger report 5 mins ago (live)
    r1 = CrowdingReport(
        report_id=uuid.uuid4(),
        organization_id=org_id,
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        crowding_state=CrowdingState.HIGH,
        confidence=0.9,
        observed_at=now - timedelta(minutes=5),
        source_type=CrowdingSource.PASSENGER,
    )
    session.add(r1)
    session.commit()

    res = CrowdingEngine.aggregate_vehicle_crowding(session, vehicle_id, reference_time=now)
    # Operator expired, so passenger takes over
    assert res.state == CrowdingState.HIGH
    assert res.evidence_type == "LIVE_REPORTED"


def test_decay_half_life(session, setup_test_data):
    vehicle_id = setup_test_data["vehicle_id"]
    org_id = setup_test_data["organization_id"]
    trip_id = setup_test_data["trip_id"]

    now = datetime.now(timezone.utc)

    # Operator report exactly 10 mins ago
    r = CrowdingReport(
        report_id=uuid.uuid4(),
        organization_id=org_id,
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        crowding_state=CrowdingState.LOW,
        confidence=0.9,
        observed_at=now - timedelta(minutes=10),
        source_type=CrowdingSource.OPERATOR,
    )
    session.add(r)
    session.commit()

    import math

    # Test 10 min decay
    res = CrowdingEngine.aggregate_vehicle_crowding(session, vehicle_id, reference_time=now)
    assert res.state == CrowdingState.LOW
    assert res.evidence_type == "LIVE_REPORTED"
    # Base is 0.90, decay is exp(-ln(2)/10 * 10) = 0.5. Final = 0.45
    assert math.isclose(res.confidence, 0.45, rel_tol=1e-5, abs_tol=1e-5)

    # Test 20 min decay (should be ~0.25 decay, 0.90 * 0.25 = 0.225)
    # At 20.01 mins, the operator report is no longer live, but acts as HISTORICAL_REPORTED
    r.observed_at = now - timedelta(minutes=20.01)
    session.commit()

    res_pass = CrowdingEngine.aggregate_vehicle_crowding(session, vehicle_id, reference_time=now)
    assert res_pass.evidence_type == "HISTORICAL_REPORTED"
    # decay = exp(-ln(2)/10 * 20.01) = 0.249826...
    # base = 0.90, final = 0.2248...
    expected_decay = math.exp(-(math.log(2) / 10) * 20.01)
    assert math.isclose(res_pass.confidence, 0.90 * expected_decay, rel_tol=1e-5, abs_tol=1e-5)


def test_passenger_aggregation_midpoint_rounding(session, setup_test_data):
    vehicle_id = setup_test_data["vehicle_id"]
    org_id = setup_test_data["organization_id"]
    trip_id = setup_test_data["trip_id"]

    now = datetime.now(timezone.utc)

    r1 = CrowdingReport(
        report_id=uuid.uuid4(),
        organization_id=org_id,
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        crowding_state=CrowdingState.LOW,  # 1
        confidence=0.9,
        observed_at=now - timedelta(minutes=1),
        source_type=CrowdingSource.PASSENGER,
    )
    session.add(r1)

    r2 = CrowdingReport(
        report_id=uuid.uuid4(),
        organization_id=org_id,
        vehicle_id=vehicle_id,
        trip_id=trip_id,
        crowding_state=CrowdingState.MODERATE,  # 2
        confidence=0.9,
        observed_at=now - timedelta(minutes=1),
        source_type=CrowdingSource.PASSENGER,
    )
    session.add(r2)
    session.commit()

    res = CrowdingEngine.aggregate_vehicle_crowding(session, vehicle_id, reference_time=now)
    # Average is 1.5. Midpoint rounding: floor(1.5 + 0.5) = 2 (MODERATE)
    assert res.state == CrowdingState.MODERATE
    assert res.evidence_type == "LIVE_REPORTED"
