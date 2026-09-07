"""
Comprehensive Build 4 Final Network MVP Test Suite.

Verifies:
1. Same org + same stop_code -> HTTP 409
2. Same org + different stop_code + same coordinates -> allowed and warning present (X-Data-Quality-Warning)
3. Same org + same name + different coordinates -> allowed
4. Different org + same stop_code -> allowed
5. Multiple aliases persist on one Stop
6. Passenger search finds official Stop name
7. Passenger search finds Stop alias
8. Multiple matching aliases still return one Stop entity (distinct)
9. Unreferenced Stop deletion cascades aliases
10. Referenced Stop deletion behavior remains safe (cannot delete stop referenced by route)
11. GET /api/passenger/cities returns active city (Kolkata)
12. City-scoped Stop search works
13. City-scoped service search returns all matching Services
14. Service whose Route misses origin/destination is excluded
15. Direction follows RouteStop sequence
16. Exact ordered route duplicate is detected
17. Different route order is not an exact duplicate
18. Multiple Services on same Route remain supported
19. Different Services may use different fare configurations
20. Admin organization/tenant isolation remains intact
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
from app.models.route import StopAlias
from app.core.security import get_password_hash


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with Session(engine) as s:
        yield s


@pytest.fixture
def org_kolkata(db: Session):
    suffix = uuid.uuid4().hex[:6]
    org = Organization(
        name=f"Kolkata Transit Authority {suffix}",
        city="Kolkata",
        status="ACTIVE"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def org_bengaluru(db: Session):
    suffix = uuid.uuid4().hex[:6]
    org = Organization(
        name=f"Bengaluru BMTC {suffix}",
        city="Bengaluru",
        status="ACTIVE"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def admin_token_kolkata(client: TestClient, db: Session, org_kolkata: Organization):
    suffix = uuid.uuid4().hex[:6]
    email = f"admin_kolkata_{suffix}@test.local"
    admin = User(
        organization_id=org_kolkata.id,
        name="Kolkata Admin",
        email=email,
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.FLEET_ADMIN,
    )
    db.add(admin)
    db.commit()

    resp = client.post("/api/admin/login", json={"email": email, "password": "AdminPass123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def admin_token_bengaluru(client: TestClient, db: Session, org_bengaluru: Organization):
    suffix = uuid.uuid4().hex[:6]
    email = f"admin_bengaluru_{suffix}@test.local"
    admin = User(
        organization_id=org_bengaluru.id,
        name="Bengaluru Admin",
        email=email,
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.FLEET_ADMIN,
    )
    db.add(admin)
    db.commit()

    resp = client.post("/api/admin/login", json={"email": email, "password": "AdminPass123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def make_route_payload(code: str, name: str, distance: float = 10.0):
    return {
        "route_code": code,
        "route_name": name,
        "distance_km": distance,
        "status": "ACTIVE",
        "geometry": {
            "type": "LineString",
            "coordinates": [[88.1, 22.1], [88.2, 22.2], [88.3, 22.3]]
        }
    }


def make_schedule_payload(direction: str = "A_TO_B"):
    return {
        "direction": direction,
        "start_time": "06:00:00",
        "end_time": "22:00:00",
        "typical_interval_minutes": 15,
        "days_of_week": [0, 1, 2, 3, 4, 5, 6],
        "effective_from": "2026-01-01T00:00:00Z",
        "status": "ACTIVE"
    }


# =========================================================================
# 1. Same org + same stop_code -> HTTP 409
# =========================================================================
def test_01_same_org_duplicate_stop_code_rejected(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    stop_payload = {
        "stop_code": "STP-001",
        "name": "Central Station",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "status": "ACTIVE",
        "aliases": ["Central"]
    }
    r1 = client.post("/api/admin/stops", json=stop_payload, headers=headers)
    assert r1.status_code == 201, r1.text

    # Attempt second stop with same stop_code in same org
    r2 = client.post("/api/admin/stops", json=stop_payload, headers=headers)
    assert r2.status_code == 409
    assert "already exists in this organization" in r2.json()["detail"]


# =========================================================================
# 2. Same org + different stop_code + same coordinates -> allowed and warning present
# =========================================================================
def test_02_same_org_same_coordinates_allowed_with_warning(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    p1 = {
        "stop_code": "STP-002A",
        "name": "Howrah Station Bay 1",
        "latitude": 22.5850,
        "longitude": 88.3420,
        "status": "ACTIVE"
    }
    r1 = client.post("/api/admin/stops", json=p1, headers=headers)
    assert r1.status_code == 201

    p2 = {
        "stop_code": "STP-002B",
        "name": "Howrah Station Bay 2",
        "latitude": 22.5850,
        "longitude": 88.3420,
        "status": "ACTIVE"
    }
    r2 = client.post("/api/admin/stops", json=p2, headers=headers)
    assert r2.status_code == 201
    assert "x-data-quality-warning" in [k.lower() for k in r2.headers.keys()]


# =========================================================================
# 3. Same org + same name + different coordinates -> allowed
# =========================================================================
def test_03_same_org_same_name_different_coordinates_allowed(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    p1 = {
        "stop_code": "STP-003A",
        "name": "Park Street",
        "latitude": 22.5500,
        "longitude": 88.3500,
        "status": "ACTIVE"
    }
    r1 = client.post("/api/admin/stops", json=p1, headers=headers)
    assert r1.status_code == 201

    p2 = {
        "stop_code": "STP-003B",
        "name": "Park Street",
        "latitude": 22.5550,
        "longitude": 88.3550,
        "status": "ACTIVE"
    }
    r2 = client.post("/api/admin/stops", json=p2, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["id"] != r1.json()["id"]


# =========================================================================
# 4. Different org + same stop_code -> allowed
# =========================================================================
def test_04_different_org_same_stop_code_allowed(client: TestClient, admin_token_kolkata: str, admin_token_bengaluru: str):
    payload = {
        "stop_code": "SHARED-CODE-01",
        "name": "Airport Terminus",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "status": "ACTIVE"
    }
    r1 = client.post("/api/admin/stops", json=payload, headers={"Authorization": f"Bearer {admin_token_kolkata}"})
    assert r1.status_code == 201

    r2 = client.post("/api/admin/stops", json=payload, headers={"Authorization": f"Bearer {admin_token_bengaluru}"})
    assert r2.status_code == 201
    assert r1.json()["organization_id"] != r2.json()["organization_id"]


# =========================================================================
# 5. Multiple aliases persist on one Stop
# =========================================================================
def test_05_multiple_aliases_persist_on_stop(client: TestClient, admin_token_kolkata: str, db: Session):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    payload = {
        "stop_code": "STP-005",
        "name": "Shivaji Nagar Bus Stop",
        "latitude": 22.5600,
        "longitude": 88.3600,
        "status": "ACTIVE",
        "aliases": ["Hanuman Mandir", "Mandir Stop", "Shivaji Nagar Bus Stand"]
    }
    r = client.post("/api/admin/stops", json=payload, headers=headers)
    assert r.status_code == 201
    created = r.json()
    assert len(created["aliases"]) == 3
    assert "Hanuman Mandir" in created["aliases"]

    stop_uuid = uuid.UUID(created["id"])
    aliases_db = db.execute(select(StopAlias).where(StopAlias.stop_id == stop_uuid)).scalars().all()
    assert len(aliases_db) == 3
    alias_names = [a.alias_name for a in aliases_db]
    assert "Hanuman Mandir" in alias_names
    assert "Mandir Stop" in alias_names


# =========================================================================
# 6. Passenger search finds official Stop name
# =========================================================================
def test_06_passenger_search_finds_official_stop_name(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    client.post("/api/admin/stops", json={
        "stop_code": "STP-006",
        "name": "Victoria Memorial Gate 1",
        "latitude": 22.5448,
        "longitude": 88.3426,
        "status": "ACTIVE",
        "aliases": ["Victoria Hall"]
    }, headers=headers)

    r = client.get("/api/passenger/stops?city=Kolkata&search=Victoria Memorial")
    assert r.status_code == 200
    results = r.json()
    assert any(s["stop_code"] == "STP-006" for s in results)


# =========================================================================
# 7. Passenger search finds Stop alias
# =========================================================================
def test_07_passenger_search_finds_stop_alias(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    r_create = client.post("/api/admin/stops", json={
        "stop_code": "STP-007",
        "name": "Esplanade Complex",
        "latitude": 22.5645,
        "longitude": 88.3510,
        "status": "ACTIVE",
        "aliases": ["Dharmatala Chottor", "Curzon Park"]
    }, headers=headers)
    stop_id = r_create.json()["id"]

    r = client.get("/api/passenger/stops?city=Kolkata&search=Dharmatala")
    assert r.status_code == 200
    results = r.json()
    assert len(results) >= 1
    found = next((s for s in results if s["id"] == stop_id), None)
    assert found is not None
    assert found["name"] == "Esplanade Complex"


# =========================================================================
# 8. Multiple matching aliases still return one Stop entity
# =========================================================================
def test_08_multiple_matching_aliases_return_one_distinct_stop(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    r_create = client.post("/api/admin/stops", json={
        "stop_code": "STP-008",
        "name": "Dakshineswar Main Stop",
        "latitude": 22.6534,
        "longitude": 88.3575,
        "status": "ACTIVE",
        "aliases": ["Kali Mandir Dakshineswar", "Dakshineswar Ghat Mandir"]
    }, headers=headers)
    stop_id = r_create.json()["id"]

    r = client.get("/api/passenger/stops?city=Kolkata&search=Dakshineswar")
    assert r.status_code == 200
    results = r.json()
    matching = [s for s in results if s["id"] == stop_id]
    assert len(matching) == 1


# =========================================================================
# 9. Unreferenced Stop deletion cascades aliases
# =========================================================================
def test_09_unreferenced_stop_deletion_cascades_aliases(client: TestClient, admin_token_kolkata: str, db: Session):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    r_create = client.post("/api/admin/stops", json={
        "stop_code": "STP-009",
        "name": "Temporary Stop",
        "latitude": 22.5000,
        "longitude": 88.3000,
        "status": "ACTIVE",
        "aliases": ["Temp Alias 1", "Temp Alias 2"]
    }, headers=headers)
    stop_id = r_create.json()["id"]
    stop_uuid = uuid.UUID(stop_id)

    aliases_before = db.execute(select(StopAlias).where(StopAlias.stop_id == stop_uuid)).scalars().all()
    assert len(aliases_before) == 2

    r_del = client.delete(f"/api/admin/stops/{stop_id}", headers=headers)
    assert r_del.status_code == 204

    aliases_after = db.execute(select(StopAlias).where(StopAlias.stop_id == stop_uuid)).scalars().all()
    assert len(aliases_after) == 0


# =========================================================================
# 10. Referenced Stop deletion behavior remains safe
# =========================================================================
def test_10_referenced_stop_deletion_blocked(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    s1 = client.post("/api/admin/stops", json={"stop_code": "STP-010A", "name": "Stop A", "latitude": 22.1, "longitude": 88.1}, headers=headers).json()
    s2 = client.post("/api/admin/stops", json={"stop_code": "STP-010B", "name": "Stop B", "latitude": 22.2, "longitude": 88.2}, headers=headers).json()

    route = client.post("/api/admin/routes", json=make_route_payload("R-010", "Route 10"), headers=headers).json()
    assert "id" in route, route

    client.post(f"/api/admin/routes/{route['id']}/stops", json={
        "stops": [
            {"stop_id": s1["id"], "sequence_number": 1, "distance_from_start": 0.0},
            {"stop_id": s2["id"], "sequence_number": 2, "distance_from_start": 5.0},
        ]
    }, headers=headers)

    r_del = client.delete(f"/api/admin/stops/{s1['id']}", headers=headers)
    assert r_del.status_code == 400
    assert "referenced by routes" in r_del.json()["detail"]


# =========================================================================
# 11. GET /api/passenger/cities returns active city (Kolkata)
# =========================================================================
def test_11_get_passenger_cities_returns_active_city(client: TestClient, org_kolkata: Organization):
    r = client.get("/api/passenger/cities")
    assert r.status_code == 200
    cities = r.json()
    assert len(cities) >= 1
    assert any(c["name"] == "Kolkata" and c["id"] == "kolkata" for c in cities)


# =========================================================================
# 12. City-scoped Stop search works
# =========================================================================
def test_12_city_scoped_stop_search(client: TestClient, admin_token_kolkata: str, admin_token_bengaluru: str):
    client.post("/api/admin/stops", json={
        "stop_code": "KOL-STOP-12", "name": "Kolkata City Plaza", "latitude": 22.5, "longitude": 88.3
    }, headers={"Authorization": f"Bearer {admin_token_kolkata}"})

    client.post("/api/admin/stops", json={
        "stop_code": "BLR-STOP-12", "name": "Bengaluru City Plaza", "latitude": 12.9, "longitude": 77.5
    }, headers={"Authorization": f"Bearer {admin_token_bengaluru}"})

    r_kol = client.get("/api/passenger/stops?city=Kolkata&search=City Plaza")
    assert r_kol.status_code == 200
    kol_stops = r_kol.json()
    assert any(s["stop_code"] == "KOL-STOP-12" for s in kol_stops)
    assert not any(s["stop_code"] == "BLR-STOP-12" for s in kol_stops)


# =========================================================================
# 13. City-scoped service search returns all matching Services
# =========================================================================
def test_13_city_scoped_service_search_returns_matching_services(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    s_orig = client.post("/api/admin/stops", json={"stop_code": "S13-O", "name": "Origin Hub", "latitude": 22.51, "longitude": 88.31}, headers=headers).json()
    s_mid = client.post("/api/admin/stops", json={"stop_code": "S13-M", "name": "Mid Hub", "latitude": 22.52, "longitude": 88.32}, headers=headers).json()
    s_dest = client.post("/api/admin/stops", json={"stop_code": "S13-D", "name": "Dest Hub", "latitude": 22.53, "longitude": 88.33}, headers=headers).json()

    # Route 1: O -> M -> D
    r1 = client.post("/api/admin/routes", json=make_route_payload("R13-1", "Corridor 1"), headers=headers).json()
    client.post(f"/api/admin/routes/{r1['id']}/stops", json={
        "stops": [
            {"stop_id": s_orig["id"], "sequence_number": 1, "distance_from_start": 0.0},
            {"stop_id": s_mid["id"], "sequence_number": 2, "distance_from_start": 5.0},
            {"stop_id": s_dest["id"], "sequence_number": 3, "distance_from_start": 10.0},
        ]
    }, headers=headers)

    # Service 1 on R1
    srv1 = client.post("/api/admin/services", json={
        "route_id": r1["id"], "service_code": "SRV13-1", "service_name": "Express 1", "status": "ACTIVE"
    }, headers=headers).json()
    client.post(f"/api/admin/services/{srv1['id']}/schedules", json=make_schedule_payload("A_TO_B"), headers=headers)

    # Route 2: O -> D (direct)
    r2 = client.post("/api/admin/routes", json=make_route_payload("R13-2", "Direct Path"), headers=headers).json()
    client.post(f"/api/admin/routes/{r2['id']}/stops", json={
        "stops": [
            {"stop_id": s_orig["id"], "sequence_number": 1, "distance_from_start": 0.0},
            {"stop_id": s_dest["id"], "sequence_number": 2, "distance_from_start": 8.0},
        ]
    }, headers=headers)

    # Service 2 on R2
    srv2 = client.post("/api/admin/services", json={
        "route_id": r2["id"], "service_code": "SRV13-2", "service_name": "Direct Express", "status": "ACTIVE"
    }, headers=headers).json()
    client.post(f"/api/admin/services/{srv2['id']}/schedules", json=make_schedule_payload("A_TO_B"), headers=headers)

    r_search = client.get(f"/api/passenger/services/search?city=Kolkata&origin_id={s_orig['id']}&destination_id={s_dest['id']}")
    assert r_search.status_code == 200
    results = r_search.json()
    srv_ids = [res["service_id"] for res in results]
    assert srv1["id"] in srv_ids
    assert srv2["id"] in srv_ids


# =========================================================================
# 14. Service whose Route misses origin/destination is excluded
# =========================================================================
def test_14_service_missing_stops_excluded(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    s_a = client.post("/api/admin/stops", json={"stop_code": "S14-A", "name": "Stop 14A", "latitude": 22.1, "longitude": 88.1}, headers=headers).json()
    s_b = client.post("/api/admin/stops", json={"stop_code": "S14-B", "name": "Stop 14B", "latitude": 22.2, "longitude": 88.2}, headers=headers).json()
    s_c = client.post("/api/admin/stops", json={"stop_code": "S14-C", "name": "Stop 14C", "latitude": 22.3, "longitude": 88.3}, headers=headers).json()

    r = client.post("/api/admin/routes", json=make_route_payload("R14", "AB Route"), headers=headers).json()
    client.post(f"/api/admin/routes/{r['id']}/stops", json={
        "stops": [
            {"stop_id": s_a["id"], "sequence_number": 1, "distance_from_start": 0.0},
            {"stop_id": s_b["id"], "sequence_number": 2, "distance_from_start": 5.0},
        ]
    }, headers=headers)
    srv = client.post("/api/admin/services", json={"route_id": r["id"], "service_code": "SRV14", "service_name": "AB Service", "status": "ACTIVE"}, headers=headers).json()
    client.post(f"/api/admin/services/{srv['id']}/schedules", json=make_schedule_payload("A_TO_B"), headers=headers)

    res = client.get(f"/api/passenger/services/search?city=Kolkata&origin_id={s_a['id']}&destination_id={s_c['id']}").json()
    assert not any(item["service_id"] == srv["id"] for item in res)


# =========================================================================
# 15. Direction follows RouteStop sequence
# =========================================================================
def test_15_direction_follows_routestop_sequence(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    s_first = client.post("/api/admin/stops", json={"stop_code": "S15-1", "name": "Stop 1", "latitude": 22.1, "longitude": 88.1}, headers=headers).json()
    s_last = client.post("/api/admin/stops", json={"stop_code": "S15-2", "name": "Stop 2", "latitude": 22.2, "longitude": 88.2}, headers=headers).json()

    route = client.post("/api/admin/routes", json=make_route_payload("R15", "Sequence Route"), headers=headers).json()
    client.post(f"/api/admin/routes/{route['id']}/stops", json={
        "stops": [
            {"stop_id": s_first["id"], "sequence_number": 1, "distance_from_start": 0.0},
            {"stop_id": s_last["id"], "sequence_number": 2, "distance_from_start": 5.0},
        ]
    }, headers=headers)

    srv = client.post("/api/admin/services", json={"route_id": route["id"], "service_code": "SRV15", "service_name": "BiDirectional", "status": "ACTIVE"}, headers=headers).json()
    client.post(f"/api/admin/services/{srv['id']}/schedules", json=make_schedule_payload("A_TO_B"), headers=headers)
    client.post(f"/api/admin/services/{srv['id']}/schedules", json=make_schedule_payload("B_TO_A"), headers=headers)

    fwd = client.get(f"/api/passenger/services/search?city=Kolkata&origin_id={s_first['id']}&destination_id={s_last['id']}").json()
    assert any(item["service_id"] == srv["id"] and item["direction"] == "A_TO_B" for item in fwd)

    rev = client.get(f"/api/passenger/services/search?city=Kolkata&origin_id={s_last['id']}&destination_id={s_first['id']}").json()
    assert any(item["service_id"] == srv["id"] and item["direction"] == "B_TO_A" for item in rev)


# =========================================================================
# 16. Exact ordered route duplicate is detected
# =========================================================================
def test_16_exact_ordered_route_duplicate_detected(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    s_a = client.post("/api/admin/stops", json={"stop_code": "S16-A", "name": "Stop 16A", "latitude": 22.1, "longitude": 88.1}, headers=headers).json()
    s_b = client.post("/api/admin/stops", json={"stop_code": "S16-B", "name": "Stop 16B", "latitude": 22.2, "longitude": 88.2}, headers=headers).json()
    s_c = client.post("/api/admin/stops", json={"stop_code": "S16-C", "name": "Stop 16C", "latitude": 22.3, "longitude": 88.3}, headers=headers).json()

    r1 = client.post("/api/admin/routes", json=make_route_payload("R16-1", "Original Corridor"), headers=headers).json()
    client.post(f"/api/admin/routes/{r1['id']}/stops", json={
        "stops": [
            {"stop_id": s_a["id"], "sequence_number": 1, "distance_from_start": 0.0},
            {"stop_id": s_b["id"], "sequence_number": 2, "distance_from_start": 5.0},
            {"stop_id": s_c["id"], "sequence_number": 3, "distance_from_start": 10.0},
        ]
    }, headers=headers)

    r2 = client.post("/api/admin/routes", json=make_route_payload("R16-2", "Proposed Duplicate"), headers=headers).json()
    check_resp = client.post(f"/api/admin/routes/{r2['id']}/check-duplicate-stops", json={
        "stops": [s_a["id"], s_b["id"], s_c["id"]]
    }, headers=headers)
    assert check_resp.status_code == 200
    data = check_resp.json()
    assert data["is_duplicate"] is True
    assert data["existing_route_id"] == r1["id"]
    assert data["route_code"] == "R16-1"
    assert data["route_name"] == "Original Corridor"


# =========================================================================
# 17. Different route order is not an exact duplicate
# =========================================================================
def test_17_different_route_order_not_duplicate(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    s_a = client.post("/api/admin/stops", json={"stop_code": "S17-A", "name": "Stop 17A", "latitude": 22.1, "longitude": 88.1}, headers=headers).json()
    s_b = client.post("/api/admin/stops", json={"stop_code": "S17-B", "name": "Stop 17B", "latitude": 22.2, "longitude": 88.2}, headers=headers).json()
    s_c = client.post("/api/admin/stops", json={"stop_code": "S17-C", "name": "Stop 17C", "latitude": 22.3, "longitude": 88.3}, headers=headers).json()

    r1 = client.post("/api/admin/routes", json=make_route_payload("R17-1", "Order 1"), headers=headers).json()
    client.post(f"/api/admin/routes/{r1['id']}/stops", json={
        "stops": [
            {"stop_id": s_a["id"], "sequence_number": 1, "distance_from_start": 0.0},
            {"stop_id": s_b["id"], "sequence_number": 2, "distance_from_start": 5.0},
            {"stop_id": s_c["id"], "sequence_number": 3, "distance_from_start": 10.0},
        ]
    }, headers=headers)

    r2 = client.post("/api/admin/routes", json=make_route_payload("R17-2", "Order 2"), headers=headers).json()
    check_resp = client.post(f"/api/admin/routes/{r2['id']}/check-duplicate-stops", json={
        "stops": [s_a["id"], s_c["id"], s_b["id"]]
    }, headers=headers)
    assert check_resp.status_code == 200
    assert check_resp.json()["is_duplicate"] is False


# =========================================================================
# 18. Multiple Services on same Route remain supported
# =========================================================================
def test_18_multiple_services_on_same_route(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    r = client.post("/api/admin/routes", json=make_route_payload("R18", "Shared Route"), headers=headers).json()

    srv_a = client.post("/api/admin/services", json={
        "route_id": r["id"], "service_code": "SRV18-A", "service_name": "Standard Service", "status": "ACTIVE"
    }, headers=headers)
    assert srv_a.status_code in (200, 201), srv_a.text

    srv_b = client.post("/api/admin/services", json={
        "route_id": r["id"], "service_code": "SRV18-B", "service_name": "Express Service", "status": "ACTIVE"
    }, headers=headers)
    assert srv_b.status_code in (200, 201), srv_b.text
    assert srv_a.json()["route_id"] == srv_b.json()["route_id"]


# =========================================================================
# 19. Different Services may use different fare configurations
# =========================================================================
def test_19_different_services_use_different_fares(client: TestClient, admin_token_kolkata: str):
    headers = {"Authorization": f"Bearer {admin_token_kolkata}"}
    fc1_res = client.post("/api/admin/fares/", json={
        "name": "Standard Slabs",
        "currency": "INR",
        "effective_from": "2026-01-01",
        "slabs": [
            {"min_distance_km": 0, "max_distance_km": 5, "fare_amount": 10},
            {"min_distance_km": 5, "max_distance_km": 100, "fare_amount": 20}
        ]
    }, headers=headers)
    assert fc1_res.status_code == 200, fc1_res.text
    fc1 = fc1_res.json()

    fc2_res = client.post("/api/admin/fares/", json={
        "name": "AC Express Slabs",
        "currency": "INR",
        "effective_from": "2026-01-01",
        "slabs": [
            {"min_distance_km": 0, "max_distance_km": 5, "fare_amount": 30},
            {"min_distance_km": 5, "max_distance_km": 100, "fare_amount": 50}
        ]
    }, headers=headers)
    assert fc2_res.status_code == 200, fc2_res.text
    fc2 = fc2_res.json()

    route = client.post("/api/admin/routes", json=make_route_payload("R19", "Fare Test Route"), headers=headers).json()

    srv_std = client.post("/api/admin/services", json={
        "route_id": route["id"], "service_code": "SRV19-STD", "service_name": "Standard Bus", "fare_configuration_id": fc1["id"], "status": "ACTIVE"
    }, headers=headers).json()

    srv_ac = client.post("/api/admin/services", json={
        "route_id": route["id"], "service_code": "SRV19-AC", "service_name": "AC Express", "fare_configuration_id": fc2["id"], "status": "ACTIVE"
    }, headers=headers).json()

    assert srv_std["fare_configuration_id"] == fc1["id"]
    assert srv_ac["fare_configuration_id"] == fc2["id"]
    assert srv_std["fare_configuration_id"] != srv_ac["fare_configuration_id"]


# =========================================================================
# 20. Admin organization/tenant isolation remains intact
# =========================================================================
def test_20_admin_tenant_isolation_intact(client: TestClient, admin_token_kolkata: str, admin_token_bengaluru: str):
    kol_stop = client.post("/api/admin/stops", json={
        "stop_code": "ISO-KOL-01", "name": "Kolkata Depot", "latitude": 22.5, "longitude": 88.3
    }, headers={"Authorization": f"Bearer {admin_token_kolkata}"}).json()

    blr_stop = client.post("/api/admin/stops", json={
        "stop_code": "ISO-BLR-01", "name": "Bengaluru Depot", "latitude": 12.9, "longitude": 77.5
    }, headers={"Authorization": f"Bearer {admin_token_bengaluru}"}).json()

    kol_list = client.get("/api/admin/stops", headers={"Authorization": f"Bearer {admin_token_kolkata}"}).json()
    assert any(s["id"] == kol_stop["id"] for s in kol_list)
    assert not any(s["id"] == blr_stop["id"] for s in kol_list)

    r_hack = client.put(f"/api/admin/stops/{kol_stop['id']}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {admin_token_bengaluru}"})
    assert r_hack.status_code == 404
