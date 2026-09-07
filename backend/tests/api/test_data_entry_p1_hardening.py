"""
Targeted tests for Build 4.1 Admin Data-Entry P1 Hardening.

Verifies:
1. Route creation without geometry persists cleanly with geometry = None (no fake fallback).
2. Route creation with valid GeoJSON LineString persists geometry correctly.
3. Route creation with artificial placeholder [[0, 0], [1, 1]] is strictly rejected with HTTP 400.
4. Route creation with artificial placeholder [[0.0, 0.0], [1.0, 1.0]] is strictly rejected with HTTP 400.
5. Service creation links to the Route UUID correctly.
6. Route update can set or clear geometry cleanly.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.main import app
from app.db.database import engine
from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole
from app.models.route import Route
from app.core.security import get_password_hash


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with Session(engine) as s:
        yield s


@pytest.fixture
def org(db: Session):
    suffix = uuid.uuid4().hex[:6]
    o = Organization(
        name=f"Kolkata Hardening Org {suffix}",
        city="Kolkata",
        status="ACTIVE"
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


@pytest.fixture
def admin_headers(client: TestClient, db: Session, org: Organization):
    suffix = uuid.uuid4().hex[:6]
    email = f"admin_hard_{suffix}@test.local"
    admin = User(
        organization_id=org.id,
        name="Hardening Admin",
        email=email,
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.FLEET_ADMIN,
    )
    db.add(admin)
    db.commit()

    resp = client.post("/api/admin/login", json={"email": email, "password": "AdminPass123!"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_01_route_creation_without_geometry_persists_as_none(client: TestClient, admin_headers: dict, db: Session):
    """Test creating a Route with no geometry field: persists with geometry=None (no fake coords)."""
    code = f"R-NOGEO-{uuid.uuid4().hex[:4]}"
    resp = client.post(
        "/api/admin/routes",
        json={
            "route_code": code,
            "route_name": "Route Without Geometry",
            "distance_km": 15.2,
            "status": "ACTIVE"
        },
        headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["route_code"] == code
    assert data["geometry"] is None

    # Verify directly in database that geometry is NULL
    route_in_db = db.execute(select(Route).where(Route.id == uuid.UUID(data["id"]))).scalar_one()
    assert route_in_db.geometry is None


def test_02_route_creation_with_valid_geometry_persists(client: TestClient, admin_headers: dict):
    """Test creating a Route with valid real GeoJSON LineString coordinates."""
    code = f"R-VALGEO-{uuid.uuid4().hex[:4]}"
    valid_geometry = {
        "type": "LineString",
        "coordinates": [
            [88.3512, 22.5678],
            [88.3623, 22.5789],
            [88.3734, 22.5890]
        ]
    }
    resp = client.post(
        "/api/admin/routes",
        json={
            "route_code": code,
            "route_name": "Route With Real Geometry",
            "distance_km": 8.4,
            "status": "ACTIVE",
            "geometry": valid_geometry
        },
        headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["geometry"] is not None
    assert data["geometry"]["type"] == "LineString"
    assert len(data["geometry"]["coordinates"]) == 3


def test_03_route_creation_with_artificial_placeholder_rejected(client: TestClient, admin_headers: dict):
    """Test that artificial placeholder [[0, 0], [1, 1]] is explicitly rejected with HTTP 400."""
    code = f"R-FAKE-{uuid.uuid4().hex[:4]}"
    fake_geometry = {
        "type": "LineString",
        "coordinates": [[0, 0], [1, 1]]
    }
    resp = client.post(
        "/api/admin/routes",
        json={
            "route_code": code,
            "route_name": "Route With Fake Geometry",
            "distance_km": 5.0,
            "status": "ACTIVE",
            "geometry": fake_geometry
        },
        headers=admin_headers
    )
    assert resp.status_code == 400
    assert "Artificial placeholder geometry [[0,0], [1,1]] is not permitted" in resp.json()["detail"]


def test_04_route_creation_with_float_artificial_placeholder_rejected(client: TestClient, admin_headers: dict):
    """Test that float [[0.0, 0.0], [1.0, 1.0]] is also rejected with HTTP 400."""
    code = f"R-FAKE2-{uuid.uuid4().hex[:4]}"
    fake_geometry = {
        "type": "LineString",
        "coordinates": [[0.0, 0.0], [1.0, 1.0]]
    }
    resp = client.post(
        "/api/admin/routes",
        json={
            "route_code": code,
            "route_name": "Route With Fake Float Geometry",
            "distance_km": 5.0,
            "status": "ACTIVE",
            "geometry": fake_geometry
        },
        headers=admin_headers
    )
    assert resp.status_code == 400
    assert "Artificial placeholder geometry [[0,0], [1,1]] is not permitted" in resp.json()["detail"]


def test_05_service_creation_submits_route_uuid_correctly(client: TestClient, admin_headers: dict):
    """Test that Service creation accepts route_id UUID from Route selection."""
    # 1. Create a route
    code = f"R-SVC-{uuid.uuid4().hex[:4]}"
    r_resp = client.post(
        "/api/admin/routes",
        json={
            "route_code": code,
            "route_name": "Route For Service",
            "distance_km": 10.0,
            "status": "ACTIVE"
        },
        headers=admin_headers
    )
    assert r_resp.status_code == 200, r_resp.text
    route_id = r_resp.json()["id"]

    # 2. Create a service linked to this route_id
    svc_code = f"SVC-{uuid.uuid4().hex[:4]}"
    s_resp = client.post(
        "/api/admin/services",
        json={
            "service_code": svc_code,
            "service_name": "Morning Express",
            "route_id": route_id,
            "fare_configuration_id": None
        },
        headers=admin_headers
    )
    assert s_resp.status_code == 200, s_resp.text
    s_data = s_resp.json()
    assert s_data["route_id"] == route_id
    assert s_data["route_code"] == code
    assert s_data["route_name"] == "Route For Service"


def test_06_route_update_sets_and_clears_geometry(client: TestClient, admin_headers: dict, db: Session):
    """Test that an existing route can have geometry added or cleared via PUT."""
    # 1. Create route without geometry
    code = f"R-UPD-{uuid.uuid4().hex[:4]}"
    r_resp = client.post(
        "/api/admin/routes",
        json={
            "route_code": code,
            "route_name": "Route Update Test",
            "distance_km": 7.5,
            "status": "ACTIVE"
        },
        headers=admin_headers
    )
    assert r_resp.status_code == 200
    route_id = r_resp.json()["id"]
    assert r_resp.json()["geometry"] is None

    # 2. Add geometry via PUT
    new_geo = {
        "type": "LineString",
        "coordinates": [[88.35, 22.55], [88.36, 22.56]]
    }
    upd_resp = client.put(
        f"/api/admin/routes/{route_id}",
        json={"geometry": new_geo},
        headers=admin_headers
    )
    assert upd_resp.status_code == 200, upd_resp.text
    assert upd_resp.json()["geometry"] is not None
    assert len(upd_resp.json()["geometry"]["coordinates"]) == 2

    # 3. Clear geometry via PUT null
    clear_resp = client.put(
        f"/api/admin/routes/{route_id}",
        json={"geometry": None},
        headers=admin_headers
    )
    assert clear_resp.status_code == 200, clear_resp.text
    assert clear_resp.json()["geometry"] is None
