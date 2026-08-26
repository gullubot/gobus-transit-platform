"""
Transit Platform — Operator Duty & Trip Tracking Lifecycle Tests.

BUILD 2: Tests for assignment retrieval and trip tracking start/end endpoints.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
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
