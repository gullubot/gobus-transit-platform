"""
Transit Platform — Operator Duty & Trip Tracking Lifecycle Tests.

BUILD 2: Tests for assignment retrieval and trip tracking start/end endpoints.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.database import engine
from app.db.seed import (
    DEV_DRIVER_ID,
    ORG_ID,
    TRIP_PLANNED_ID,
    USER_DEPOT_ADMIN_ID,
    USER_FLEET_ADMIN_ID,
    seed_dev_data,
)
from app.main import app
from app.models.device import Device, DeviceStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        seed_dev_data(session)


def get_driver_token() -> str:
    """Helper to authenticate DRV001 and get access token."""
    response = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "DRV001", "password": "operator123"},
    )
    return response.json()["access_token"]


def get_conductor_token() -> str:
    """Helper to authenticate CND001 and get access token."""
    response = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "CND001", "password": "operator123"},
    )
    return response.json()["access_token"]


def test_get_operator_assignment_success():
    """CASE A: Driver retrieves assigned trip duty with vehicle, route, and device info."""
    token = get_driver_token()
    response = client.get(
        "/api/operator/me/assignment",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["trip_id"] == str(TRIP_PLANNED_ID)
    assert data["service_code"] == "AC4B"
    assert data["vehicle_number"] == "PNB005234"
    assert data["route_code"] == "R1"
    assert data["direction"] == "A_TO_B"
    assert data["operator_role"] == "DRIVER"
    assert data["assigned_device_status"] == "ACTIVE"
    assert data["vehicle_type"] == "BUS"
    assert data["origin_stop_name"] == "City Center"
    assert data["destination_stop_name"] == "Tech Park"


def test_start_and_end_trip_tracking_lifecycle():
    """CASE A (Tracking Start/End): Driver starts tracking for assigned trip, then ends it."""
    token = get_driver_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Start tracking
    start_resp = client.post(f"/api/trips/{TRIP_PLANNED_ID}/start", headers=headers)
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["status"] == "ACTIVE"
    assert start_data["trip_id"] == str(TRIP_PLANNED_ID)
    assert "tracking_session_id" in start_data

    session_id = start_data["tracking_session_id"]

    # 2. Duplicate start is idempotent — returns the existing active session
    dup_start_resp = client.post(f"/api/trips/{TRIP_PLANNED_ID}/start", headers=headers)
    assert dup_start_resp.status_code == 200
    assert dup_start_resp.json()["tracking_session_id"] == session_id

    # 3. End tracking
    end_resp = client.post(f"/api/trips/{TRIP_PLANNED_ID}/end", headers=headers)
    assert end_resp.status_code == 200
    end_data = end_resp.json()
    assert end_data["status"] == "ENDED"
    assert "ended_at" in end_data


def test_start_unassigned_trip_rejected():
    """CASE C & F: Starting tracking for an unassigned / fake trip returns 403 Forbidden."""
    token = get_driver_token()
    random_trip_id = uuid.uuid4()
    response = client.post(
        f"/api/trips/{random_trip_id}/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_conductor_assignment_retrieval():
    """Conductor retrieves their assigned duty with CONDUCTOR role."""
    token = get_conductor_token()
    response = client.get(
        "/api/operator/me/assignment",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["operator_role"] == "CONDUCTOR"
    assert data["service_code"] == "AC4B"


def test_fleet_admin_rejected_from_operator_endpoints():
    """CASE G: Fleet admin accounts are rejected from operator tracking endpoints."""
    admin_token = create_access_token(
        subject=str(USER_FLEET_ADMIN_ID),
        claims={"role": "FLEET_ADMIN", "org_id": str(ORG_ID)},
    )
    response = client.get(
        "/api/operator/me/assignment",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403
    assert "not authorized for operator tracking" in response.json()["detail"]


def test_depot_admin_rejected_from_operator_endpoints():
    """CASE H: Depot admin accounts are rejected from operator tracking endpoints."""
    depot_token = create_access_token(
        subject=str(USER_DEPOT_ADMIN_ID),
        claims={"role": "DEPOT_ADMIN", "org_id": str(ORG_ID)},
    )
    response = client.get(
        "/api/operator/me/assignment",
        headers={"Authorization": f"Bearer {depot_token}"},
    )
    assert response.status_code == 403
    assert "not authorized for operator tracking" in response.json()["detail"]


def test_inactive_device_rejected_from_tracking():
    """CASE I: An assigned device with REVOKED status is rejected on start tracking."""
    try:
        with Session(engine) as session:
            device = session.get(Device, DEV_DRIVER_ID)
            if device:
                device.status = DeviceStatus.REVOKED
                session.commit()

        token = get_driver_token()
        response = client.post(
            f"/api/trips/{TRIP_PLANNED_ID}/start",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "not active" in response.json()["detail"].lower()
    finally:
        with Session(engine) as session:
            device = session.get(Device, DEV_DRIVER_ID)
            if device:
                device.status = DeviceStatus.ACTIVE
                session.commit()


def test_get_operator_todays_trips_chronological_and_is_next():
    """Verify Today's Trips returns today's trips chronologically, excludes yesterday, and flags correct is_next."""
    from datetime import date, datetime, timedelta, timezone
    from app.models.trip import Trip, TripAssignment
    from app.models.enums import Direction, TripStatus, AssignmentStatus, UserRole, VerificationStatus
    from app.models.user import User, OperatorProfile
    from app.db.seed import ORG_ID, SVC_AC4B_ID, ROUTE_R1_ID, VEH_IDS

    today = date.today()
    now = datetime.now(timezone.utc)
    chrono_driver_id = uuid.uuid4()

    with Session(engine) as session:
        # Create isolated driver user
        test_driver = User(
            id=chrono_driver_id,
            organization_id=ORG_ID,
            role=UserRole.DRIVER,
            name="Chrono Test Driver",
            phone="+919999900001",
            status="ACTIVE",
        )
        test_profile = OperatorProfile(
            user_id=chrono_driver_id,
            employee_code="DRV_TEST_CHRONO",
            operator_type="DRIVER",
            verification_status=VerificationStatus.VERIFIED,
        )
        session.add(test_driver)
        session.add(test_profile)

        # Create 3 trips for today: 1 completed earlier, 1 upcoming planned, 1 later planned
        trip_completed = Trip(
            organization_id=ORG_ID,
            service_id=SVC_AC4B_ID,
            vehicle_id=VEH_IDS["PNB005234"],
            route_id=ROUTE_R1_ID,
            direction=Direction.A_TO_B,
            operating_date=today,
            planned_start_at=now - timedelta(hours=3),
            actual_start_at=now - timedelta(hours=3),
            actual_end_at=now - timedelta(hours=2),
            status=TripStatus.COMPLETED,
        )
        trip_next = Trip(
            organization_id=ORG_ID,
            service_id=SVC_AC4B_ID,
            vehicle_id=VEH_IDS["PNB005234"],
            route_id=ROUTE_R1_ID,
            direction=Direction.A_TO_B,
            operating_date=today,
            planned_start_at=now + timedelta(hours=1),
            status=TripStatus.PLANNED,
        )
        trip_later = Trip(
            organization_id=ORG_ID,
            service_id=SVC_AC4B_ID,
            vehicle_id=VEH_IDS["PNB005234"],
            route_id=ROUTE_R1_ID,
            direction=Direction.B_TO_A,
            operating_date=today,
            planned_start_at=now + timedelta(hours=4),
            status=TripStatus.PLANNED,
        )
        session.add_all([trip_completed, trip_next, trip_later])
        session.flush()

        session.add_all([
            TripAssignment(
                trip_id=trip_completed.id,
                user_id=chrono_driver_id,
                role="DRIVER",
                assigned_at=now - timedelta(hours=4),
                status=AssignmentStatus.ENDED,
            ),
            TripAssignment(
                trip_id=trip_next.id,
                user_id=chrono_driver_id,
                role="DRIVER",
                assigned_at=now - timedelta(hours=4),
                status=AssignmentStatus.ASSIGNED,
            ),
            TripAssignment(
                trip_id=trip_later.id,
                user_id=chrono_driver_id,
                role="DRIVER",
                assigned_at=now - timedelta(hours=4),
                status=AssignmentStatus.ASSIGNED,
            ),
        ])
        session.commit()

        next_id = trip_next.id
        completed_id = trip_completed.id
        later_id = trip_later.id

    try:
        token = create_access_token(str(chrono_driver_id), claims={"role": "DRIVER", "org_id": str(ORG_ID)})
        response = client.get(
            "/api/operator/me/trips",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        trips = response.json()
        assert len(trips) == 3

        # Check chronological ordering
        assert [t["trip_id"] for t in trips] == [str(completed_id), str(next_id), str(later_id)]

        # Check is_next flag
        for t in trips:
            if t["trip_id"] == str(next_id):
                assert t["is_next"] is True
            elif t["trip_id"] == str(completed_id):
                assert t["is_next"] is False
                assert t["trip_status"] == "COMPLETED"
            elif t["trip_id"] == str(later_id):
                assert t["is_next"] is False
                # Check B_TO_A terminal stop reversal
                assert t["direction"] == "B_TO_A"
                assert t["origin_stop_name"] == "Tech Park"
                assert t["destination_stop_name"] == "City Center"

        # At most one trip is next
        assert sum(1 for t in trips if t["is_next"]) == 1
    finally:
        with Session(engine) as session:
            session.execute(delete(TripAssignment).where(TripAssignment.user_id == chrono_driver_id))
            session.execute(delete(Trip).where(Trip.id.in_([completed_id, next_id, later_id])))
            session.execute(delete(OperatorProfile).where(OperatorProfile.user_id == chrono_driver_id))
            session.execute(delete(User).where(User.id == chrono_driver_id))
            session.commit()


def test_get_operator_todays_trips_unassigned_returns_empty():
    """Verify an operator with no assigned trips today receives an empty list."""
    token = get_conductor_token()
    response = client.get(
        "/api/operator/me/trips",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []
