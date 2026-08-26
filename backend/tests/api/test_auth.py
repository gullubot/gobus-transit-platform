"""
Transit Platform — Operator Authentication API Tests.

BUILD 2: Tests for POST /api/auth/operator/login and JWT validation.
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


def test_valid_driver_login():
    """Valid DRIVER login returns 200, access token, and operator metadata."""
    response = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "DRV001", "password": "operator123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "DRIVER"
    assert data["employee_code"] == "DRV001"
    assert data["name"] == "Demo Driver"
    assert "organization_id" in data


def test_valid_conductor_login():
    """Valid CONDUCTOR login returns 200 with CONDUCTOR role."""
    response = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "CND001", "password": "operator123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "CONDUCTOR"
    assert data["employee_code"] == "CND001"


def test_invalid_password_returns_401():
    """Invalid password returns 401 Unauthorized."""
    response = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "DRV001", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Invalid employee code or password" in response.json()["detail"]


def test_nonexistent_employee_code_returns_401():
    """Unknown employee code returns 401 Unauthorized."""
    response = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "NONEXISTENT999", "password": "operator123"},
    )
    assert response.status_code == 401


def test_unauthenticated_request_to_protected_endpoint_returns_401():
    """Protected endpoints reject requests without valid Bearer token."""
    response = client.get("/api/operator/me/assignment")
    assert response.status_code == 401
