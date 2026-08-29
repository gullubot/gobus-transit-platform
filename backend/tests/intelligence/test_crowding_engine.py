import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
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


def test_case_11_12_13_trip_resolution():
    """Case 11, 12, 13: Passenger trip resolution boundaries."""
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.db.seed import ORG_ID, ROUTE_R1_ID, SVC_AC4B_ID
    from app.repositories.crowding_repository import get_active_trip_for_vehicle

    unique_vehicle_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        session.execute(
            text(
                f"INSERT INTO vehicles (id, organization_id, vehicle_number, vehicle_type, status, created_at, updated_at) VALUES ('{unique_vehicle_id}', '{ORG_ID}', 'V-{uuid.uuid4().hex[:6]}', 'BUS', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )

        # Zero trips (Case 12)
        trip_id_none = get_active_trip_for_vehicle(session, ORG_ID, unique_vehicle_id, now)
        assert trip_id_none is None

        # Single trip (Case 11)
        trip_1 = str(uuid.uuid4())
        device_1 = str(uuid.uuid4())
        op_1 = str(uuid.uuid4())
        session.execute(
            text(
                f"INSERT INTO users (id, organization_id, name, phone, role, password_hash, status, created_at, updated_at) VALUES ('{op_1}', '{ORG_ID}', 'Driver', '1', 'DRIVER', '1', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO devices (id, organization_id, device_name, platform, status, created_at, updated_at) VALUES ('{device_1}', '{ORG_ID}', 'D', 'ANDROID', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO trips (id, organization_id, service_id, vehicle_id, route_id, direction, operating_date, planned_start_at, status, created_at, updated_at) VALUES ('{trip_1}', '{ORG_ID}', '{SVC_AC4B_ID}', '{unique_vehicle_id}', '{ROUTE_R1_ID}', 'A_TO_B', '2026-08-26', now(), 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO tracking_sessions (id, device_id, operator_id, trip_id, started_at, status, created_at, updated_at) VALUES ('{uuid.uuid4()}', '{device_1}', '{op_1}', '{trip_1}', '{(now - timedelta(minutes=30)).isoformat()}', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.commit()

        trip_id_single = get_active_trip_for_vehicle(session, ORG_ID, unique_vehicle_id, now)
        assert str(trip_id_single) == trip_1

        # Multiple overlapping trips (Case 13)
        trip_2 = str(uuid.uuid4())
        session.execute(
            text(
                f"INSERT INTO trips (id, organization_id, service_id, vehicle_id, route_id, direction, operating_date, planned_start_at, status, created_at, updated_at) VALUES ('{trip_2}', '{ORG_ID}', '{SVC_AC4B_ID}', '{unique_vehicle_id}', '{ROUTE_R1_ID}', 'B_TO_A', '2026-08-26', now(), 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO tracking_sessions (id, device_id, operator_id, trip_id, started_at, status, created_at, updated_at) VALUES ('{uuid.uuid4()}', '{device_1}', '{op_1}', '{trip_2}', '{(now - timedelta(minutes=20)).isoformat()}', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.commit()

        trip_id_multi = get_active_trip_for_vehicle(session, ORG_ID, unique_vehicle_id, now)
        assert trip_id_multi is None

        # Cleanup
        session.execute(text(f"DELETE FROM tracking_sessions WHERE operator_id = '{op_1}'"))
        session.execute(text(f"DELETE FROM trips WHERE id IN ('{trip_1}', '{trip_2}')"))
        session.execute(text(f"DELETE FROM devices WHERE id = '{device_1}'"))
        session.execute(text(f"DELETE FROM users WHERE id = '{op_1}'"))
        session.execute(text(f"DELETE FROM vehicles WHERE id = '{unique_vehicle_id}'"))
        session.commit()


def test_case_14_trip_a_not_converted_to_trip_b():
    """Case 14: Report for Trip A at observed_at is not silently converted to Trip B active at received_at."""  # noqa: E501
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.db.seed import ORG_ID, ROUTE_R1_ID, SVC_AC4B_ID
    from app.repositories.crowding_repository import get_active_trip_for_vehicle

    unique_vehicle_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    observed = now - timedelta(minutes=30)

    with Session(engine) as session:
        session.execute(
            text(
                f"INSERT INTO vehicles (id, organization_id, vehicle_number, vehicle_type, status, created_at, updated_at) VALUES ('{unique_vehicle_id}', '{ORG_ID}', 'V-{uuid.uuid4().hex[:6]}', 'BUS', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        trip_a = str(uuid.uuid4())
        trip_b = str(uuid.uuid4())
        device_id = str(uuid.uuid4())
        op_id = str(uuid.uuid4())
        session.execute(
            text(
                f"INSERT INTO users (id, organization_id, name, phone, role, password_hash, status, created_at, updated_at) VALUES ('{op_id}', '{ORG_ID}', 'Driver', '1', 'DRIVER', '1', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO devices (id, organization_id, device_name, platform, status, created_at, updated_at) VALUES ('{device_id}', '{ORG_ID}', 'D', 'ANDROID', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )

        # Trip A was active at observed
        session.execute(
            text(
                f"INSERT INTO trips (id, organization_id, service_id, vehicle_id, route_id, direction, operating_date, planned_start_at, status, created_at, updated_at) VALUES ('{trip_a}', '{ORG_ID}', '{SVC_AC4B_ID}', '{unique_vehicle_id}', '{ROUTE_R1_ID}', 'A_TO_B', '2026-08-26', now(), 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO tracking_sessions (id, device_id, operator_id, trip_id, started_at, ended_at, status, created_at, updated_at) VALUES ('{uuid.uuid4()}', '{device_id}', '{op_id}', '{trip_a}', '{(observed - timedelta(minutes=10)).isoformat()}', '{(observed + timedelta(minutes=10)).isoformat()}', 'ENDED', now(), now())"  # noqa: E501
            )
        )

        # Trip B is active at now (received)
        session.execute(
            text(
                f"INSERT INTO trips (id, organization_id, service_id, vehicle_id, route_id, direction, operating_date, planned_start_at, status, created_at, updated_at) VALUES ('{trip_b}', '{ORG_ID}', '{SVC_AC4B_ID}', '{unique_vehicle_id}', '{ROUTE_R1_ID}', 'B_TO_A', '2026-08-26', now(), 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO tracking_sessions (id, device_id, operator_id, trip_id, started_at, status, created_at, updated_at) VALUES ('{uuid.uuid4()}', '{device_id}', '{op_id}', '{trip_b}', '{(now - timedelta(minutes=5)).isoformat()}', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.commit()

        trip_resolved = get_active_trip_for_vehicle(session, ORG_ID, unique_vehicle_id, observed)
        assert str(trip_resolved) == trip_a

        # Cleanup
        session.execute(text(f"DELETE FROM tracking_sessions WHERE operator_id = '{op_id}'"))
        session.execute(text(f"DELETE FROM trips WHERE id IN ('{trip_a}', '{trip_b}')"))
        session.execute(text(f"DELETE FROM devices WHERE id = '{device_id}'"))
        session.execute(text(f"DELETE FROM users WHERE id = '{op_id}'"))
        session.execute(text(f"DELETE FROM vehicles WHERE id = '{unique_vehicle_id}'"))
        session.commit()


def test_case_15_unresolved_excluded():
    """Case 15: Unresolved report (trip_id=None) is excluded from LIVE aggregation."""
    import uuid
    from datetime import datetime, timezone

    from app.db.seed import ORG_ID, VEH_IDS
    from app.intelligence.crowding_engine import CrowdingEngine
    from app.models.crowding import CrowdingReport
    from app.models.enums import CrowdingSource, CrowdingState

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.execute(text("DELETE FROM crowding_reports"))
        r = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=ORG_ID,
            vehicle_id=VEH_IDS["PNB005781"],
            trip_id=None,
            crowding_state=CrowdingState.FULL,
            confidence=1.0,
            observed_at=now,
            source_type=CrowdingSource.PASSENGER,
        )
        session.add(r)
        session.commit()

        res = CrowdingEngine.aggregate_vehicle_crowding(
            session, VEH_IDS["PNB005781"], reference_time=now
        )
        assert res.state == CrowdingState.UNKNOWN

        session.delete(r)
        session.commit()


def test_case_22_confidence_cutoff():
    """Case 22: final_confidence < 0.20 is excluded from LIVE aggregation."""
    import uuid
    from datetime import datetime, timezone

    from app.db.seed import ORG_ID, ROUTE_R1_ID, SVC_AC4B_ID
    from app.intelligence.crowding_engine import CrowdingEngine
    from app.models.crowding import CrowdingReport
    from app.models.enums import CrowdingSource, CrowdingState

    v_id = str(uuid.uuid4())
    TRIP_COMPLETED_ID = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.execute(text("DELETE FROM crowding_reports"))
        session.execute(
            text(
                f"INSERT INTO vehicles (id, organization_id, vehicle_number, vehicle_type, status, created_at, updated_at) VALUES ('{v_id}', '{ORG_ID}', 'V-{uuid.uuid4().hex[:6]}', 'BUS', 'ACTIVE', now(), now())"  # noqa: E501
            )
        )
        session.execute(
            text(
                f"INSERT INTO trips (id, organization_id, service_id, vehicle_id, route_id, direction, operating_date, planned_start_at, status, created_at, updated_at) VALUES ('{TRIP_COMPLETED_ID}', '{ORG_ID}', '{SVC_AC4B_ID}', '{v_id}', '{ROUTE_R1_ID}', 'A_TO_B', '2026-08-26', now(), 'COMPLETED', now(), now())"  # noqa: E501
            )
        )
        from datetime import timedelta

        # 18 mins ago -> final_conf = 0.60 * 0.287 = 0.17 < 0.20
        observed = now - timedelta(minutes=18)
        r = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=ORG_ID,
            vehicle_id=v_id,
            trip_id=TRIP_COMPLETED_ID,
            crowding_state=CrowdingState.FULL,
            confidence=0.80,
            observed_at=observed,
            source_type=CrowdingSource.PASSENGER,
        )
        session.add(r)
        session.commit()

        try:
            res = CrowdingEngine.aggregate_vehicle_crowding(session, v_id, reference_time=now)
            assert res.state == CrowdingState.UNKNOWN
        finally:
            session.delete(r)
            session.execute(text("DELETE FROM crowding_reports"))
            session.execute(text(f"DELETE FROM trips WHERE id = '{TRIP_COMPLETED_ID}'"))
            session.execute(text(f"DELETE FROM vehicles WHERE id = '{v_id}'"))
            session.commit()


def test_case_29_weighted_passenger_aggregation():
    """Case 29: Exact passenger weighted mean math."""
    import uuid
    from datetime import datetime, timezone

    from app.db.seed import ORG_ID, TRIP_COMPLETED_ID, VEH_IDS
    from app.intelligence.crowding_engine import CrowdingEngine
    from app.models.crowding import CrowdingReport
    from app.models.enums import CrowdingSource, CrowdingState

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.execute(text("DELETE FROM crowding_reports"))
        r1 = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=ORG_ID,
            vehicle_id=VEH_IDS["PNB005781"],
            trip_id=TRIP_COMPLETED_ID,
            crowding_state=CrowdingState.LOW,  # value 1
            confidence=1.0,  # passenger base 0.6
            observed_at=now,
            source_type=CrowdingSource.PASSENGER,
        )
        r2 = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=ORG_ID,
            vehicle_id=VEH_IDS["PNB005781"],
            trip_id=TRIP_COMPLETED_ID,
            crowding_state=CrowdingState.HIGH,  # value 3
            confidence=0.5,  # passenger base 0.3
            observed_at=now,
            source_type=CrowdingSource.PASSENGER,
        )
        session.add_all([r1, r2])
        session.commit()

        res = CrowdingEngine.aggregate_vehicle_crowding(
            session, VEH_IDS["PNB005781"], reference_time=now
        )
        # Weighted mean: (1*0.6 + 3*0.3)/(0.6+0.3) = (0.6 + 0.9)/0.9 = 1.5/0.9 = 1.666
        # Rounding: floor(1.666 + 0.5) = floor(2.166) = 2 (MODERATE)
        assert res.state == CrowdingState.MODERATE

        session.delete(r1)
        session.delete(r2)
        session.commit()
