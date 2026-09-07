"""
Transit Platform — Operator Issue Reporting Endpoint Tests (Operator 1.0.6).

Tests that an assigned operator can report an operational issue during a trip,
creating an OPEN ServiceAlert for Admin triage without altering trip status,
ETA, route matching, or tracking sessions.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.database import engine
from app.db.guard import assert_testing_database
from app.db.seed import (
    DEV_DRIVER_ID,
    ORG_ID,
    TRIP_PLANNED_ID,
    USER_DEPOT_ADMIN_ID,
    USER_FLEET_ADMIN_ID,
    seed_dev_data,
)
from app.main import app
from app.models.alert import ServiceAlert
from app.models.enums import AlertScope, AlertStatus, AlertSeverity, TripStatus
from app.models.trip import Trip

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    assert_testing_database(engine)
    with Session(engine) as session:
        seed_dev_data(session)
    yield
    with Session(engine) as session:
        session.execute(delete(ServiceAlert).where(ServiceAlert.trip_id == TRIP_PLANNED_ID))
        session.commit()


def get_driver_token() -> str:
    """Helper to authenticate DRV001 and get access token."""
    response = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "DRV001", "password": "operator123"},
    )
    return response.json()["access_token"]


def test_operator_report_issue_success():
    """CASE 1: Assigned driver successfully reports an issue on their assigned trip."""
    token = get_driver_token()
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "issue_type": "BREAKDOWN",
        "message": "Engine overheating near Sector 5 stop",
        "severity": "CRITICAL",
    }

    # Record initial trip status
    with Session(engine) as session:
        trip = session.get(Trip, TRIP_PLANNED_ID)
        initial_status = trip.status
        initial_actual_start = trip.actual_start_at

    response = client.post(
        f"/api/operator/trips/{TRIP_PLANNED_ID}/issues",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert "alert_id" in data
    assert data["trip_id"] == str(TRIP_PLANNED_ID)
    assert data["scope"] == AlertScope.TRIP.value
    assert data["status"] == AlertStatus.OPEN.value
    assert data["type"] == "OPERATOR_REPORTED_ISSUE"
    assert data["severity"] == AlertSeverity.CRITICAL.value
    assert data["title"] == "Operator Report: Breakdown"
    assert data["message"] == "Engine overheating near Sector 5 stop"

    # CRITICAL: Verify trip status, actual_start, etc. were NOT mutated
    with Session(engine) as session:
        trip = session.get(Trip, TRIP_PLANNED_ID)
        assert trip.status == initial_status
        assert trip.actual_start_at == initial_actual_start

        # Verify ServiceAlert exists in DB with OPEN status for Admin triage
        alert = session.get(ServiceAlert, uuid.UUID(data["alert_id"]))
        assert alert is not None
        assert alert.scope == AlertScope.TRIP
        assert alert.status == AlertStatus.OPEN
        assert alert.type == "OPERATOR_REPORTED_ISSUE"
        assert alert.organization_id == trip.organization_id


def test_operator_report_issue_unauthorized_cases():
    """CASE 2: Authorization and validation rules for issue reporting."""
    token = get_driver_token()
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "issue_type": "TRAFFIC_DELAY",
        "message": "Heavy traffic on main corridor",
        "severity": "WARNING",
    }

    # 1. Non-existent trip -> 404
    non_existent = uuid.uuid4()
    resp_404 = client.post(
        f"/api/operator/trips/{non_existent}/issues",
        json=payload,
        headers=headers,
    )
    assert resp_404.status_code == 404

    # 2. Unauthenticated -> 401
    resp_401 = client.post(
        f"/api/operator/trips/{TRIP_PLANNED_ID}/issues",
        json=payload,
    )
    assert resp_401.status_code == 401

    # 3. Fleet Admin calling operator endpoint -> 403
    admin_token = create_access_token(
        subject=str(USER_FLEET_ADMIN_ID),
        claims={"role": "FLEET_ADMIN", "org_id": str(ORG_ID)},
    )
    resp_admin = client.post(
        f"/api/operator/trips/{TRIP_PLANNED_ID}/issues",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 403


def test_operator_cannot_report_issue_on_unassigned_trip():
    """CASE 3: Driver cannot report issue on a trip they are not assigned to."""
    token = get_driver_token()

    # Create an unassigned trip in the test DB
    with Session(engine) as session:
        trip = session.get(Trip, TRIP_PLANNED_ID)
        unassigned_trip = Trip(
            organization_id=trip.organization_id,
            service_id=trip.service_id,
            route_id=trip.route_id,
            vehicle_id=trip.vehicle_id,
            direction=trip.direction,
            operating_date=trip.operating_date,
            planned_start_at=trip.planned_start_at,
            expected_end_at=trip.expected_end_at,
            status=TripStatus.PLANNED,
        )
        session.add(unassigned_trip)
        session.commit()
        session.refresh(unassigned_trip)
        unassigned_trip_id = unassigned_trip.id

    try:
        payload = {
            "issue_type": "OTHER",
            "message": "Testing unassigned trip report",
            "severity": "INFO",
        }
        resp = client.post(
            f"/api/operator/trips/{unassigned_trip_id}/issues",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "not assigned" in resp.json()["detail"].lower()
    finally:
        with Session(engine) as session:
            t = session.get(Trip, unassigned_trip_id)
            if t:
                session.delete(t)
                session.commit()
