import uuid
from datetime import datetime, timezone, timedelta, date, time
import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, Direction, VehicleStatus, ServiceStatus, RouteStatus
from app.models.vehicle import Vehicle
from app.models.service import Service, DepotSchedule
from app.models.service_vehicle import ServiceVehicle
from app.models.route import Route
from app.db.database import engine
from app.db.seed import seed_dev_data
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def ensure_seed():
    with Session(engine) as session:
        seed_dev_data(session)

@pytest.fixture
def session():
    with Session(engine) as s:
        yield s

@pytest.fixture
def org_a(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org A FleetSched {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_sched_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Sched A",
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
    org = Organization(name=f"Org B FleetSched {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_b_token(client: TestClient, session: Session, org_b: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_sched_b_{suffix}@demo.com"
    admin = User(
        organization_id=org_b.id,
        name="Admin Sched B",
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
def fleet_setup(session: Session, org_a: Organization):
    suffix = uuid.uuid4().hex[:8]
    rt = Route(
        organization_id=org_a.id,
        route_code=f"RT-{suffix}",
        route_name="Route Sched Test",
        status=RouteStatus.ACTIVE,
    )
    session.add(rt)
    session.flush()

    svc = Service(
        organization_id=org_a.id,
        route_id=rt.id,
        service_code=f"SVC-{suffix}",
        service_name="Service Sched Test",
        status=ServiceStatus.ACTIVE,
    )
    session.add(svc)
    session.flush()

    v1 = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"BUS-{suffix}-1",
        vehicle_type="Standard",
        status=VehicleStatus.ACTIVE,
    )
    v2 = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"BUS-{suffix}-2",
        vehicle_type="Standard",
        status=VehicleStatus.ACTIVE,
    )
    session.add_all([v1, v2])
    session.flush()

    # Link both vehicles to service via initial DepotSchedule
    ds1 = DepotSchedule(
        vehicle_id=v1.id,
        service_id=svc.id,
        direction=Direction.A_TO_B,
        operating_date=date.today(),
        planned_departure=datetime.now(timezone.utc),
        status="PLANNED",
        source="SERVICE_FLEET_ASSIGNMENT",
    )
    ds2 = DepotSchedule(
        vehicle_id=v2.id,
        service_id=svc.id,
        direction=Direction.A_TO_B,
        operating_date=date.today(),
        planned_departure=datetime.now(timezone.utc),
        status="PLANNED",
        source="SERVICE_FLEET_ASSIGNMENT",
    )
    session.add_all([ds1, ds2])
    session.commit()

    return {"service": svc, "vehicle1": v1, "vehicle2": v2, "ds1": ds1, "ds2": ds2}


def test_get_fleet_schedules_ordered_chronologically(client: TestClient, admin_token: str, fleet_setup: dict, session: Session):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]
    v2 = fleet_setup["vehicle2"]

    # Clear initial depot schedules for clean test
    session.query(DepotSchedule).filter(DepotSchedule.service_id == svc.id).delete()
    
    # Add departures in non-chronological order: 09:30, 06:30, 08:00, 07:15
    for dep_time, veh in [("09:30:00", v1), ("06:30:00", v1), ("08:00:00", v2), ("07:15:00", v2)]:
        h, m, s = [int(x) for x in dep_time.split(":")]
        session.add(DepotSchedule(
            vehicle_id=veh.id,
            service_id=svc.id,
            direction=Direction.A_TO_B,
            operating_date=date.today(),
            planned_departure=datetime.combine(date.today(), time(h, m, s)),
            status="PLANNED",
            source="RECURRING_DAILY",
        ))
    session.commit()

    res = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 4
    
    # Verify chronological ordering
    times = [item["departure_time"] for item in data]
    assert times == ["06:30", "07:15", "08:00", "09:30"]
    assert data[0]["formatted_departure_time"] == "06:30 AM"
    assert data[0]["every_day"] is True
    assert data[0]["vehicle_number"] == v1.vehicle_number


def test_create_fleet_schedule_recurring_daily(client: TestClient, admin_token: str, fleet_setup: dict):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]

    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(v1.id),
        "departure_time": "06:30",
        "every_day": True,
    }
    res = client.post(
        "/api/admin/fleet-schedules",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["service_id"] == str(svc.id)
    assert data["vehicle_id"] == str(v1.id)
    assert data["departure_time"] == "06:30"
    assert data["formatted_departure_time"] == "06:30 AM"
    assert data["every_day"] is True
    assert data["source"] == "RECURRING_DAILY"


def test_create_fleet_schedule_duplicate_rejection(client: TestClient, admin_token: str, fleet_setup: dict):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]

    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(v1.id),
        "departure_time": "07:00",
        "every_day": True,
    }
    res1 = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res1.status_code == 201

    # Re-submitting same service + vehicle + departure time must fail
    res2 = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_create_fleet_schedule_invalid_vehicle_for_service(client: TestClient, admin_token: str, fleet_setup: dict, session: Session, org_a: Organization):
    svc = fleet_setup["service"]
    
    # Create unassigned vehicle belonging to org_a
    unassigned_veh = Vehicle(
        organization_id=org_a.id,
        vehicle_number="UNASSIGNED-BUS-99",
        vehicle_type="Standard",
        status=VehicleStatus.ACTIVE,
    )
    session.add(unassigned_veh)
    session.commit()

    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(unassigned_veh.id),
        "departure_time": "11:00",
        "every_day": True,
    }
    res = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert "not associated with this service" in res.json()["detail"]


def test_create_fleet_schedule_cross_tenant_isolation(client: TestClient, admin_b_token: str, fleet_setup: dict):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]

    # Admin B tries to create schedule for Org A service
    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(v1.id),
        "departure_time": "12:00",
        "every_day": True,
    }
    res = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_b_token}"})
    assert res.status_code == 400
    assert "unauthorized" in res.json()["detail"] or "not found" in res.json()["detail"]


def test_update_fleet_schedule(client: TestClient, admin_token: str, fleet_setup: dict):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]
    v2 = fleet_setup["vehicle2"]

    # Create schedule
    create_res = client.post(
        "/api/admin/fleet-schedules",
        json={"service_id": str(svc.id), "vehicle_id": str(v1.id), "departure_time": "08:15"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert create_res.status_code == 201
    sched_id = create_res.json()["id"]

    # Update departure time to 08:45 and vehicle to v2
    update_res = client.put(
        f"/api/admin/fleet-schedules/{sched_id}",
        json={"departure_time": "08:45", "vehicle_id": str(v2.id)},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["departure_time"] == "08:45"
    assert data["formatted_departure_time"] == "08:45 AM"
    assert data["vehicle_id"] == str(v2.id)
    assert data["vehicle_number"] == v2.vehicle_number


def test_delete_fleet_schedule(client: TestClient, admin_token: str, fleet_setup: dict):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]

    create_res = client.post(
        "/api/admin/fleet-schedules",
        json={"service_id": str(svc.id), "vehicle_id": str(v1.id), "departure_time": "14:00"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert create_res.status_code == 201
    sched_id = create_res.json()["id"]

    # Delete (soft cancel)
    del_res = client.delete(
        f"/api/admin/fleet-schedules/{sched_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert del_res.status_code == 204

    # Verify not returned in active fleet-schedules
    list_res = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert list_res.status_code == 200
    ids = [item["id"] for item in list_res.json()]
    assert sched_id not in ids


def test_recurrence_persistence_across_dates(client: TestClient, admin_token: str, fleet_setup: dict, session: Session):
    """
    Verifies that a recurring timetable entry created with an effective date in the past
    continues to be active and returned as part of the service's recurring timetable.
    """
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]

    # Add schedule effective from 10 days ago
    past_date = date.today() - timedelta(days=10)
    past_sched = DepotSchedule(
        vehicle_id=v1.id,
        service_id=svc.id,
        direction=Direction.A_TO_B,
        operating_date=past_date,
        planned_departure=datetime.combine(past_date, time(6, 45)),
        status="PLANNED",
        source="RECURRING_DAILY",
    )
    session.add(past_sched)
    session.commit()

    # Query fleet schedules - must include the 06:45 departure regardless of date
    res = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    times = [item["departure_time"] for item in res.json()]
    assert "06:45" in times


def test_direction_scoped_filtering(client: TestClient, admin_token: str, fleet_setup: dict):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]
    v2 = fleet_setup["vehicle2"]

    # Create A_TO_B departure
    res_a = client.post(
        "/api/admin/fleet-schedules",
        json={
            "service_id": str(svc.id),
            "vehicle_id": str(v1.id),
            "direction": "A_TO_B",
            "departure_time": "06:30",
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_a.status_code == 201

    # Create B_TO_A departure
    res_b = client.post(
        "/api/admin/fleet-schedules",
        json={
            "service_id": str(svc.id),
            "vehicle_id": str(v2.id),
            "direction": "B_TO_A",
            "departure_time": "07:15",
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_b.status_code == 201

    # Query A_TO_B only
    res_query_a = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}&direction=A_TO_B",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_query_a.status_code == 200
    items_a = res_query_a.json()
    assert all(item["direction"] == "A_TO_B" for item in items_a)
    times_a = [item["departure_time"] for item in items_a]
    assert "06:30" in times_a
    assert "07:15" not in times_a

    # Query B_TO_A only
    res_query_b = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}&direction=B_TO_A",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_query_b.status_code == 200
    items_b = res_query_b.json()
    assert all(item["direction"] == "B_TO_A" for item in items_b)
    times_b = [item["departure_time"] for item in items_b]
    assert "07:15" in times_b
    assert "06:30" not in times_b


def test_same_vehicle_and_time_allowed_in_opposite_directions(client: TestClient, admin_token: str, fleet_setup: dict):
    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]

    # Schedule at 06:30 for A_TO_B
    res1 = client.post(
        "/api/admin/fleet-schedules",
        json={
            "service_id": str(svc.id),
            "vehicle_id": str(v1.id),
            "direction": "A_TO_B",
            "departure_time": "06:30",
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res1.status_code == 201

    # Schedule at 06:30 for B_TO_A (opposite direction) MUST SUCCEED
    res2 = client.post(
        "/api/admin/fleet-schedules",
        json={
            "service_id": str(svc.id),
            "vehicle_id": str(v1.id),
            "direction": "B_TO_A",
            "departure_time": "06:30",
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res2.status_code == 201

    # Attempting duplicate at 06:30 for A_TO_B again MUST FAIL
    res3 = client.post(
        "/api/admin/fleet-schedules",
        json={
            "service_id": str(svc.id),
            "vehicle_id": str(v1.id),
            "direction": "A_TO_B",
            "departure_time": "06:30",
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res3.status_code == 400
    assert "already exists" in res3.json()["detail"]


def test_crew_summary_hydration_on_fleet_schedule(client: TestClient, admin_token: str, fleet_setup: dict, session: Session, org_a: Organization):
    from app.models.trip import Trip, TripAssignment
    from app.models.user import OperatorProfile
    from app.models.enums import TripStatus, AssignmentStatus, Direction

    svc = fleet_setup["service"]
    v1 = fleet_setup["vehicle1"]
    suffix = uuid.uuid4().hex[:6]

    # Create Driver User + Profile
    driver_user = User(
        organization_id=org_a.id,
        name=f"Driver Test {suffix}",
        email=f"driver_{suffix}@demo.com",
        password_hash="hash",
        role=UserRole.DRIVER,
    )
    conductor_user = User(
        organization_id=org_a.id,
        name=f"Conductor Test {suffix}",
        email=f"conductor_{suffix}@demo.com",
        password_hash="hash",
        role=UserRole.CONDUCTOR,
    )
    session.add_all([driver_user, conductor_user])
    session.flush()

    d_profile = OperatorProfile(user_id=driver_user.id, employee_code=f"DR-{suffix}", operator_type="DRIVER")
    c_profile = OperatorProfile(user_id=conductor_user.id, employee_code=f"CD-{suffix}", operator_type="CONDUCTOR")
    session.add_all([d_profile, c_profile])
    session.flush()

    # Create active trip for vehicle1 and service
    trip = Trip(
        organization_id=org_a.id,
        service_id=svc.id,
        vehicle_id=v1.id,
        route_id=svc.route_id,
        direction=Direction.A_TO_B,
        operating_date=date.today(),
        planned_start_at=datetime.now(timezone.utc),
        status=TripStatus.ACTIVE,
    )
    session.add(trip)
    session.flush()

    assign1 = TripAssignment(
        trip_id=trip.id,
        user_id=driver_user.id,
        role="DRIVER",
        status=AssignmentStatus.ACTIVE,
        assigned_at=datetime.now(timezone.utc),
    )
    assign2 = TripAssignment(
        trip_id=trip.id,
        user_id=conductor_user.id,
        role="CONDUCTOR",
        status=AssignmentStatus.ACTIVE,
        assigned_at=datetime.now(timezone.utc),
    )
    session.add_all([assign1, assign2])
    session.commit()

    # Create schedule for v1
    res = client.post(
        "/api/admin/fleet-schedules",
        json={
            "service_id": str(svc.id),
            "vehicle_id": str(v1.id),
            "direction": "A_TO_B",
            "departure_time": "10:15",
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["driver"] is not None
    assert data["driver"]["name"] == driver_user.name
    assert data["driver"]["employee_code"] == f"DR-{suffix}"
    assert data["conductor"] is not None
    assert data["conductor"]["name"] == conductor_user.name
    assert data["conductor"]["employee_code"] == f"CD-{suffix}"
    assert data["vehicle_status"] == "ACTIVE"


def test_create_fleet_schedule_active_service_vehicle_allowed(client: TestClient, admin_token: str, fleet_setup: dict, session: Session, org_a: Organization):
    svc = fleet_setup["service"]
    suffix = uuid.uuid4().hex[:8]

    # Create vehicle with NO existing DepotSchedule and NO Trip
    veh_active = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"ACTIVE-BUS-{suffix}",
        vehicle_type="Standard",
        status=VehicleStatus.ACTIVE,
    )
    session.add(veh_active)
    session.flush()

    # Explicit ACTIVE ServiceVehicle membership
    sv = ServiceVehicle(
        organization_id=org_a.id,
        service_id=svc.id,
        vehicle_id=veh_active.id,
        status="ACTIVE",
        assigned_at=datetime.now(timezone.utc),
    )
    session.add(sv)
    session.commit()

    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(veh_active.id),
        "direction": "A_TO_B",
        "departure_time": "08:45",
        "every_day": True,
    }
    res = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    data = res.json()
    assert data["vehicle_id"] == str(veh_active.id)
    assert data["departure_time"] == "08:45"
    assert data["vehicle_number"] == f"ACTIVE-BUS-{suffix}"


def test_create_fleet_schedule_inactive_service_vehicle_rejected(client: TestClient, admin_token: str, fleet_setup: dict, session: Session, org_a: Organization):
    svc = fleet_setup["service"]
    suffix = uuid.uuid4().hex[:8]

    # Create vehicle with old cancelled DepotSchedule
    veh_inactive = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"INACTIVE-BUS-{suffix}",
        vehicle_type="Standard",
        status=VehicleStatus.ACTIVE,
    )
    session.add(veh_inactive)
    session.flush()

    old_ds = DepotSchedule(
        vehicle_id=veh_inactive.id,
        service_id=svc.id,
        direction=Direction.A_TO_B,
        operating_date=date.today(),
        planned_departure=datetime.now(timezone.utc),
        status="CANCELLED",
        source="SERVICE_FLEET_ASSIGNMENT",
    )
    session.add(old_ds)

    # Explicit INACTIVE ServiceVehicle membership
    sv = ServiceVehicle(
        organization_id=org_a.id,
        service_id=svc.id,
        vehicle_id=veh_inactive.id,
        status="INACTIVE",
        assigned_at=datetime.now(timezone.utc),
        unassigned_at=datetime.now(timezone.utc),
    )
    session.add(sv)
    session.commit()

    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(veh_inactive.id),
        "direction": "A_TO_B",
        "departure_time": "09:15",
        "every_day": True,
    }
    res = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert "not associated with this service" in res.json()["detail"]


def test_create_fleet_schedule_legacy_fallback_preserved(client: TestClient, admin_token: str, fleet_setup: dict, session: Session, org_a: Organization):
    svc = fleet_setup["service"]
    suffix = uuid.uuid4().hex[:8]

    # Create vehicle with legacy DepotSchedule but NO ServiceVehicle row
    veh_legacy = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"LEGACY-BUS-{suffix}",
        vehicle_type="Standard",
        status=VehicleStatus.ACTIVE,
    )
    session.add(veh_legacy)
    session.flush()

    legacy_ds = DepotSchedule(
        vehicle_id=veh_legacy.id,
        service_id=svc.id,
        direction=Direction.A_TO_B,
        operating_date=date.today(),
        planned_departure=datetime.now(timezone.utc),
        status="PLANNED",
        source="SERVICE_FLEET_ASSIGNMENT",
    )
    session.add(legacy_ds)
    session.commit()

    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(veh_legacy.id),
        "direction": "A_TO_B",
        "departure_time": "14:30",
        "every_day": True,
    }
    res = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    data = res.json()
    assert data["vehicle_id"] == str(veh_legacy.id)
    assert data["departure_time"] == "14:30"


def test_create_fleet_schedule_other_service_vehicle_rejected(client: TestClient, admin_token: str, fleet_setup: dict, session: Session, org_a: Organization):
    svc = fleet_setup["service"]
    suffix = uuid.uuid4().hex[:8]

    # Create a second service
    rt2 = Route(
        organization_id=org_a.id,
        route_code=f"RT2-{suffix}",
        route_name="Route 2 Sched Test",
        status=RouteStatus.ACTIVE,
    )
    session.add(rt2)
    session.flush()

    svc2 = Service(
        organization_id=org_a.id,
        route_id=rt2.id,
        service_code=f"SVC2-{suffix}",
        service_name="Service 2 Sched Test",
        status=ServiceStatus.ACTIVE,
    )
    session.add(svc2)
    session.flush()

    # Create vehicle associated with svc2 only
    veh_other = Vehicle(
        organization_id=org_a.id,
        vehicle_number=f"OTHER-BUS-{suffix}",
        vehicle_type="Standard",
        status=VehicleStatus.ACTIVE,
    )
    session.add(veh_other)
    session.flush()

    sv2 = ServiceVehicle(
        organization_id=org_a.id,
        service_id=svc2.id,
        vehicle_id=veh_other.id,
        status="ACTIVE",
        assigned_at=datetime.now(timezone.utc),
    )
    session.add(sv2)
    session.commit()

    # Attempt to create departure schedule on svc (first service) using veh_other
    payload = {
        "service_id": str(svc.id),
        "vehicle_id": str(veh_other.id),
        "direction": "A_TO_B",
        "departure_time": "15:45",
        "every_day": True,
    }
    res = client.post("/api/admin/fleet-schedules", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert "not associated with this service" in res.json()["detail"]



