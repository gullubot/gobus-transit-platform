"""
BUILD 6.1 — Comprehensive Route Creation & Road Routing Test Suite.

Verifies:
1. Fewer than 2 Stops rejected
2. Start Stop must exist
3. End Stop must exist
4. Intermediate Stops must exist
5. Unknown Stop rejected
6. Cross-organization Stop rejected
7. Start == End rejected
8. Duplicate Stop inside sequence rejected
9. Exact order preserved
10. No alphabetical reordering
11. No geographic reordering
12. Missing coordinates rejected
13. Valid coordinates invoke routing
14. Routing receives coordinates in exact Stop order
15. Distance comes from routing provider
16. Geometry comes from routing provider
17. Routing duration comes from routing provider
18. Leg distances populated correctly on RouteStops
19. Routing failure prevents creation
20. Routing failure creates no fake geometry
21. Routing failure creates no fake distance
22. Fake [[0,0],[1,1]] remains rejected
23. Duplicate Route sequence detected
24. Different sequence not duplicate
25. Start is RouteStop sequence 1
26. End is final RouteStop sequence
27. Route code remains admin-controlled
28. Route name remains admin-controlled
29. Editing Stop sequence recalculates route distance
30. Editing Stop sequence recalculates geometry
31. Existing Service -> Route relationship remains valid
32. Tenant isolation remains intact
"""

import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.main import app
from app.db.database import engine
from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, RouteStatus, StopStatus
from app.models.route import Stop, Route, RouteStop
from app.core.security import get_password_hash
from app.services.routing_service import (
    RouteCalculationResult,
    RouteLeg,
    RoutingServiceUnavailableException,
    NoRouteFoundException,
)
from geoalchemy2.elements import WKTElement


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with Session(engine) as s:
        yield s


@pytest.fixture
def org_a(db: Session):
    suffix = uuid.uuid4().hex[:6]
    org = Organization(name=f"Org A {suffix}", city="Kolkata", status="ACTIVE")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def org_b(db: Session):
    suffix = uuid.uuid4().hex[:6]
    org = Organization(name=f"Org B {suffix}", city="Bengaluru", status="ACTIVE")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def token_a(client: TestClient, db: Session, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    email = f"admin_a_{suffix}@test.local"
    admin = User(
        organization_id=org_a.id,
        name="Admin A",
        email=email,
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.FLEET_ADMIN,
    )
    db.add(admin)
    db.commit()
    resp = client.post("/api/admin/login", json={"email": email, "password": "AdminPass123!"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def token_b(client: TestClient, db: Session, org_b: Organization):
    suffix = uuid.uuid4().hex[:6]
    email = f"admin_b_{suffix}@test.local"
    admin = User(
        organization_id=org_b.id,
        name="Admin B",
        email=email,
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.FLEET_ADMIN,
    )
    db.add(admin)
    db.commit()
    resp = client.post("/api/admin/login", json={"email": email, "password": "AdminPass123!"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def create_stop(db: Session, org_id: uuid.UUID, code: str, name: str, lat: float = 22.44, lon: float = 88.42) -> Stop:
    stop = Stop(
        organization_id=org_id,
        stop_code=code,
        name=name,
        latitude=lat,
        longitude=lon,
        location=WKTElement(f"SRID=4326;POINT({lon} {lat})", srid=4326),
        status=StopStatus.ACTIVE,
    )
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop


def mock_routing_success(waypoints):
    """Generates a realistic mocked routing response based on received waypoints."""
    coords = [[lon, lat] for lon, lat in waypoints]
    # Synthetic realistic distance: 1.5 km per leg
    legs = []
    total_meters = 0.0
    total_seconds = 0
    for i in range(len(waypoints) - 1):
        leg_dist_m = 1500.0 + (i * 200.0)
        leg_dur_s = 180 + (i * 20)
        total_meters += leg_dist_m
        total_seconds += leg_dur_s
        legs.append(RouteLeg(distance_km=round(leg_dist_m / 1000.0, 3), duration_seconds=leg_dur_s))

    return RouteCalculationResult(
        distance_km=round(total_meters / 1000.0, 3),
        duration_seconds=total_seconds,
        geometry={"type": "LineString", "coordinates": coords},
        legs=legs,
    )


# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------

def test_01_fewer_than_2_stops_rejected(client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T01-1", "Stop 1")
    # Missing intermediate, start == end
    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s1.id), "intermediate_stop_ids": []},
    )
    assert resp.status_code == 400
    assert "cannot be the same" in resp.text


def test_02_start_stop_must_exist(client: TestClient, token_a: str, org_a: Organization, db: Session):
    s2 = create_stop(db, org_a.id, "T02-2", "Stop 2")
    random_id = str(uuid.uuid4())
    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": random_id, "end_stop_id": str(s2.id), "intermediate_stop_ids": []},
    )
    assert resp.status_code == 404
    assert f"Stop with ID '{random_id}' does not exist" in resp.text


def test_03_end_stop_must_exist(client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T03-1", "Stop 1")
    random_id = str(uuid.uuid4())
    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": random_id, "intermediate_stop_ids": []},
    )
    assert resp.status_code == 404
    assert f"Stop with ID '{random_id}' does not exist" in resp.text


def test_04_intermediate_stops_must_exist(client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T04-1", "Stop 1")
    s2 = create_stop(db, org_a.id, "T04-2", "Stop 2")
    random_id = str(uuid.uuid4())
    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s2.id), "intermediate_stop_ids": [random_id]},
    )
    assert resp.status_code == 404
    assert f"Stop with ID '{random_id}' does not exist" in resp.text


def test_05_unknown_stop_rejected(client: TestClient, token_a: str):
    random_1 = str(uuid.uuid4())
    random_2 = str(uuid.uuid4())
    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-UNKNOWN",
            "route_name": "Unknown Stops Route",
            "start_stop_id": random_1,
            "end_stop_id": random_2,
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code == 404


def test_06_cross_organization_stop_rejected(client: TestClient, token_a: str, org_a: Organization, org_b: Organization, db: Session):
    s_a = create_stop(db, org_a.id, "T06-A", "Org A Stop")
    s_b = create_stop(db, org_b.id, "T06-B", "Org B Stop")

    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s_a.id), "end_stop_id": str(s_b.id), "intermediate_stop_ids": []},
    )
    assert resp.status_code == 400
    assert "does not belong to your organization" in resp.text


def test_07_start_equals_end_rejected(client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T07-1", "Loop Stop")
    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-LOOP",
            "route_name": "Self Loop Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s1.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code == 400
    assert "cannot be the same" in resp.text


def test_08_duplicate_stop_rejected(client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T08-1", "Stop 1")
    s2 = create_stop(db, org_a.id, "T08-2", "Stop 2")
    s3 = create_stop(db, org_a.id, "T08-3", "Stop 3")

    # Start repeated in intermediate
    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s3.id), "intermediate_stop_ids": [str(s1.id)]},
    )
    assert resp.status_code == 400
    assert "cannot be repeated" in resp.text

    # Intermediate repeated: s2, s2
    resp2 = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s3.id), "intermediate_stop_ids": [str(s2.id), str(s2.id)]},
    )
    assert resp2.status_code == 400
    assert "Duplicate stops inside route sequence are not permitted" in resp2.text


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_09_exact_order_preserved(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T09-1", "Stop 1", 22.441, 88.421)
    s2 = create_stop(db, org_a.id, "T09-2", "Stop 2", 22.442, 88.422)
    s3 = create_stop(db, org_a.id, "T09-3", "Stop 3", 22.443, 88.423)
    s4 = create_stop(db, org_a.id, "T09-4", "Stop 4", 22.444, 88.424)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-EXACT-09",
            "route_name": "Exact Order Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s4.id),
            "intermediate_stop_ids": [str(s2.id), str(s3.id)],
        },
    )
    assert resp.status_code in [200, 201], resp.text
    route_id = resp.json()["id"]

    # Verify RouteStops sequence
    rs_resp = client.get(f"/api/admin/routes/{route_id}/stops", headers={"Authorization": f"Bearer {token_a}"})
    assert rs_resp.status_code == 200
    stops_data = rs_resp.json()
    assert [s["stop_id"] for s in stops_data] == [str(s1.id), str(s2.id), str(s3.id), str(s4.id)]
    assert [s["sequence_number"] for s in stops_data] == [1, 2, 3, 4]


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_10_no_alphabetical_reordering(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    sz = create_stop(db, org_a.id, "T10-Z", "Zebra Stop", 22.441, 88.421)
    sa = create_stop(db, org_a.id, "T10-A", "Apple Stop", 22.442, 88.422)
    sm = create_stop(db, org_a.id, "T10-M", "Mango Stop", 22.443, 88.423)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-NO-ALPHA",
            "route_name": "No Alpha Route",
            "start_stop_id": str(sz.id),
            "end_stop_id": str(sm.id),
            "intermediate_stop_ids": [str(sa.id)],
        },
    )
    assert resp.status_code in [200, 201]
    route_id = resp.json()["id"]

    rs_resp = client.get(f"/api/admin/routes/{route_id}/stops", headers={"Authorization": f"Bearer {token_a}"})
    stops_data = rs_resp.json()
    # Zebra -> Apple -> Mango, NOT Apple -> Mango -> Zebra
    assert [s["stop_code"] for s in stops_data] == ["T10-Z", "T10-A", "T10-M"]


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_11_no_geographic_reordering(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s_north = create_stop(db, org_a.id, "T11-N", "North", 22.60, 88.40)
    s_south = create_stop(db, org_a.id, "T11-S", "South", 22.40, 88.40)
    s_mid = create_stop(db, org_a.id, "T11-M", "Middle", 22.50, 88.40)

    # Order: North -> South -> Middle
    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-NO-GEO",
            "route_name": "No Geo Route",
            "start_stop_id": str(s_north.id),
            "end_stop_id": str(s_mid.id),
            "intermediate_stop_ids": [str(s_south.id)],
        },
    )
    assert resp.status_code in [200, 201]
    route_id = resp.json()["id"]

    rs_resp = client.get(f"/api/admin/routes/{route_id}/stops", headers={"Authorization": f"Bearer {token_a}"})
    stops_data = rs_resp.json()
    assert [s["stop_code"] for s in stops_data] == ["T11-N", "T11-S", "T11-M"]


def test_12_missing_coordinates_rejected(client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T12-1", "Valid Coords", 22.44, 88.42)
    s2 = Stop(
        organization_id=org_a.id,
        stop_code="T12-NULL",
        name="No Coords Stop",
        latitude=None,
        longitude=None,
        location=WKTElement("SRID=4326;POINT(0 0)", srid=4326),
        status=StopStatus.ACTIVE,
    )
    db.add(s2)
    db.commit()
    db.refresh(s2)

    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s2.id), "intermediate_stop_ids": []},
    )
    assert resp.status_code == 400
    assert "has no coordinates" in resp.text


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_13_valid_coordinates_invoke_routing(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T13-1", "Stop 1", 22.441, 88.421)
    s2 = create_stop(db, org_a.id, "T13-2", "Stop 2", 22.442, 88.422)

    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s2.id), "intermediate_stop_ids": []},
    )
    assert resp.status_code == 200
    assert mock_calc.called


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_14_routing_receives_coordinates_in_exact_stop_order(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T14-1", "Stop 1", 22.111, 88.111)
    s2 = create_stop(db, org_a.id, "T14-2", "Stop 2", 22.222, 88.222)
    s3 = create_stop(db, org_a.id, "T14-3", "Stop 3", 22.333, 88.333)

    client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s3.id), "intermediate_stop_ids": [str(s2.id)]},
    )
    # mock_calc call args: [(lon1, lat1), (lon2, lat2), (lon3, lat3)]
    args, _ = mock_calc.call_args
    waypoints = args[0]
    assert waypoints == [(88.111, 22.111), (88.222, 22.222), (88.333, 22.333)]


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_15_distance_comes_from_routing_provider(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T15-1", "Stop 1", 22.44, 88.42)
    s2 = create_stop(db, org_a.id, "T15-2", "Stop 2", 22.45, 88.43)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-DIST-15",
            "route_name": "Distance Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code in [200, 201]
    data = resp.json()
    # Mocked 1 leg = 1500m = 1.5 km
    assert data["distance_km"] == 1.5


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_16_geometry_comes_from_routing_provider(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T16-1", "Stop 1", 22.44, 88.42)
    s2 = create_stop(db, org_a.id, "T16-2", "Stop 2", 22.45, 88.43)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-GEOM-16",
            "route_name": "Geometry Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert data["geometry"]["type"] == "LineString"
    assert data["geometry"]["coordinates"] == [[88.42, 22.44], [88.43, 22.45]]


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_17_routing_duration_comes_from_routing_provider(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T17-1", "Stop 1", 22.44, 88.42)
    s2 = create_stop(db, org_a.id, "T17-2", "Stop 2", 22.45, 88.43)

    resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s2.id), "intermediate_stop_ids": []},
    )
    assert resp.status_code == 200
    assert resp.json()["duration_seconds"] == 180


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_18_leg_distances_are_populated_correctly(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T18-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T18-2", "Stop 2", 22.42, 88.42)
    s3 = create_stop(db, org_a.id, "T18-3", "Stop 3", 22.43, 88.43)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-LEGS-18",
            "route_name": "Legs Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s3.id),
            "intermediate_stop_ids": [str(s2.id)],
        },
    )
    assert resp.status_code in [200, 201]
    route_id = resp.json()["id"]

    rs_resp = client.get(f"/api/admin/routes/{route_id}/stops", headers={"Authorization": f"Bearer {token_a}"})
    stops_data = rs_resp.json()
    # Stop 1: 0.0 km, 0 sec
    # Stop 2: leg0 = 1.5 km, 180 sec
    # Stop 3: leg0 + leg1 = 1.5 + 1.7 = 3.2 km, 180 + 200 = 380 sec
    assert stops_data[0]["distance_from_start"] == 0.0
    assert stops_data[0]["nominal_travel_time_seconds"] == 0
    assert stops_data[1]["distance_from_start"] == 1.5
    assert stops_data[1]["nominal_travel_time_seconds"] == 180
    assert stops_data[2]["distance_from_start"] == 3.2
    assert stops_data[2]["nominal_travel_time_seconds"] == 380


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=RoutingServiceUnavailableException("OSRM down"))
def test_19_routing_failure_prevents_creation(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T19-1", "Stop 1", 22.44, 88.42)
    s2 = create_stop(db, org_a.id, "T19-2", "Stop 2", 22.45, 88.43)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-FAIL-19",
            "route_name": "Fail Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code == 503
    assert "Unable to calculate road distance right now" in resp.text


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=RoutingServiceUnavailableException("OSRM down"))
def test_20_routing_failure_creates_no_fake_geometry(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T20-1", "Stop 1", 22.44, 88.42)
    s2 = create_stop(db, org_a.id, "T20-2", "Stop 2", 22.45, 88.43)

    client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-FAIL-20",
            "route_name": "Fail Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    # Check that route was NOT persisted in DB
    route_db = db.execute(select(Route).where(Route.route_code == "R-FAIL-20")).scalar_one_or_none()
    assert route_db is None


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=RoutingServiceUnavailableException("OSRM down"))
def test_21_routing_failure_creates_no_fake_distance(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T21-1", "Stop 1", 22.44, 88.42)
    s2 = create_stop(db, org_a.id, "T21-2", "Stop 2", 22.45, 88.43)

    client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-FAIL-21",
            "route_name": "Fail Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    route_db = db.execute(select(Route).where(Route.route_code == "R-FAIL-21")).scalar_one_or_none()
    assert route_db is None


def test_22_fake_placeholder_geometry_rejected(client: TestClient, token_a: str):
    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-PLACEHOLDER",
            "route_name": "Placeholder Route",
            "distance_km": 12.0,
            "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        },
    )
    assert resp.status_code == 400
    assert "placeholder" in resp.text.lower()


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_23_duplicate_route_sequence_detected(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T23-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T23-2", "Stop 2", 22.42, 88.42)

    # Create original route
    res_orig = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-ORIG-23",
            "route_name": "Original Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert res_orig.status_code in [200, 201]

    # Preview with identical sequence
    preview_resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s1.id), "end_stop_id": str(s2.id), "intermediate_stop_ids": []},
    )
    assert preview_resp.status_code == 200
    dup = preview_resp.json()["duplicate_match"]
    assert dup is not None
    assert dup["is_duplicate"] is True
    assert dup["route_code"] == "R-ORIG-23"


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_24_different_sequence_not_duplicate(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T24-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T24-2", "Stop 2", 22.42, 88.42)

    # Route with s1 -> s2
    client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-ORIG-24",
            "route_name": "Original Route 24",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )

    # Preview with reverse sequence: s2 -> s1
    preview_resp = client.post(
        "/api/admin/routes/preview",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"start_stop_id": str(s2.id), "end_stop_id": str(s1.id), "intermediate_stop_ids": []},
    )
    assert preview_resp.status_code == 200
    assert preview_resp.json()["duplicate_match"] is None


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_25_start_is_routestop_sequence_1(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T25-1", "Start Stop", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T25-2", "End Stop", 22.42, 88.42)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-SEQ-25",
            "route_name": "Seq 25 Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code in [200, 201]
    route_id = resp.json()["id"]

    rs_resp = client.get(f"/api/admin/routes/{route_id}/stops", headers={"Authorization": f"Bearer {token_a}"})
    stops_data = rs_resp.json()
    assert stops_data[0]["stop_id"] == str(s1.id)
    assert stops_data[0]["sequence_number"] == 1


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_26_end_is_final_routestop_sequence(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T26-1", "Start Stop", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T26-2", "Mid Stop", 22.42, 88.42)
    s3 = create_stop(db, org_a.id, "T26-3", "End Stop", 22.43, 88.43)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-SEQ-26",
            "route_name": "Seq 26 Route",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s3.id),
            "intermediate_stop_ids": [str(s2.id)],
        },
    )
    assert resp.status_code in [200, 201]
    route_id = resp.json()["id"]

    rs_resp = client.get(f"/api/admin/routes/{route_id}/stops", headers={"Authorization": f"Bearer {token_a}"})
    stops_data = rs_resp.json()
    assert stops_data[-1]["stop_id"] == str(s3.id)
    assert stops_data[-1]["sequence_number"] == 3


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_27_route_code_remains_admin_controlled(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T27-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T27-2", "Stop 2", 22.42, 88.42)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "SD5-EXPRESS",
            "route_name": "Sonarpur Express",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code in [200, 201]
    assert resp.json()["route_code"] == "SD5-EXPRESS"


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_28_route_name_remains_admin_controlled(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T28-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T28-2", "Stop 2", 22.42, 88.42)

    custom_name = "Sonarpur Station - Kharibaria via Tollygunge"
    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "SD5-CUSTOM",
            "route_name": custom_name,
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code in [200, 201]
    assert resp.json()["route_name"] == custom_name


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_29_editing_stop_sequence_recalculates_route_distance(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T29-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T29-2", "Stop 2", 22.42, 88.42)
    s3 = create_stop(db, org_a.id, "T29-3", "Stop 3", 22.43, 88.43)

    # Route created with 2 stops (dist = 1.5 km)
    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-EDIT-29",
            "route_name": "Edit Route 29",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    assert resp.status_code in [200, 201]
    route_id = resp.json()["id"]
    assert resp.json()["distance_km"] == 1.5

    # Update stops: add s3 (3 stops, dist = 3.2 km)
    update_resp = client.post(
        f"/api/admin/routes/{route_id}/stops",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "stops": [
                {"stop_id": str(s1.id), "sequence_number": 1},
                {"stop_id": str(s2.id), "sequence_number": 2},
                {"stop_id": str(s3.id), "sequence_number": 3},
            ]
        },
    )
    assert update_resp.status_code == 200

    # Fetch updated route to confirm distance recalculated
    route_fetch = client.get(f"/api/admin/routes/{route_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert route_fetch.json()["distance_km"] == 3.2


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_30_editing_stop_sequence_recalculates_geometry(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T30-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T30-2", "Stop 2", 22.42, 88.42)
    s3 = create_stop(db, org_a.id, "T30-3", "Stop 3", 22.43, 88.43)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-GEOM-30",
            "route_name": "Geom Route 30",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    route_id = resp.json()["id"]

    # Now add s3
    client.post(
        f"/api/admin/routes/{route_id}/stops",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "stops": [
                {"stop_id": str(s1.id), "sequence_number": 1},
                {"stop_id": str(s2.id), "sequence_number": 2},
                {"stop_id": str(s3.id), "sequence_number": 3},
            ]
        },
    )

    route_fetch = client.get(f"/api/admin/routes/{route_id}", headers={"Authorization": f"Bearer {token_a}"})
    geom = route_fetch.json()["geometry"]
    assert len(geom["coordinates"]) == 3
    assert geom["coordinates"][2] == [88.43, 22.43]


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_31_existing_service_to_route_relationship_remains_valid(mock_calc, client: TestClient, token_a: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T31-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T31-2", "Stop 2", 22.42, 88.42)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-SERV-31",
            "route_name": "Service Route 31",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    route_id = resp.json()["id"]

    # Create service referencing this route
    svc_resp = client.post(
        "/api/admin/services",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_id": route_id,
            "service_code": "S-31",
            "service_name": "Service 31",
            "status": "ACTIVE",
        },
    )
    assert svc_resp.status_code == 200
    assert svc_resp.json()["route_id"] == route_id
    assert svc_resp.json()["route_code"] == "R-SERV-31"


@patch("app.services.routing_service.routing_service.provider.calculate_route", side_effect=mock_routing_success)
def test_32_tenant_isolation_remains_intact(mock_calc, client: TestClient, token_a: str, token_b: str, org_a: Organization, db: Session):
    s1 = create_stop(db, org_a.id, "T32-1", "Stop 1", 22.41, 88.41)
    s2 = create_stop(db, org_a.id, "T32-2", "Stop 2", 22.42, 88.42)

    resp = client.post(
        "/api/admin/routes",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "route_code": "R-TENANT-32",
            "route_name": "Tenant Route 32",
            "start_stop_id": str(s1.id),
            "end_stop_id": str(s2.id),
            "intermediate_stop_ids": [],
        },
    )
    route_id = resp.json()["id"]

    # Admin B attempts to access Route of Org A
    get_resp = client.get(f"/api/admin/routes/{route_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_resp.status_code == 404

    # Admin B attempts to update RouteStops of Org A
    update_resp = client.post(
        f"/api/admin/routes/{route_id}/stops",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"stops": []},
    )
    assert update_resp.status_code == 404
