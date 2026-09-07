import uuid
from datetime import datetime, timezone
import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, Direction, RouteStatus, StopStatus, ServiceStatus
from app.models.service import Service
from app.models.route import Route, Stop, RouteStop
from app.db.database import engine
from app.db.seed import seed_dev_data
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        seed_dev_data(session)

@pytest.fixture
def session():
    with Session(engine) as s:
        yield s

@pytest.fixture
def org_a(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org A {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin A",
        email=email,
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()
    
    response = client.post(
        "/api/admin/login",
        json={"email": email, "password": "password"},
    )
    return response.json()["access_token"]

@pytest.fixture
def org_b(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org B {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_b_token(client: TestClient, session: Session, org_b: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_b_{suffix}@demo.com"
    admin = User(
        organization_id=org_b.id,
        name="Admin B",
        email=email,
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()
    
    response = client.post(
        "/api/admin/login",
        json={"email": email, "password": "password"},
    )
    return response.json()["access_token"]


@pytest.fixture
def stop_b(session: Session, org_b: Organization):
    stop = Stop(
        organization_id=org_b.id,
        stop_code="B_STOP",
        name="Org B Stop",
        latitude=10.0,
        longitude=10.0,
        location="SRID=4326;POINT(10 10)",
        status=StopStatus.ACTIVE
    )
    session.add(stop)
    session.commit()
    session.refresh(stop)
    return stop

@pytest.fixture
def route_b(session: Session, org_b: Organization):
    route = Route(
        organization_id=org_b.id,
        route_code="B_ROUTE",
        route_name="Org B Route",
        distance_km=10.5,
        geometry="SRID=4326;LINESTRING(10 10, 11 11)",
        status=RouteStatus.ACTIVE
    )
    session.add(route)
    session.commit()
    session.refresh(route)
    return route


def test_create_stop(client: TestClient, admin_token: str):
    suffix = uuid.uuid4().hex[:8]
    data = {
        "stop_code": f"TEST_STOP_{suffix}",
        "name": "Test Stop",
        "latitude": 45.0,
        "longitude": 45.0,
        "status": "ACTIVE"
    }
    response = client.post("/api/admin/stops", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["stop_code"] == f"TEST_STOP_{suffix}"
    assert "id" in res_data
    return res_data["id"]

def test_get_stops(client: TestClient, admin_token: str, admin_b_token: str, stop_b: Stop):
    # Admin A shouldn't see Admin B's stop
    resp_a = client.get("/api/admin/stops", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_a.status_code == 200
    ids_a = [s["id"] for s in resp_a.json()]
    assert str(stop_b.id) not in ids_a

    # Admin B should see Admin B's stop
    resp_b = client.get("/api/admin/stops", headers={"Authorization": f"Bearer {admin_b_token}"})
    assert resp_b.status_code == 200
    ids_b = [s["id"] for s in resp_b.json()]
    assert str(stop_b.id) in ids_b


def test_update_stop_isolation(client: TestClient, admin_token: str, stop_b: Stop):
    # Admin A cannot update Admin B's stop
    data = {"name": "Hacked Name"}
    response = client.put(f"/api/admin/stops/{stop_b.id}", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 404


def test_create_route(client: TestClient, admin_token: str):
    suffix = uuid.uuid4().hex[:8]
    data = {
        "route_code": f"R_TEST_{suffix}",
        "route_name": "Test Route",
        "distance_km": 15.0,
        "geometry": {
            "type": "LineString",
            "coordinates": [[0,0], [1,1]]
        },
        "status": "ACTIVE"
    }
    response = client.post("/api/admin/routes", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["route_code"] == f"R_TEST_{suffix}"
    assert res_data["geometry"]["type"] == "LineString"


def test_route_stop_isolation(client: TestClient, admin_token: str, route_b: Route, stop_b: Stop):
    # Admin A cannot attach stops to Admin B's route
    data = {
        "stops": [
            {
                "stop_id": str(stop_b.id),
                "sequence_number": 1
            }
        ]
    }
    response = client.post(f"/api/admin/routes/{route_b.id}/stops", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 404

def test_route_stop_org_mismatch(client: TestClient, admin_b_token: str, route_b: Route):
    # Admin B cannot attach an unknown/other org stop to Admin B's route
    # Get a stop from Org A (assume one exists from dev seed)
    resp = client.get("/api/admin/stops", headers={"Authorization": f"Bearer {admin_b_token}"})
    
    # Just pass a fake UUID
    fake_id = str(uuid.uuid4())
    data = {
        "stops": [
            {
                "stop_id": fake_id,
                "sequence_number": 1
            }
        ]
    }
    response = client.post(f"/api/admin/routes/{route_b.id}/stops", headers={"Authorization": f"Bearer {admin_b_token}"}, json=data)
    assert response.status_code == 400
    assert "not belong to your organization" in response.json()["detail"]


def test_create_service(client: TestClient, admin_token: str):
    # Create a route first
    route_suffix = uuid.uuid4().hex[:8]
    route_data = {
        "route_code": f"R_SVC_{route_suffix}",
        "route_name": "Service Route",
        "distance_km": 10.0,
        "geometry": {"type": "LineString", "coordinates": [[0,0], [1,1]]},
        "status": "ACTIVE"
    }
    route_resp = client.post("/api/admin/routes", headers={"Authorization": f"Bearer {admin_token}"}, json=route_data)
    route_id = route_resp.json()["id"]

    suffix = uuid.uuid4().hex[:8]
    data = {
        "service_code": f"TEST_SVC_{suffix}",
        "service_name": "Test Service",
        "route_id": route_id
    }
    response = client.post("/api/admin/services", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 200
    assert response.json()["service_code"] == f"TEST_SVC_{suffix}"


def test_create_service_cross_org(client: TestClient, admin_token: str, route_b: Route):
    # Admin A cannot create a service referencing Admin B's route
    data = {
        "service_code": "HACK_SVC",
        "service_name": "Hack Service",
        "route_id": str(route_b.id)
    }
    response = client.post("/api/admin/services", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 400
    assert "does not belong to your organization" in response.json()["detail"]
