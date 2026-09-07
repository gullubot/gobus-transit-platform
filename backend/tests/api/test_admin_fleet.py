import uuid
from datetime import datetime, timezone, timedelta
import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, Direction, VehicleStatus, ServiceStatus, RouteStatus
from app.models.vehicle import Vehicle
from app.models.service import Service, DepotSchedule
from app.models.route import Route
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
    org = Organization(name=f"Org A Fleet {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_fleet_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Fleet A",
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
    org = Organization(name=f"Org B Fleet {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_b_token(client: TestClient, session: Session, org_b: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_fleet_b_{suffix}@demo.com"
    admin = User(
        organization_id=org_b.id,
        name="Admin Fleet B",
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
def vehicle_b(session: Session, org_b: Organization):
    suffix = uuid.uuid4().hex[:8]
    vehicle = Vehicle(
        organization_id=org_b.id,
        vehicle_number=f"VB_{suffix}",
        registration_number="REG-B123",
        vehicle_type="BUS",
        status=VehicleStatus.ACTIVE
    )
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle

@pytest.fixture
def service_b(session: Session, org_b: Organization):
    # Need a route first
    route = Route(
        organization_id=org_b.id,
        route_code=f"RB_{uuid.uuid4().hex[:8]}",
        route_name="Route B",
        distance_km=10.0,
        geometry="SRID=4326;LINESTRING(10 10, 11 11)",
        status=RouteStatus.ACTIVE
    )
    session.add(route)
    session.commit()
    
    service = Service(
        organization_id=org_b.id,
        route_id=route.id,
        service_code=f"SB_{uuid.uuid4().hex[:8]}",
        service_name="Service B",
        status=ServiceStatus.ACTIVE
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    return service

# -----------------------------------------------------------------------------
# VEHICLE TESTS
# -----------------------------------------------------------------------------

def test_create_vehicle(client: TestClient, admin_token: str):
    suffix = uuid.uuid4().hex[:8]
    data = {
        "vehicle_number": f"VA_{suffix}",
        "registration_number": "REG-A123",
        "vehicle_type": "BUS",
        "status": "ACTIVE"
    }
    response = client.post("/api/admin/vehicles", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["vehicle_number"] == f"VA_{suffix}"
    assert "id" in res_data
    return res_data["id"]

def test_get_vehicles_isolation(client: TestClient, admin_token: str, admin_b_token: str, vehicle_b: Vehicle):
    # Admin A shouldn't see Admin B's vehicle
    resp_a = client.get("/api/admin/vehicles", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_a.status_code == 200
    ids_a = [v["id"] for v in resp_a.json()]
    assert str(vehicle_b.id) not in ids_a

    # Admin B should see Admin B's vehicle
    resp_b = client.get("/api/admin/vehicles", headers={"Authorization": f"Bearer {admin_b_token}"})
    assert resp_b.status_code == 200
    ids_b = [v["id"] for v in resp_b.json()]
    assert str(vehicle_b.id) in ids_b

def test_update_vehicle_isolation(client: TestClient, admin_token: str, vehicle_b: Vehicle):
    # Admin A cannot update Admin B's vehicle
    data = {"vehicle_type": "MINIBUS"}
    response = client.put(f"/api/admin/vehicles/{vehicle_b.id}", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 404

def test_decommission_vehicle(client: TestClient, admin_token: str):
    v_id = test_create_vehicle(client, admin_token)
    
    # Decommission it
    response = client.delete(f"/api/admin/vehicles/{v_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 204
    
    # Verify status changed
    get_resp = client.get(f"/api/admin/vehicles/{v_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "DECOMMISSIONED"

def test_decommission_vehicle_isolation(client: TestClient, admin_token: str, vehicle_b: Vehicle):
    # Admin A cannot decommission Admin B's vehicle
    response = client.delete(f"/api/admin/vehicles/{vehicle_b.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 404

# -----------------------------------------------------------------------------
# DEPOT SCHEDULE TESTS
# -----------------------------------------------------------------------------

def test_create_depot_schedule(client: TestClient, admin_token: str, session: Session, org_a: Organization):
    # Create Route & Service for Org A
    route = Route(
        organization_id=org_a.id,
        route_code=f"RA_{uuid.uuid4().hex[:8]}",
        route_name="Route A",
        distance_km=10.0,
        geometry="SRID=4326;LINESTRING(10 10, 11 11)",
        status=RouteStatus.ACTIVE
    )
    session.add(route)
    session.commit()
    
    service = Service(
        organization_id=org_a.id,
        route_id=route.id,
        service_code=f"SA_{uuid.uuid4().hex[:8]}",
        service_name="Service A",
        status=ServiceStatus.ACTIVE
    )
    session.add(service)
    
    # Create Vehicle for Org A
    vehicle = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"VA_SCHED_{uuid.uuid4().hex[:8]}",
        vehicle_type="BUS",
        status=VehicleStatus.ACTIVE
    )
    session.add(vehicle)
    session.commit()

    data = {
        "vehicle_id": str(vehicle.id),
        "service_id": str(service.id),
        "direction": "A_TO_B",
        "operating_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "planned_departure": datetime.now(timezone.utc).isoformat(),
        "status": "PLANNED"
    }
    
    response = client.post("/api/admin/depot-schedules", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["vehicle_id"] == str(vehicle.id)
    assert res_data["service_id"] == str(service.id)
    return res_data["id"]

def test_create_depot_schedule_cross_tenant_vehicle(client: TestClient, admin_token: str, session: Session, org_a: Organization, vehicle_b: Vehicle):
    # Try to use Org B's vehicle
    route = Route(organization_id=org_a.id, route_code=f"RA_{uuid.uuid4().hex[:8]}", route_name="Route A", distance_km=10.0, geometry="SRID=4326;LINESTRING(1 1, 2 2)", status=RouteStatus.ACTIVE)
    session.add(route)
    session.commit()
    service = Service(organization_id=org_a.id, route_id=route.id, service_code=f"SA_{uuid.uuid4().hex[:8]}", service_name="Service A", status=ServiceStatus.ACTIVE)
    session.add(service)
    session.commit()
    
    data = {
        "vehicle_id": str(vehicle_b.id),  # Org B's vehicle
        "service_id": str(service.id),
        "direction": "A_TO_B",
        "operating_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "planned_departure": datetime.now(timezone.utc).isoformat(),
        "status": "PLANNED"
    }
    
    response = client.post("/api/admin/depot-schedules", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 400
    assert "not belong to your organization" in response.json()["detail"]

def test_create_depot_schedule_cross_tenant_service(client: TestClient, admin_token: str, session: Session, org_a: Organization, service_b: Service):
    # Try to use Org B's service
    vehicle = Vehicle(organization_id=org_a.id, vehicle_number=f"VA_{uuid.uuid4().hex[:8]}", vehicle_type="BUS", status=VehicleStatus.ACTIVE)
    session.add(vehicle)
    session.commit()
    
    data = {
        "vehicle_id": str(vehicle.id),
        "service_id": str(service_b.id), # Org B's service
        "direction": "A_TO_B",
        "operating_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "planned_departure": datetime.now(timezone.utc).isoformat(),
        "status": "PLANNED"
    }
    
    response = client.post("/api/admin/depot-schedules", headers={"Authorization": f"Bearer {admin_token}"}, json=data)
    assert response.status_code == 400
    assert "not belong to your organization" in response.json()["detail"]


def test_get_vehicles_service_scoped(client: TestClient, admin_token: str, session: Session, org_a: Organization):
    # Create Route and Services for Org A
    route = Route(organization_id=org_a.id, route_code=f"RA_{uuid.uuid4().hex[:8]}", route_name="Route A", distance_km=10.0, geometry="SRID=4326;LINESTRING(1 1, 2 2)", status=RouteStatus.ACTIVE)
    session.add(route)
    session.commit()

    service_1 = Service(organization_id=org_a.id, route_id=route.id, service_code=f"SA_{uuid.uuid4().hex[:8]}", service_name="Service 1", status=ServiceStatus.ACTIVE)
    service_2 = Service(organization_id=org_a.id, route_id=route.id, service_code=f"SA_{uuid.uuid4().hex[:8]}", service_name="Service 2", status=ServiceStatus.ACTIVE)
    session.add_all([service_1, service_2])
    session.commit()

    # Create Vehicle assigned to Service 1
    resp_v1 = client.post(
        "/api/admin/vehicles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "vehicle_number": f"V1_{uuid.uuid4().hex[:8]}",
            "registration_number": "REG-1",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": str(service_1.id)
        }
    )
    assert resp_v1.status_code == 200
    v1_id = resp_v1.json()["id"]

    # Create Vehicle assigned to Service 2
    resp_v2 = client.post(
        "/api/admin/vehicles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "vehicle_number": f"V2_{uuid.uuid4().hex[:8]}",
            "registration_number": "REG-2",
            "vehicle_type": "MINIBUS",
            "status": "ACTIVE",
            "service_id": str(service_2.id)
        }
    )
    assert resp_v2.status_code == 200
    v2_id = resp_v2.json()["id"]

    # Query for Service 1 fleet: must only contain v1
    resp_s1 = client.get(f"/api/admin/vehicles?service_id={service_1.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_s1.status_code == 200
    s1_ids = [v["id"] for v in resp_s1.json()]
    assert v1_id in s1_ids
    assert v2_id not in s1_ids

    # Query for Service 2 fleet: must only contain v2
    resp_s2 = client.get(f"/api/admin/vehicles?service_id={service_2.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_s2.status_code == 200
    s2_ids = [v["id"] for v in resp_s2.json()]
    assert v2_id in s2_ids
    assert v1_id not in s2_ids


def test_assign_vehicle_crew_lifecycle_and_validation(client: TestClient, session: Session, org_a: Organization, admin_token: str):
    from app.models.user import OperatorProfile
    from app.models.enums import VerificationStatus
    from app.models.route import Route, RouteStop, Stop
    from app.models.service import Service
    from app.models.vehicle import Vehicle

    # 1. Create Driver and Conductor in org_a
    driver = User(
        organization_id=org_a.id,
        name="Test Driver Rahul",
        email=f"driver_{uuid.uuid4().hex[:6]}@demo.com",
        role=UserRole.DRIVER,
        status="ACTIVE"
    )
    conductor = User(
        organization_id=org_a.id,
        name="Test Conductor Amit",
        email=f"cond_{uuid.uuid4().hex[:6]}@demo.com",
        role=UserRole.CONDUCTOR,
        status="ACTIVE"
    )
    session.add_all([driver, conductor])
    session.commit()

    drv_profile = OperatorProfile(
        user_id=driver.id,
        employee_code=f"DRV_{uuid.uuid4().hex[:4]}",
        operator_type="CITY_BUS",
        verification_status=VerificationStatus.VERIFIED
    )
    cnd_profile = OperatorProfile(
        user_id=conductor.id,
        employee_code=f"CND_{uuid.uuid4().hex[:4]}",
        operator_type="CITY_BUS",
        verification_status=VerificationStatus.VERIFIED
    )
    session.add_all([drv_profile, cnd_profile])

    # 2. Create Route, Service, and Vehicle
    route = Route(organization_id=org_a.id, route_code=f"R_{uuid.uuid4().hex[:6]}", route_name="Route 1", distance_km=10.0, geometry="SRID=4326;LINESTRING(1 1, 2 2)", status=RouteStatus.ACTIVE)
    session.add(route)
    session.commit()

    service = Service(organization_id=org_a.id, route_id=route.id, service_code=f"SVC_{uuid.uuid4().hex[:6]}", service_name="Express 1", status=ServiceStatus.ACTIVE)
    session.add(service)
    session.commit()

    vehicle = Vehicle(organization_id=org_a.id, vehicle_number=f"V_CREW_{uuid.uuid4().hex[:6]}", vehicle_type="BUS", status=VehicleStatus.ACTIVE)
    session.add(vehicle)
    session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Test: Role mismatch rejection (passing conductor as driver)
    mismatch_resp = client.post(
        f"/api/admin/vehicles/{vehicle.id}/crew",
        headers=headers,
        json={
            "service_id": str(service.id),
            "driver_id": str(conductor.id),
            "conductor_id": str(conductor.id)
        }
    )
    assert mismatch_resp.status_code == 400
    assert "DRIVER" in mismatch_resp.json()["detail"]

    # 4. Test: Cross-tenant rejection
    org_b = Organization(name=f"Org B {uuid.uuid4().hex[:6]}")
    session.add(org_b)
    session.commit()

    driver_b = User(
        organization_id=org_b.id,
        name="Foreign Driver",
        role=UserRole.DRIVER,
        status="ACTIVE"
    )
    session.add(driver_b)
    session.commit()

    cross_tenant_resp = client.post(
        f"/api/admin/vehicles/{vehicle.id}/crew",
        headers=headers,
        json={
            "service_id": str(service.id),
            "driver_id": str(driver_b.id)
        }
    )
    assert cross_tenant_resp.status_code == 400
    assert "Driver not found" in cross_tenant_resp.json()["detail"]

    # 5. Test: Successful crew assignment
    assign_resp = client.post(
        f"/api/admin/vehicles/{vehicle.id}/crew",
        headers=headers,
        json={
            "service_id": str(service.id),
            "driver_id": str(driver.id),
            "conductor_id": str(conductor.id)
        }
    )
    assert assign_resp.status_code == 200
    data = assign_resp.json()
    assert data["vehicle_id"] == str(vehicle.id)
    assert data["service_id"] == str(service.id)
    assert data["driver"]["id"] == str(driver.id)
    assert data["driver"]["employee_code"] == drv_profile.employee_code
    assert data["conductor"]["id"] == str(conductor.id)
    assert data["conductor"]["employee_code"] == cnd_profile.employee_code

    # 6. Test: GET /vehicles/{id}/crew returns current assignment
    get_crew_resp = client.get(
        f"/api/admin/vehicles/{vehicle.id}/crew?service_id={service.id}",
        headers=headers
    )
    assert get_crew_resp.status_code == 200
    assert get_crew_resp.json()["driver"]["id"] == str(driver.id)
    assert get_crew_resp.json()["conductor"]["id"] == str(conductor.id)

    # 7. Test: GET /vehicles?service_id=... enriches vehicle with crew
    list_resp = client.get(
        f"/api/admin/vehicles?service_id={service.id}",
        headers=headers
    )
    assert list_resp.status_code == 200
    veh_item = next(v for v in list_resp.json() if v["id"] == str(vehicle.id))
    assert veh_item["driver"]["id"] == str(driver.id)
    assert veh_item["conductor"]["id"] == str(conductor.id)

    # 8. Test: Unassign driver (pass driver_id=None)
    unassign_resp = client.post(
        f"/api/admin/vehicles/{vehicle.id}/crew",
        headers=headers,
        json={
            "service_id": str(service.id),
            "driver_id": None,
            "conductor_id": str(conductor.id)
        }
    )
    assert unassign_resp.status_code == 200
    unassign_data = unassign_resp.json()
    assert unassign_data["driver"] is None
    assert unassign_data["conductor"]["id"] == str(conductor.id)


def test_crew_reassignment_single_active_bus_invariant(client: TestClient, session: Session, org_a: Organization, admin_token: str):
    """
    Comprehensive test suite for Fleet Crew Assignment Fix — Single Active Bus Invariant.
    Enforces:
    1. Driver can be assigned to Bus 1.
    2. Driver cannot have two active buses.
    3. Driver A moved Bus 1 -> Bus 2 releases Bus 1.
    4. Bus 2's existing Driver B is released (unassigned / relieved).
    5. Driver A becomes active on Bus 2.
    6. Historical assignment rows remain preserved (AssignmentStatus.CANCELLED + unassigned_at).
    7. Same driver + same bus produces no duplicate active assignment.
    8. Conductor follows identical independent behavior.
    9. Conductor A moved Bus 1 -> Bus 2 releases Bus 1.
    10. Bus 2's existing Conductor B is released.
    11. Driver reassignment does not alter Conductor.
    12. Conductor reassignment does not alter Driver.
    13. Cross-organization personnel rejected.
    14. Wrong-role personnel rejected.
    15. Transaction rollback is verified on failure.
    16. Authorization remains intact.
    17. Concurrent assignment cannot create duplicate active Driver state.
    18. Concurrent assignment cannot create duplicate active Conductor state.
    """
    from concurrent.futures import ThreadPoolExecutor
    from app.models.enums import AssignmentStatus, TripStatus
    from app.models.trip import Trip, TripAssignment
    from app.models.user import OperatorProfile

    headers = {"Authorization": f"Bearer {admin_token}"}
    suffix = uuid.uuid4().hex[:6]

    # Setup Route and Service
    route = Route(
        organization_id=org_a.id,
        route_code=f"R_INV_{suffix}",
        route_name=f"Route Invariant {suffix}",
        status=RouteStatus.ACTIVE,
    )
    session.add(route)
    session.commit()

    service = Service(
        organization_id=org_a.id,
        route_id=route.id,
        service_code=f"S_INV_{suffix}",
        service_name=f"Service Invariant {suffix}",
        status=ServiceStatus.ACTIVE,
    )
    session.add(service)
    session.commit()

    # Setup Two Vehicles: Bus 1 and Bus 2
    bus1 = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"BUS1_{suffix}",
        registration_number=f"REG-BUS1-{suffix}",
        vehicle_type="STANDARD",
        status=VehicleStatus.ACTIVE,
    )
    bus2 = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"BUS2_{suffix}",
        registration_number=f"REG-BUS2-{suffix}",
        vehicle_type="STANDARD",
        status=VehicleStatus.ACTIVE,
    )
    session.add_all([bus1, bus2])
    session.commit()

    # Setup Personnel in Org A
    driver_a = User(
        organization_id=org_a.id,
        name=f"Driver A {suffix}",
        email=f"driver_a_{suffix}@demo.com",
        role=UserRole.DRIVER,
        status="ACTIVE",
    )
    driver_b = User(
        organization_id=org_a.id,
        name=f"Driver B {suffix}",
        email=f"driver_b_{suffix}@demo.com",
        role=UserRole.DRIVER,
        status="ACTIVE",
    )
    conductor_a = User(
        organization_id=org_a.id,
        name=f"Conductor A {suffix}",
        email=f"cond_a_{suffix}@demo.com",
        role=UserRole.CONDUCTOR,
        status="ACTIVE",
    )
    conductor_b = User(
        organization_id=org_a.id,
        name=f"Conductor B {suffix}",
        email=f"cond_b_{suffix}@demo.com",
        role=UserRole.CONDUCTOR,
        status="ACTIVE",
    )
    session.add_all([driver_a, driver_b, conductor_a, conductor_b])
    session.commit()

    session.add_all([
        OperatorProfile(user_id=driver_a.id, employee_code=f"DR_A_{suffix}", operator_type="DRIVER"),
        OperatorProfile(user_id=driver_b.id, employee_code=f"DR_B_{suffix}", operator_type="DRIVER"),
        OperatorProfile(user_id=conductor_a.id, employee_code=f"CD_A_{suffix}", operator_type="CONDUCTOR"),
        OperatorProfile(user_id=conductor_b.id, employee_code=f"CD_B_{suffix}", operator_type="CONDUCTOR"),
    ])
    session.commit()

    # Setup Foreign Org B and foreign personnel
    org_b = Organization(name=f"Foreign Org {suffix}")
    session.add(org_b)
    session.commit()

    foreign_driver = User(
        organization_id=org_b.id,
        name="Foreign Driver",
        email=f"foreign_drv_{suffix}@demo.com",
        role=UserRole.DRIVER,
        status="ACTIVE",
    )
    foreign_conductor = User(
        organization_id=org_b.id,
        name="Foreign Conductor",
        email=f"foreign_cnd_{suffix}@demo.com",
        role=UserRole.CONDUCTOR,
        status="ACTIVE",
    )
    session.add_all([foreign_driver, foreign_conductor])
    session.commit()

    # ─────────────────────────────────────────────────────────────
    # TEST 1 & 2: Driver A can be assigned to Bus 1; cannot have two active buses
    # ─────────────────────────────────────────────────────────────
    r1 = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_a.id), "conductor_id": None},
    )
    assert r1.status_code == 200
    assert r1.json()["driver"]["id"] == str(driver_a.id)

    # Verify active vehicle via Admin Users API
    users_resp = client.get("/api/admin/users?role=DRIVER", headers=headers)
    assert users_resp.status_code == 200
    driver_a_entry = next(u for u in users_resp.json() if u["id"] == str(driver_a.id))
    assert driver_a_entry["active_vehicle"] is not None
    assert driver_a_entry["active_vehicle"]["id"] == str(bus1.id)
    assert driver_a_entry["active_vehicle"]["vehicle_number"] == bus1.vehicle_number

    # ─────────────────────────────────────────────────────────────
    # Assign Driver B to Bus 2
    # ─────────────────────────────────────────────────────────────
    r2 = client.post(
        f"/api/admin/vehicles/{bus2.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_b.id), "conductor_id": None},
    )
    assert r2.status_code == 200
    assert r2.json()["driver"]["id"] == str(driver_b.id)

    # ─────────────────────────────────────────────────────────────
    # TEST 3, 4, 5: Driver A moved Bus 1 -> Bus 2 releases Bus 1;
    # Bus 2's existing Driver B is released; Driver A becomes active on Bus 2.
    # ─────────────────────────────────────────────────────────────
    r3 = client.post(
        f"/api/admin/vehicles/{bus2.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_a.id), "conductor_id": None},
    )
    assert r3.status_code == 200
    assert r3.json()["driver"]["id"] == str(driver_a.id)

    # Bus 1 must now have NO active driver
    bus1_crew = client.get(f"/api/admin/vehicles/{bus1.id}/crew?service_id={service.id}", headers=headers)
    assert bus1_crew.status_code == 200
    assert bus1_crew.json()["driver"] is None

    # Bus 2 must now have Driver A
    bus2_crew = client.get(f"/api/admin/vehicles/{bus2.id}/crew?service_id={service.id}", headers=headers)
    assert bus2_crew.status_code == 200
    assert bus2_crew.json()["driver"]["id"] == str(driver_a.id)

    # Driver B must now be relieved / unassigned
    users_resp = client.get("/api/admin/users?role=DRIVER", headers=headers)
    assert users_resp.status_code == 200
    driver_b_entry = next(u for u in users_resp.json() if u["id"] == str(driver_b.id))
    assert driver_b_entry["active_vehicle"] is None

    # Driver A must have Bus 2 as their sole active vehicle
    driver_a_entry = next(u for u in users_resp.json() if u["id"] == str(driver_a.id))
    assert driver_a_entry["active_vehicle"]["id"] == str(bus2.id)

    # ─────────────────────────────────────────────────────────────
    # TEST 6: Historical assignment rows remain preserved
    # ─────────────────────────────────────────────────────────────
    with Session(engine) as s:
        all_driver_a_assigns = s.execute(
            select(TripAssignment).where(TripAssignment.user_id == driver_a.id).order_by(TripAssignment.assigned_at)
        ).scalars().all()
        assert len(all_driver_a_assigns) >= 2  # Old on Bus 1, new on Bus 2
        old_assign = all_driver_a_assigns[0]
        assert old_assign.status == AssignmentStatus.CANCELLED
        assert old_assign.unassigned_at is not None

        driver_b_assigns = s.execute(
            select(TripAssignment).where(TripAssignment.user_id == driver_b.id)
        ).scalars().all()
        assert len(driver_b_assigns) >= 1
        displaced_assign = driver_b_assigns[0]
        assert displaced_assign.status == AssignmentStatus.CANCELLED
        assert displaced_assign.unassigned_at is not None

        # Verify exactly ONE active assignment for Driver A across all trips
        active_driver_a = s.execute(
            select(TripAssignment).where(
                TripAssignment.user_id == driver_a.id,
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
        ).scalars().all()
        assert len(active_driver_a) == 1

    # ─────────────────────────────────────────────────────────────
    # TEST 7: Same driver + same bus produces NO duplicate active assignment
    # ─────────────────────────────────────────────────────────────
    r_same = client.post(
        f"/api/admin/vehicles/{bus2.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_a.id), "conductor_id": None},
    )
    assert r_same.status_code == 200
    with Session(engine) as s:
        active_driver_a_re = s.execute(
            select(TripAssignment).where(
                TripAssignment.user_id == driver_a.id,
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
        ).scalars().all()
        assert len(active_driver_a_re) == 1

    # ─────────────────────────────────────────────────────────────
    # TEST 8, 9, 10: Conductor follows identical behavior independently
    # ─────────────────────────────────────────────────────────────
    # Assign Conductor A -> Bus 1
    c1 = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": None, "conductor_id": str(conductor_a.id)},
    )
    assert c1.status_code == 200
    assert c1.json()["conductor"]["id"] == str(conductor_a.id)

    # Assign Conductor B -> Bus 2
    c2 = client.post(
        f"/api/admin/vehicles/{bus2.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_a.id), "conductor_id": str(conductor_b.id)},
    )
    assert c2.status_code == 200
    assert c2.json()["conductor"]["id"] == str(conductor_b.id)

    # Move Conductor A -> Bus 2: releases Conductor A from Bus 1, displaces Conductor B from Bus 2
    c3 = client.post(
        f"/api/admin/vehicles/{bus2.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_a.id), "conductor_id": str(conductor_a.id)},
    )
    assert c3.status_code == 200
    assert c3.json()["conductor"]["id"] == str(conductor_a.id)

    # Bus 1 has no active conductor
    bus1_crew = client.get(f"/api/admin/vehicles/{bus1.id}/crew?service_id={service.id}", headers=headers).json()
    assert bus1_crew["conductor"] is None

    # Bus 2 has Conductor A
    bus2_crew = client.get(f"/api/admin/vehicles/{bus2.id}/crew?service_id={service.id}", headers=headers).json()
    assert bus2_crew["conductor"]["id"] == str(conductor_a.id)

    # Conductor B is unassigned
    users_resp = client.get("/api/admin/users?role=CONDUCTOR", headers=headers).json()
    conductor_b_entry = next(u for u in users_resp if u["id"] == str(conductor_b.id))
    assert conductor_b_entry["active_vehicle"] is None

    # Conductor historical preservation
    with Session(engine) as s:
        cond_b_assigns = s.execute(
            select(TripAssignment).where(TripAssignment.user_id == conductor_b.id)
        ).scalars().all()
        assert len(cond_b_assigns) >= 1
        assert cond_b_assigns[0].status == AssignmentStatus.CANCELLED
        assert cond_b_assigns[0].unassigned_at is not None

        active_cond_a = s.execute(
            select(TripAssignment).where(
                TripAssignment.user_id == conductor_a.id,
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
        ).scalars().all()
        assert len(active_cond_a) == 1

    # ─────────────────────────────────────────────────────────────
    # TEST 11 & 12: Driver reassignment does NOT alter Conductor, and vice-versa
    # ─────────────────────────────────────────────────────────────
    # Change driver on Bus 2 from Driver A to Driver B: Conductor A must remain active and unchanged!
    swap_drv = client.post(
        f"/api/admin/vehicles/{bus2.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_b.id), "conductor_id": str(conductor_a.id)},
    )
    assert swap_drv.status_code == 200
    assert swap_drv.json()["driver"]["id"] == str(driver_b.id)
    assert swap_drv.json()["conductor"]["id"] == str(conductor_a.id)

    # Change conductor on Bus 2 from Conductor A to Conductor B: Driver B must remain active and unchanged!
    swap_cnd = client.post(
        f"/api/admin/vehicles/{bus2.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(driver_b.id), "conductor_id": str(conductor_b.id)},
    )
    assert swap_cnd.status_code == 200
    assert swap_cnd.json()["driver"]["id"] == str(driver_b.id)
    assert swap_cnd.json()["conductor"]["id"] == str(conductor_b.id)

    # ─────────────────────────────────────────────────────────────
    # TEST 13: Cross-organization personnel rejected
    # ─────────────────────────────────────────────────────────────
    cross_drv = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(foreign_driver.id), "conductor_id": None},
    )
    assert cross_drv.status_code == 400
    assert "Driver not found" in cross_drv.json()["detail"]

    cross_cnd = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": None, "conductor_id": str(foreign_conductor.id)},
    )
    assert cross_cnd.status_code == 400
    assert "Conductor not found" in cross_cnd.json()["detail"]

    # ─────────────────────────────────────────────────────────────
    # TEST 14: Wrong-role personnel rejected
    # ─────────────────────────────────────────────────────────────
    # Pass conductor into driver_id
    wrong_role_drv = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": str(conductor_a.id), "conductor_id": None},
    )
    assert wrong_role_drv.status_code == 400
    assert "DRIVER" in wrong_role_drv.json()["detail"]

    # Pass driver into conductor_id
    wrong_role_cnd = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        headers=headers,
        json={"service_id": str(service.id), "driver_id": None, "conductor_id": str(driver_a.id)},
    )
    assert wrong_role_cnd.status_code == 400
    assert "CONDUCTOR" in wrong_role_cnd.json()["detail"]

    # ─────────────────────────────────────────────────────────────
    # TEST 15: Transaction rollback verified on failure
    # ─────────────────────────────────────────────────────────────
    # Bus 1 currently has no driver. Attempt assignment with valid driver_id but invalid service_id
    invalid_service_id = uuid.uuid4()
    fail_resp = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        headers=headers,
        json={"service_id": str(invalid_service_id), "driver_id": str(driver_a.id), "conductor_id": None},
    )
    assert fail_resp.status_code == 400
    # Verify driver_a was not partially touched or assigned to bus 1
    bus1_verify = client.get(f"/api/admin/vehicles/{bus1.id}/crew?service_id={service.id}", headers=headers).json()
    assert bus1_verify["driver"] is None

    # ─────────────────────────────────────────────────────────────
    # TEST 16: Authorization remains intact
    # ─────────────────────────────────────────────────────────────
    unauth_resp = client.post(
        f"/api/admin/vehicles/{bus1.id}/crew",
        json={"service_id": str(service.id), "driver_id": str(driver_a.id), "conductor_id": None},
    )
    assert unauth_resp.status_code == 401

    # ─────────────────────────────────────────────────────────────
    # TEST 17 & 18: Concurrency protection — concurrent assignment cannot create duplicate active state
    # ─────────────────────────────────────────────────────────────
    # Simultaneously attempt assigning Driver A to Bus 1 and Bus 2 in parallel threads
    def assign_worker(target_bus_id: uuid.UUID):
        c = TestClient(app)
        return c.post(
            f"/api/admin/vehicles/{target_bus_id}/crew",
            headers=headers,
            json={"service_id": str(service.id), "driver_id": str(driver_a.id), "conductor_id": None},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(assign_worker, bus1.id)
        f2 = executor.submit(assign_worker, bus2.id)
        r_f1 = f1.result()
        r_f2 = f2.result()

    # Both requests must complete (either 200 or clean serialized resolution)
    assert r_f1.status_code == 200
    assert r_f2.status_code == 200

    # The authoritative database state MUST have at most ONE active assignment for Driver A
    with Session(engine) as s:
        final_active_drv = s.execute(
            select(TripAssignment).where(
                TripAssignment.user_id == driver_a.id,
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
        ).scalars().all()
        assert len(final_active_drv) == 1, f"Expected 1 active driver assignment, found {len(final_active_drv)}"

        # Same concurrent test for Conductor A
        def assign_cond_worker(target_bus_id: uuid.UUID):
            c = TestClient(app)
            return c.post(
                f"/api/admin/vehicles/{target_bus_id}/crew",
                headers=headers,
                json={"service_id": str(service.id), "driver_id": None, "conductor_id": str(conductor_a.id)},
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            fc1 = executor.submit(assign_cond_worker, bus1.id)
            fc2 = executor.submit(assign_cond_worker, bus2.id)
            rfc1 = fc1.result()
            rfc2 = fc2.result()

        assert rfc1.status_code == 200
        assert rfc2.status_code == 200

        final_active_cnd = s.execute(
            select(TripAssignment).where(
                TripAssignment.user_id == conductor_a.id,
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
        ).scalars().all()
        assert len(final_active_cnd) == 1, f"Expected 1 active conductor assignment, found {len(final_active_cnd)}"


