"""
Transit Platform — Admin Authentication API Tests.

BUILD 4: Tests for POST /api/admin/login, GET /api/admin/me, and JWT validation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import seed_dev_data
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        seed_dev_data(session)


def test_valid_fleet_admin_login():
    """Valid FLEET_ADMIN login returns 200 and access token."""
    response = client.post(
        "/api/admin/login",
        json={"email": "fleet@demo.com", "password": "operator123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "FLEET_ADMIN"
    assert data["email"] == "fleet@demo.com"
    assert data["name"] == "Fleet Admin"
    assert "organization_id" in data


def test_valid_depot_admin_login():
    """Valid DEPOT_ADMIN login returns 200."""
    response = client.post(
        "/api/admin/login",
        json={"email": "depot@demo.com", "password": "operator123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "DEPOT_ADMIN"
    assert data["email"] == "depot@demo.com"


def test_invalid_admin_password_returns_401():
    """Invalid password returns 401 Unauthorized."""
    response = client.post(
        "/api/admin/login",
        json={"email": "fleet@demo.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_non_admin_rejected():
    """DRIVER/CONDUCTOR/PASSENGER cannot login to admin endpoint."""
    response = client.post(
        "/api/admin/login",
        json={"email": "driver@demo.com", "password": "operator123"},
    )
    assert response.status_code == 403
    assert "not authorized for administration" in response.json()["detail"]


def test_admin_me_endpoint():
    """Admin /me endpoint requires valid admin token and returns profile."""
    # 1. Login to get token
    login_resp = client.post(
        "/api/admin/login",
        json={"email": "fleet@demo.com", "password": "operator123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # 2. Call /me
    me_resp = client.get(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["role"] == "FLEET_ADMIN"
    assert me_data["email"] == "fleet@demo.com"


def test_admin_me_rejects_operator_token():
    """Admin /me endpoint rejects DRIVER token."""
    # 1. Login as driver (operator endpoint)
    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "DRV001", "password": "operator123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # 2. Call admin /me with operator token
    me_resp = client.get(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 403
    assert "not authorized for administration" in me_resp.json()["detail"]
