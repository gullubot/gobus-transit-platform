import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole
from app.models.route import Stop, StopAlias, Route, RouteStop
from app.db.database import engine
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def session():
    with Session(engine) as s:
        yield s


@pytest.fixture
def org_stop(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org Stop Detail {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def other_org(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Other Org {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def admin_user(session: Session, org_stop: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_stop_{suffix}@demo.com"
    admin = User(
        organization_id=org_stop.id,
        name="Admin Stop Detail",
        email=email,
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def other_admin_user(session: Session, other_org: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_other_stop_{suffix}@demo.com"
    admin = User(
        organization_id=other_org.id,
        name="Admin Other Org",
        email=email,
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client: TestClient, admin_user: User):
    response = client.post(
        "/api/admin/login",
        json={"email": admin_user.email, "password": "password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(client: TestClient, other_admin_user: User):
    response = client.post(
        "/api/admin/login",
        json={"email": other_admin_user.email, "password": "password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def stop_with_routes(session: Session, org_stop: Organization):
    suffix = uuid.uuid4().hex[:8]

    # Stop 1 with aliases
    stop1 = Stop(
        organization_id=org_stop.id,
        stop_code=f"KOL_{suffix}_1",
        name="Sonarpur Station Terminus",
        latitude=22.4431,
        longitude=88.4285,
        location="SRID=4326;POINT(88.4285 22.4431)",
        status="ACTIVE",
    )
    # Stop 2 (endpoint)
    stop2 = Stop(
        organization_id=org_stop.id,
        stop_code=f"KOL_{suffix}_2",
        name="Khariberia",
        latitude=22.4800,
        longitude=88.4600,
        location="SRID=4326;POINT(88.4600 22.4800)",
        status="ACTIVE",
    )
    # Stop 3 (endpoint for route 2)
    stop3 = Stop(
        organization_id=org_stop.id,
        stop_code=f"KOL_{suffix}_3",
        name="Howrah Station",
        latitude=22.5850,
        longitude=88.3420,
        location="SRID=4326;POINT(88.3420 22.5850)",
        status="ACTIVE",
    )
    session.add_all([stop1, stop2, stop3])
    session.commit()

    # Add aliases to Stop 1
    alias1 = StopAlias(
        stop_id=stop1.id,
        organization_id=org_stop.id,
        alias_name="Sonarpur Bus Stand",
        alias_type="LOCAL_NAME",
    )
    alias2 = StopAlias(
        stop_id=stop1.id,
        organization_id=org_stop.id,
        alias_name="Sonarpur Rly Stn",
        alias_type="LOCAL_NAME",
    )
    session.add_all([alias1, alias2])
    session.commit()

    # Route 1: uses Stop 1 and Stop 2
    route1 = Route(
        organization_id=org_stop.id,
        route_code=f"R001_{suffix}",
        route_name="Sonarpur to Khariberia",
        distance_km=43.69,
        status="ACTIVE",
    )
    # Route 2: uses Stop 1 and Stop 3
    route2 = Route(
        organization_id=org_stop.id,
        route_code=f"R002_{suffix}",
        route_name="Sonarpur to Howrah Station",
        distance_km=25.50,
        status="ACTIVE",
    )
    session.add_all([route1, route2])
    session.commit()

    # Link Route 1 stops
    rs1_1 = RouteStop(route_id=route1.id, stop_id=stop1.id, sequence_number=1, distance_from_start=0.0, nominal_travel_time_seconds=0)
    rs1_2 = RouteStop(route_id=route1.id, stop_id=stop2.id, sequence_number=2, distance_from_start=43.69, nominal_travel_time_seconds=4854)

    # Link Route 2 stops
    rs2_1 = RouteStop(route_id=route2.id, stop_id=stop1.id, sequence_number=1, distance_from_start=0.0, nominal_travel_time_seconds=0)
    rs2_2 = RouteStop(route_id=route2.id, stop_id=stop3.id, sequence_number=2, distance_from_start=25.50, nominal_travel_time_seconds=3600)

    session.add_all([rs1_1, rs1_2, rs2_1, rs2_2])
    session.commit()

    # Standalone Stop 4 with no routes
    stop4 = Stop(
        organization_id=org_stop.id,
        stop_code=f"KOL_{suffix}_4",
        name="Isolated Stop",
        latitude=22.5000,
        longitude=88.3500,
        location="SRID=4326;POINT(88.3500 22.5000)",
        status="INACTIVE",
    )
    session.add(stop4)
    session.commit()

    return {
        "stop1": stop1,
        "stop2": stop2,
        "stop3": stop3,
        "stop4_isolated": stop4,
        "route1": route1,
        "route2": route2,
    }


def test_get_stop_detail_success(client: TestClient, auth_headers: dict, stop_with_routes: dict):
    stop = stop_with_routes["stop1"]
    response = client.get(f"/api/admin/stops/{stop.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(stop.id)
    assert data["stop_code"] == stop.stop_code
    assert data["name"] == "Sonarpur Station Terminus"
    assert data["status"] == "ACTIVE"
    assert pytest.approx(data["latitude"], 0.0001) == 22.4431
    assert pytest.approx(data["longitude"], 0.0001) == 88.4285
    assert set(data["aliases"]) == {"Sonarpur Bus Stand", "Sonarpur Rly Stn"}


def test_get_stop_detail_not_found(client: TestClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/admin/stops/{fake_id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Stop not found"


def test_get_stop_detail_tenant_isolation(client: TestClient, other_auth_headers: dict, stop_with_routes: dict):
    stop = stop_with_routes["stop1"]
    response = client.get(f"/api/admin/stops/{stop.id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_get_stop_routes_multiple(client: TestClient, auth_headers: dict, stop_with_routes: dict):
    stop = stop_with_routes["stop1"]
    route1 = stop_with_routes["route1"]
    route2 = stop_with_routes["route2"]

    response = client.get(f"/api/admin/stops/{stop.id}/routes", headers=auth_headers)
    assert response.status_code == 200
    routes = response.json()
    assert len(routes) == 2

    route_codes = {r["route_code"] for r in routes}
    assert route1.route_code in route_codes
    assert route2.route_code in route_codes

    # Verify each route carries its own actual route_id
    r1_data = next(r for r in routes if r["route_code"] == route1.route_code)
    assert r1_data["id"] == str(route1.id)
    assert r1_data["route_name"] == route1.route_name
    assert r1_data["status"] == "ACTIVE"

    r2_data = next(r for r in routes if r["route_code"] == route2.route_code)
    assert r2_data["id"] == str(route2.id)
    assert r2_data["route_name"] == route2.route_name
    assert r2_data["status"] == "ACTIVE"


def test_get_stop_routes_empty(client: TestClient, auth_headers: dict, stop_with_routes: dict):
    stop4 = stop_with_routes["stop4_isolated"]
    response = client.get(f"/api/admin/stops/{stop4.id}/routes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_stop_routes_tenant_isolation(client: TestClient, other_auth_headers: dict, stop_with_routes: dict):
    stop = stop_with_routes["stop1"]
    response = client.get(f"/api/admin/stops/{stop.id}/routes", headers=other_auth_headers)
    assert response.status_code == 404
