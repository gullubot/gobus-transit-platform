import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole
from app.models.route import Route, Stop, RouteStop
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
def org_route(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org Route Detail {suffix}")
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
def admin_user(session: Session, org_route: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_route_{suffix}@demo.com"
    admin = User(
        organization_id=org_route.id,
        name="Admin Route Detail",
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
    email = f"admin_other_{suffix}@demo.com"
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
def route_with_stops(session: Session, org_route: Organization):
    suffix = uuid.uuid4().hex[:8]

    stop1 = Stop(
        organization_id=org_route.id,
        stop_code=f"STP1_{suffix}",
        name="Sonarpur Station",
        latitude=22.44,
        longitude=88.42,
        location="SRID=4326;POINT(88.42 22.44)",
    )
    stop2 = Stop(
        organization_id=org_route.id,
        stop_code=f"STP2_{suffix}",
        name="Sahebpara",
        latitude=22.45,
        longitude=88.43,
        location="SRID=4326;POINT(88.43 22.45)",
    )
    stop3 = Stop(
        organization_id=org_route.id,
        stop_code=f"STP3_{suffix}",
        name="Khariberea",
        latitude=22.48,
        longitude=88.46,
        location="SRID=4326;POINT(88.46 22.48)",
    )
    session.add_all([stop1, stop2, stop3])
    session.commit()

    route = Route(
        organization_id=org_route.id,
        route_code=f"R001_{suffix}",
        route_name="Sonarpur to Khariberea",
        distance_km=43.69,
        status="ACTIVE",
    )
    session.add(route)
    session.commit()
    session.refresh(route)

    # Route stops with cumulative travel time: 0s, 123s, 4854s
    rs1 = RouteStop(
        route_id=route.id,
        stop_id=stop1.id,
        sequence_number=1,
        distance_from_start=0.0,
        nominal_travel_time_seconds=0,
    )
    rs2 = RouteStop(
        route_id=route.id,
        stop_id=stop2.id,
        sequence_number=2,
        distance_from_start=0.83,
        nominal_travel_time_seconds=123,
    )
    rs3 = RouteStop(
        route_id=route.id,
        stop_id=stop3.id,
        sequence_number=3,
        distance_from_start=43.69,
        nominal_travel_time_seconds=4854,
    )
    session.add_all([rs1, rs2, rs3])
    session.commit()

    return {
        "route": route,
        "stops": [stop1, stop2, stop3],
        "route_stops": [rs1, rs2, rs3],
    }


def test_get_route_details_success(client: TestClient, auth_headers: dict, route_with_stops: dict):
    route = route_with_stops["route"]
    response = client.get(f"/api/admin/routes/{route.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(route.id)
    assert data["route_code"] == route.route_code
    assert data["route_name"] == route.route_name
    assert data["distance_km"] == 43.69
    assert data["status"] == "ACTIVE"


def test_get_route_details_not_found(client: TestClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/admin/routes/{fake_id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Route not found"


def test_get_route_details_tenant_isolation(client: TestClient, other_auth_headers: dict, route_with_stops: dict):
    route = route_with_stops["route"]
    response = client.get(f"/api/admin/routes/{route.id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_get_route_stops_sequence(client: TestClient, auth_headers: dict, route_with_stops: dict):
    route = route_with_stops["route"]
    response = client.get(f"/api/admin/routes/{route.id}/stops", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["sequence_number"] == 1
    assert data[0]["stop_name"] == "Sonarpur Station"
    assert data[0]["distance_from_start"] == 0.0
    assert data[0]["nominal_travel_time_seconds"] == 0

    assert data[1]["sequence_number"] == 2
    assert data[1]["stop_name"] == "Sahebpara"
    assert data[1]["distance_from_start"] == 0.83
    assert data[1]["nominal_travel_time_seconds"] == 123

    assert data[2]["sequence_number"] == 3
    assert data[2]["stop_name"] == "Khariberea"
    assert data[2]["distance_from_start"] == 43.69
    assert data[2]["nominal_travel_time_seconds"] == 4854


def test_route_total_travel_time_audit(client: TestClient, auth_headers: dict, route_with_stops: dict):
    """
    CRITICAL AUDIT TEST:
    Verify that nominal_travel_time_seconds is cumulative.
    Total Route Travel Time = final stop nominal_travel_time_seconds (4854s = ~1 hr 20 min 54 sec),
    NOT sum of all stops (0 + 123 + 4854 = 4977s, or 192,982s for 86 stops).
    """
    route = route_with_stops["route"]
    response = client.get(f"/api/admin/routes/{route.id}/stops", headers=auth_headers)
    assert response.status_code == 200
    stops = response.json()

    # The buggy calculation:
    sum_travel_time = sum(s.get("nominal_travel_time_seconds") or 0 for s in stops)

    # The authoritative calculation:
    final_stop = max(stops, key=lambda s: s["sequence_number"])
    authoritative_total_travel_time = final_stop.get("nominal_travel_time_seconds") or 0

    assert authoritative_total_travel_time == 4854
    # Ensure they are distinct concepts and the final stop time reflects actual route travel time
    assert authoritative_total_travel_time != sum_travel_time or len(stops) == 1

    # Segment travel time calculation test
    segment_0 = stops[0]["nominal_travel_time_seconds"] - 0  # 0s
    segment_1 = stops[1]["nominal_travel_time_seconds"] - stops[0]["nominal_travel_time_seconds"]  # 123s
    segment_2 = stops[2]["nominal_travel_time_seconds"] - stops[1]["nominal_travel_time_seconds"]  # 4731s
    assert segment_0 == 0
    assert segment_1 == 123
    assert segment_2 == 4731
    assert segment_0 + segment_1 + segment_2 == authoritative_total_travel_time


def test_update_route_success(client: TestClient, auth_headers: dict, route_with_stops: dict):
    route = route_with_stops["route"]
    update_payload = {
        "route_name": "Updated Route Name",
        "status": "INACTIVE",
    }
    response = client.put(f"/api/admin/routes/{route.id}", json=update_payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["route_name"] == "Updated Route Name"
    assert data["status"] == "INACTIVE"
    assert data["route_code"] == route.route_code


def test_update_route_code_duplicate_rejected(client: TestClient, auth_headers: dict, session: Session, org_route: Organization, route_with_stops: dict):
    # Create another route in same org
    suffix = uuid.uuid4().hex[:8]
    other_route = Route(
        organization_id=org_route.id,
        route_code=f"R_DUP_{suffix}",
        route_name="Another Route",
        distance_km=10.0,
        status="ACTIVE",
    )
    session.add(other_route)
    session.commit()
    session.refresh(other_route)

    # Attempt to update first route to other_route's code
    target_route = route_with_stops["route"]
    response = client.put(
        f"/api/admin/routes/{target_route.id}",
        json={"route_code": other_route.route_code},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "duplicate" in response.json()["detail"].lower()


def test_update_route_tenant_isolation(client: TestClient, other_auth_headers: dict, route_with_stops: dict):
    route = route_with_stops["route"]
    response = client.put(
        f"/api/admin/routes/{route.id}",
        json={"route_name": "Hacked Route Name"},
        headers=other_auth_headers,
    )
    assert response.status_code == 404
