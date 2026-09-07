import uuid
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole
from app.models.route import Route, Stop, RouteStop
from app.models.service import Service
from app.db.database import engine
from app.main import app
from app.core.security import get_password_hash


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
    org = Organization(name=f"Org Route Edit {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def other_org(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Other Org Edit {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def admin_user(session: Session, org_route: Organization):
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_edit_{suffix}@demo.com"
    admin = User(
        organization_id=org_route.id,
        name="Admin Route Edit",
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
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_other_edit_{suffix}@demo.com"
    admin = User(
        organization_id=other_org.id,
        name="Admin Other Edit",
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
def test_setup(session: Session, org_route: Organization):
    suffix = uuid.uuid4().hex[:8]

    # Authentic coordinates near Kolkata
    s1 = Stop(
        organization_id=org_route.id,
        stop_code=f"KOL_{suffix}_1",
        name="Sonarpur Station",
        latitude=22.4398,
        longitude=88.4312,
        location="SRID=4326;POINT(88.4312 22.4398)",
    )
    s2 = Stop(
        organization_id=org_route.id,
        stop_code=f"KOL_{suffix}_2",
        name="Sahebpara",
        latitude=22.4450,
        longitude=88.4350,
        location="SRID=4326;POINT(88.4350 22.4450)",
    )
    s3 = Stop(
        organization_id=org_route.id,
        stop_code=f"KOL_{suffix}_3",
        name="Power House",
        latitude=22.4500,
        longitude=88.4400,
        location="SRID=4326;POINT(88.4400 22.4500)",
    )
    s4 = Stop(
        organization_id=org_route.id,
        stop_code=f"KOL_{suffix}_4",
        name="Khariberea",
        latitude=22.4600,
        longitude=88.4500,
        location="SRID=4326;POINT(88.4500 22.4600)",
    )
    session.add_all([s1, s2, s3, s4])
    session.commit()

    # Create initial route with 3 stops (s1, s2, s4)
    route = Route(
        organization_id=org_route.id,
        route_code=f"R001_{suffix}",
        route_name="Sonarpur to Khariberea",
        distance_km=15.5,
        status="ACTIVE",
    )
    session.add(route)
    session.commit()
    session.refresh(route)

    rs1 = RouteStop(
        route_id=route.id,
        stop_id=s1.id,
        sequence_number=1,
        distance_from_start=0.0,
        nominal_travel_time_seconds=0,
    )
    rs2 = RouteStop(
        route_id=route.id,
        stop_id=s2.id,
        sequence_number=2,
        distance_from_start=5.0,
        nominal_travel_time_seconds=600,
    )
    rs3 = RouteStop(
        route_id=route.id,
        stop_id=s4.id,
        sequence_number=3,
        distance_from_start=15.5,
        nominal_travel_time_seconds=1800,
    )
    session.add_all([rs1, rs2, rs3])
    session.commit()

    return {
        "route": route,
        "stops": [s1, s2, s3, s4],
    }


# 1, 2, 3. Route Edit loads, existing metadata & stop sequence pre-populated
def test_route_edit_prepopulated_data(client: TestClient, auth_headers: dict, test_setup: dict):
    route = test_setup["route"]
    # Get route details
    res_route = client.get(f"/api/admin/routes/{route.id}", headers=auth_headers)
    assert res_route.status_code == status.HTTP_200_OK
    rdata = res_route.json()
    assert rdata["route_code"] == route.route_code
    assert rdata["route_name"] == route.route_name
    assert rdata["status"] == "ACTIVE"

    # Get route stops
    res_stops = client.get(f"/api/admin/routes/{route.id}/stops", headers=auth_headers)
    assert res_stops.status_code == status.HTTP_200_OK
    sdata = res_stops.json()
    assert len(sdata) == 3
    assert sdata[0]["sequence_number"] == 1
    assert sdata[1]["sequence_number"] == 2
    assert sdata[2]["sequence_number"] == 3


# 21, 22. Route metadata update works and duplicate code is rejected
def test_route_metadata_update_and_duplicate_rejection(
    client: TestClient, auth_headers: dict, test_setup: dict, session: Session, org_route: Organization
):
    route = test_setup["route"]

    # Update metadata
    res_update = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "route_name": "Updated Route Name Description",
            "status": "INACTIVE",
        },
    )
    assert res_update.status_code == status.HTTP_200_OK
    data = res_update.json()
    assert data["route_name"] == "Updated Route Name Description"
    assert data["status"] == "INACTIVE"

    # Create another route in org
    other_route = Route(
        organization_id=org_route.id,
        route_code="R_DUP_TEST",
        route_name="Duplicate Code Target",
        status="ACTIVE",
    )
    session.add(other_route)
    session.commit()

    # Try to change route_code to existing code -> 400
    res_dup = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={"route_code": "R_DUP_TEST"},
    )
    assert res_dup.status_code == status.HTTP_400_BAD_REQUEST
    assert "duplicate" in res_dup.json()["detail"].lower()


# 4, 5, 6, 15, 16, 17, 18, 19. Add Existing Stop recalculates topology and does NOT create a new Stop entity
def test_route_edit_add_existing_stop(
    client: TestClient, auth_headers: dict, test_setup: dict, session: Session
):
    route = test_setup["route"]
    stops = test_setup["stops"]
    s1, s2, s3, s4 = stops

    stop_count_before = session.query(Stop).count()

    # Update route by inserting s3 (Power House) as an intermediate stop between s2 and s4
    # Sequence: s1 (start), intermediates: [s2, s3], s4 (end)
    res_save = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "route_code": route.route_code,
            "route_name": route.route_name,
            "status": "ACTIVE",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s4.id),
            "intermediate_stop_ids": [str(s2.id), str(s3.id)],
        },
    )
    assert res_save.status_code == status.HTTP_200_OK
    data = res_save.json()
    assert data["distance_km"] > 0
    assert data["geometry"] is not None

    # CRITICAL INVARIANT: Stop table entity count MUST NOT change!
    stop_count_after = session.query(Stop).count()
    assert stop_count_after == stop_count_before

    # Verify RouteStop sequence in DB
    route_stops = (
        session.query(RouteStop)
        .filter(RouteStop.route_id == route.id)
        .order_by(RouteStop.sequence_number.asc())
        .all()
    )
    assert len(route_stops) == 4
    assert [rs.stop_id for rs in route_stops] == [s1.id, s2.id, s3.id, s4.id]
    assert [rs.sequence_number for rs in route_stops] == [1, 2, 3, 4]

    # Monotonic cumulative distance and cumulative travel time checks
    for i in range(len(route_stops) - 1):
        assert route_stops[i + 1].distance_from_start >= route_stops[i].distance_from_start
        assert route_stops[i + 1].nominal_travel_time_seconds >= route_stops[i].nominal_travel_time_seconds


# 7, 8, 9. Remove Stop from Route does NOT delete the Stop entity
def test_route_edit_remove_stop_does_not_delete_stop_entity(
    client: TestClient, auth_headers: dict, test_setup: dict, session: Session
):
    route = test_setup["route"]
    stops = test_setup["stops"]
    s1, s2, s3, s4 = stops

    stop_count_before = session.query(Stop).count()

    # Remove s2 (intermediate stop) leaving only s1 -> s4
    res_save = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s4.id),
            "intermediate_stop_ids": [],
        },
    )
    assert res_save.status_code == status.HTTP_200_OK

    # Verify stop count in stops table is UNCHANGED
    stop_count_after = session.query(Stop).count()
    assert stop_count_after == stop_count_before

    # Verify s2 still exists in the Stop entity catalog!
    s2_in_db = session.get(Stop, s2.id)
    assert s2_in_db is not None
    assert s2_in_db.name == "Sahebpara"

    # Verify route_stops has only 2 stops
    route_stops = (
        session.query(RouteStop)
        .filter(RouteStop.route_id == route.id)
        .order_by(RouteStop.sequence_number.asc())
        .all()
    )
    assert len(route_stops) == 2
    assert [rs.stop_id for rs in route_stops] == [s1.id, s4.id]
    assert [rs.sequence_number for rs in route_stops] == [1, 2]


# 10, 11, 20. Reorder stops updates sequence numbers and endpoints
def test_route_edit_reorder_stops(
    client: TestClient, auth_headers: dict, test_setup: dict, session: Session
):
    route = test_setup["route"]
    stops = test_setup["stops"]
    s1, s2, s3, s4 = stops

    # Reverse direction: s4 (start) -> s2 (intermediate) -> s1 (end)
    res_save = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "start_stop_id": str(s4.id),
            "end_stop_id": str(s1.id),
            "intermediate_stop_ids": [str(s2.id)],
        },
    )
    assert res_save.status_code == status.HTTP_200_OK

    route_stops = (
        session.query(RouteStop)
        .filter(RouteStop.route_id == route.id)
        .order_by(RouteStop.sequence_number.asc())
        .all()
    )
    assert len(route_stops) == 3
    assert route_stops[0].stop_id == s4.id
    assert route_stops[0].sequence_number == 1
    assert route_stops[1].stop_id == s2.id
    assert route_stops[1].sequence_number == 2
    assert route_stops[2].stop_id == s1.id
    assert route_stops[2].sequence_number == 3


# 12, 13, 14. Validation rules: minimum stops, duplicate stops, start == end
def test_route_edit_validation_errors(client: TestClient, auth_headers: dict, test_setup: dict):
    route = test_setup["route"]
    stops = test_setup["stops"]
    s1, s2, s3, s4 = stops

    # Start and End cannot be the same
    res_same = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s1.id),
            "intermediate_stop_ids": [],
        },
    )
    assert res_same.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot be the same" in res_same.json()["detail"].lower()

    # Duplicate stop in sequence
    res_dup = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s4.id),
            "intermediate_stop_ids": [str(s2.id), str(s2.id)],
        },
    )
    assert res_dup.status_code == status.HTTP_400_BAD_REQUEST
    assert "duplicate" in res_dup.json()["detail"].lower()

    # Non-existent stop
    res_missing = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "start_stop_id": str(s1.id),
            "end_stop_id": str(uuid.uuid4()),
            "intermediate_stop_ids": [],
        },
    )
    assert res_missing.status_code == status.HTTP_404_NOT_FOUND


# 4. Preview route endpoint with exclude_route_id
def test_route_preview_with_exclude_route_id(client: TestClient, auth_headers: dict, test_setup: dict):
    route = test_setup["route"]
    stops = test_setup["stops"]
    s1, s2, s3, s4 = stops

    # Calling preview for current route with exclude_route_id=route.id
    # should NOT return duplicate_match.is_duplicate=True for itself
    res = client.post(
        "/api/admin/routes/preview",
        headers=auth_headers,
        json={
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s4.id),
            "intermediate_stop_ids": [str(s2.id)],
            "exclude_route_id": str(route.id),
        },
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["distance_km"] > 0
    assert len(data["stops"]) == 3
    assert data.get("duplicate_match") is None or not data["duplicate_match"]["is_duplicate"]


# 25, 26. Dependent Services remain referentially safe
def test_dependent_service_preservation_after_route_edit(
    client: TestClient, auth_headers: dict, test_setup: dict, session: Session, org_route: Organization
):
    route = test_setup["route"]
    stops = test_setup["stops"]
    s1, s2, s3, s4 = stops

    # Create a Service referencing this route
    svc = Service(
        organization_id=org_route.id,
        service_code="SVC_TEST_ROUTE_EDIT",
        service_name="Route Edit Dependency Service",
        route_id=route.id,
        status="ACTIVE",
    )
    session.add(svc)
    session.commit()

    # Update route topology
    res = client.put(
        f"/api/admin/routes/{route.id}",
        headers=auth_headers,
        json={
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s4.id),
            "intermediate_stop_ids": [str(s3.id)],
        },
    )
    assert res.status_code == status.HTTP_200_OK

    # Verify Service still references this route safely
    session.refresh(svc)
    assert svc.route_id == route.id


# 28. Strict Tenant Isolation
def test_tenant_isolation_on_route_edit(
    client: TestClient, other_auth_headers: dict, test_setup: dict
):
    route = test_setup["route"]

    # Other organization attempts to update route -> 404
    res = client.put(
        f"/api/admin/routes/{route.id}",
        headers=other_auth_headers,
        json={"route_name": "Hacked Route Name"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
