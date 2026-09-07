import uuid
from datetime import datetime, timezone, time, date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, Direction, ServiceStatus, VehicleStatus
from app.models.service import Service, ServiceSchedule, DepotSchedule
from app.models.route import Route, Stop, RouteStop
from app.models.vehicle import Vehicle
from app.models.fare import FareConfiguration, FareSlab
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
def org_svc(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org Svc Detail {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def admin_user(session: Session, org_svc: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_detail_{suffix}@demo.com"
    admin = User(
        organization_id=org_svc.id,
        name="Admin Svc Detail",
        email=email,
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def admin_token(client: TestClient, admin_user: User):
    response = client.post(
        "/api/admin/login",
        json={"email": admin_user.email, "password": "password"},
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def full_service_setup(session: Session, org_svc: Organization, admin_user: User):
    suffix = uuid.uuid4().hex[:8]

    # 1. Stops
    stop1 = Stop(
        organization_id=org_svc.id,
        stop_code=f"STP1_{suffix}",
        name="Origin Stop",
        latitude=22.57,
        longitude=88.36,
        location="SRID=4326;POINT(88.36 22.57)",
    )
    stop2 = Stop(
        organization_id=org_svc.id,
        stop_code=f"STP2_{suffix}",
        name="Destination Stop",
        latitude=22.60,
        longitude=88.40,
        location="SRID=4326;POINT(88.40 22.60)",
    )
    session.add_all([stop1, stop2])
    session.commit()

    # 2. Route
    route = Route(
        organization_id=org_svc.id,
        route_code=f"RT_{suffix}",
        route_name="Origin to Destination",
        distance_km=14.5,
        geometry="SRID=4326;LINESTRING(88.36 22.57, 88.40 22.60)",
    )
    session.add(route)
    session.commit()
    session.refresh(route)

    # 3. RouteStops
    rs1 = RouteStop(
        route_id=route.id,
        stop_id=stop1.id,
        sequence_number=1,
        distance_from_start=0.0,
    )
    rs2 = RouteStop(
        route_id=route.id,
        stop_id=stop2.id,
        sequence_number=2,
        distance_from_start=14.5,
    )
    session.add_all([rs1, rs2])
    session.commit()

    # 4. Fare Configuration with Slabs
    fare = FareConfiguration(
        organization_id=org_svc.id,
        name=f"Fare {suffix}",
        currency="INR",
        effective_from=date(2026, 9, 1),
        is_active=True,
        created_by=admin_user.id,
    )
    session.add(fare)
    session.commit()
    session.refresh(fare)

    slab1 = FareSlab(
        fare_configuration_id=fare.id,
        min_distance_km=0.0,
        max_distance_km=5.0,
        fare_amount=10.0,
    )
    slab2 = FareSlab(
        fare_configuration_id=fare.id,
        min_distance_km=5.0,
        max_distance_km=None,
        fare_amount=20.0,
    )
    session.add_all([slab1, slab2])
    session.commit()

    # 5. Service
    svc = Service(
        organization_id=org_svc.id,
        route_id=route.id,
        service_code=f"SVC_{suffix}",
        service_name="Express Line",
        status=ServiceStatus.ACTIVE,
        fare_configuration_id=fare.id,
    )
    session.add(svc)
    session.commit()
    session.refresh(svc)

    # 6. Vehicle
    vehicle = Vehicle(
        organization_id=org_svc.id,
        vehicle_number=f"WB-{suffix[:4].upper()}",
        registration_number=f"WB-01-{suffix[:4].upper()}",
        vehicle_type="STANDARD_BUS",
        status=VehicleStatus.ACTIVE,
    )
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)

    return {
        "service": svc,
        "route": route,
        "fare": fare,
        "stops": [stop1, stop2],
        "vehicle": vehicle,
    }


def test_service_detail_loads_with_enriched_route_and_fare(
    client: TestClient, admin_token: str, full_service_setup: dict
):
    svc = full_service_setup["service"]
    route = full_service_setup["route"]
    fare = full_service_setup["fare"]

    resp = client.get(
        f"/api/admin/services/{svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Service Identity
    assert data["id"] == str(svc.id)
    assert data["service_code"] == svc.service_code
    assert data["service_name"] == "Express Line"
    assert data["status"] == "ACTIVE"

    # Enriched Route relationship
    assert data["route_id"] == str(route.id)
    assert data["route_code"] == route.route_code
    assert data["route_name"] == route.route_name

    # Enriched Fare relationship
    assert data["fare_configuration_id"] == str(fare.id)
    assert data["fare_configuration_name"] == fare.name
    assert data["fare_is_active"] is True
    assert data["fare_slabs_count"] == 2
    assert data["fare_currency"] == "INR"


def test_service_schedules_timing_and_frequency_derivation(
    client: TestClient, admin_token: str, full_service_setup: dict, session: Session
):
    svc = full_service_setup["service"]

    # Add a passenger ServiceSchedule
    sched = ServiceSchedule(
        service_id=svc.id,
        direction=Direction.A_TO_B,
        start_time=time(6, 0, 0),
        end_time=time(22, 30, 0),
        typical_interval_minutes=15,
        days_of_week=[1, 2, 3, 4, 5],
        effective_from=datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc),
        status="ACTIVE",
    )
    session.add(sched)
    session.commit()

    resp = client.get(
        f"/api/admin/services/{svc.id}/schedules",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    schedules = resp.json()
    assert len(schedules) == 1
    s = schedules[0]

    # Authoritative fields: start_time, end_time, typical_interval_minutes
    assert s["start_time"] == "06:00:00"
    assert s["end_time"] == "22:30:00"
    assert s["typical_interval_minutes"] == 15
    assert s["days_of_week"] == [1, 2, 3, 4, 5]


def test_fleet_schedules_recurring_timetable_derivation(
    client: TestClient, admin_token: str, full_service_setup: dict, session: Session
):
    svc = full_service_setup["service"]
    vehicle = full_service_setup["vehicle"]

    # Create 2 DepotSchedule recurring departures
    ds1 = DepotSchedule(
        service_id=svc.id,
        vehicle_id=vehicle.id,
        direction=Direction.A_TO_B,
        operating_date=date(2026, 9, 4),
        planned_departure=datetime(2026, 9, 4, 6, 30, 0, tzinfo=timezone.utc),
        status="PLANNED",
    )
    ds2 = DepotSchedule(
        service_id=svc.id,
        vehicle_id=vehicle.id,
        direction=Direction.A_TO_B,
        operating_date=date(2026, 9, 4),
        planned_departure=datetime(2026, 9, 4, 17, 45, 0, tzinfo=timezone.utc),
        status="PLANNED",
    )
    session.add_all([ds1, ds2])
    session.commit()

    resp = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    departures = resp.json()
    assert len(departures) == 2

    # Earliest departure = 06:30
    assert departures[0]["departure_time"] == "06:30"
    # Latest departure = 17:45
    assert departures[1]["departure_time"] == "17:45"


def test_empty_schedule_and_fleet_graceful_handling(
    client: TestClient, admin_token: str, full_service_setup: dict
):
    svc = full_service_setup["service"]

    # When no schedules or fleet assigned
    resp_sched = client.get(
        f"/api/admin/services/{svc.id}/schedules",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_sched.status_code == 200
    assert resp_sched.json() == []

    resp_fleet = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_fleet.status_code == 200
    assert resp_fleet.json() == []


def test_service_detail_cross_tenant_isolation(
    client: TestClient, admin_token: str, session: Session
):
    # Create an entirely different organization and service
    other_org = Organization(name=f"Other Org Svc {uuid.uuid4().hex[:8]}")
    session.add(other_org)
    session.commit()
    session.refresh(other_org)

    other_route = Route(
        organization_id=other_org.id,
        route_code=f"RT_OTHER_{uuid.uuid4().hex[:6]}",
        route_name="Other Route",
        distance_km=10.0,
    )
    session.add(other_route)
    session.commit()

    other_svc = Service(
        organization_id=other_org.id,
        route_id=other_route.id,
        service_code=f"SVC_OTHER_{uuid.uuid4().hex[:6]}",
        service_name="Other Service",
        status=ServiceStatus.ACTIVE,
    )
    session.add(other_svc)
    session.commit()
    session.refresh(other_svc)

    # Admin from org_svc tries to read other_svc -> 404
    resp = client.get(
        f"/api/admin/services/{other_svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_service_update_core_properties_and_route(
    client: TestClient, admin_token: str, full_service_setup: dict, org_svc: Organization, session: Session
):
    svc = full_service_setup["service"]
    current_route = full_service_setup["route"]

    # Create an alternative valid route in same org
    new_route = Route(
        organization_id=org_svc.id,
        route_code=f"RT_NEW_{uuid.uuid4().hex[:6]}",
        route_name="Alternative Route",
        distance_km=18.0,
    )
    session.add(new_route)
    session.commit()
    session.refresh(new_route)

    new_code = f"SVC_UPD_{uuid.uuid4().hex[:6]}"
    resp = client.put(
        f"/api/admin/services/{svc.id}",
        json={
            "service_code": new_code,
            "service_name": "Updated Express Line",
            "status": "INACTIVE",
            "route_id": str(new_route.id),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["service_code"] == new_code
    assert data["service_name"] == "Updated Express Line"
    assert data["status"] == "INACTIVE"
    assert data["route_id"] == str(new_route.id)
    assert data["route_code"] == new_route.route_code


def test_service_update_duplicate_code_rejection(
    client: TestClient, admin_token: str, full_service_setup: dict, org_svc: Organization, session: Session
):
    svc1 = full_service_setup["service"]
    route = full_service_setup["route"]

    # Create a second service in same org
    svc2_code = f"SVC_DUP_{uuid.uuid4().hex[:6]}"
    svc2 = Service(
        organization_id=org_svc.id,
        route_id=route.id,
        service_code=svc2_code,
        service_name="Second Service",
        status=ServiceStatus.ACTIVE,
    )
    session.add(svc2)
    session.commit()

    # Attempt to update svc1 to have svc2's code
    resp = client.put(
        f"/api/admin/services/{svc1.id}",
        json={"service_code": svc2_code},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


def test_service_update_cross_tenant_route_rejection(
    client: TestClient, admin_token: str, full_service_setup: dict, session: Session
):
    svc = full_service_setup["service"]

    # Create a foreign org and route
    foreign_org = Organization(name=f"Foreign Org {uuid.uuid4().hex[:6]}")
    session.add(foreign_org)
    session.commit()
    foreign_route = Route(
        organization_id=foreign_org.id,
        route_code=f"RT_FOR_{uuid.uuid4().hex[:6]}",
        route_name="Foreign Route",
        distance_km=10.0,
    )
    session.add(foreign_route)
    session.commit()

    # Attempt to associate svc with foreign route -> 400
    resp = client.put(
        f"/api/admin/services/{svc.id}",
        json={"route_id": str(foreign_route.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "does not belong to your organization" in resp.json()["detail"]


def test_service_update_first_and_last_bus_not_editable_fields(
    client: TestClient, admin_token: str, full_service_setup: dict
):
    svc = full_service_setup["service"]

    # First Bus and Last Bus are NOT accepted as Service database fields
    resp = client.put(
        f"/api/admin/services/{svc.id}",
        json={
            "service_name": "Verified Name",
            "first_bus": "05:30",
            "last_bus": "23:30",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["service_name"] == "Verified Name"
    # Verify Service schema does not expose or persist first_bus / last_bus
    assert "first_bus" not in data
    assert "last_bus" not in data


def test_service_schedule_frequency_and_days_update(
    client: TestClient, admin_token: str, full_service_setup: dict, session: Session
):
    svc = full_service_setup["service"]

    # Create active passenger ServiceSchedule
    sched = ServiceSchedule(
        service_id=svc.id,
        direction=Direction.A_TO_B,
        start_time=time(6, 0, 0),
        end_time=time(22, 0, 0),
        typical_interval_minutes=20,
        days_of_week=[1, 2, 3, 4, 5],
        effective_from=datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc),
        status="ACTIVE",
    )
    session.add(sched)
    session.commit()
    session.refresh(sched)

    # Update frequency to 12 minutes and operating days to all 7 days
    resp = client.put(
        f"/api/admin/services/{svc.id}/schedules/{sched.id}",
        json={
            "typical_interval_minutes": 12,
            "days_of_week": [1, 2, 3, 4, 5, 6, 7],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["typical_interval_minutes"] == 12
    assert data["days_of_week"] == [1, 2, 3, 4, 5, 6, 7]


def test_service_schedule_frequency_validation_rejects_non_positive(
    client: TestClient, admin_token: str, full_service_setup: dict, session: Session
):
    svc = full_service_setup["service"]

    sched = ServiceSchedule(
        service_id=svc.id,
        direction=Direction.A_TO_B,
        start_time=time(6, 0, 0),
        end_time=time(22, 0, 0),
        typical_interval_minutes=15,
        days_of_week=[1, 2, 3, 4, 5],
        effective_from=datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc),
        status="ACTIVE",
    )
    session.add(sched)
    session.commit()

    # Attempt typical_interval_minutes = 0 -> 422 Unprocessable Entity
    resp_zero = client.put(
        f"/api/admin/services/{svc.id}/schedules/{sched.id}",
        json={"typical_interval_minutes": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_zero.status_code == 422

    # Attempt typical_interval_minutes = -5 -> 422 Unprocessable Entity
    resp_neg = client.put(
        f"/api/admin/services/{svc.id}/schedules/{sched.id}",
        json={"typical_interval_minutes": -5},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_neg.status_code == 422


def test_fleet_schedule_derives_first_and_last_bus_without_fabricating_frequency(
    client: TestClient, admin_token: str, full_service_setup: dict, session: Session
):
    svc = full_service_setup["service"]
    vehicle = full_service_setup["vehicle"]

    # Create 4 departures: 06:30 AM, 09:00 AM, 12:00 PM, 03:55 PM (15:55)
    times = [
        datetime(2026, 9, 4, 6, 30, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 4, 9, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 4, 15, 55, 0, tzinfo=timezone.utc),
    ]
    for t in times:
        session.add(
            DepotSchedule(
                service_id=svc.id,
                vehicle_id=vehicle.id,
                direction=Direction.A_TO_B,
                operating_date=date(2026, 9, 4),
                planned_departure=t,
                status="PLANNED",
            )
        )
    session.commit()

    resp = client.get(
        f"/api/admin/fleet-schedules?service_id={svc.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    fleet_rows = resp.json()
    assert len(fleet_rows) == 4

    # Earliest is First Bus: 06:30
    assert fleet_rows[0]["departure_time"] == "06:30"
    # Latest is Last Bus: 15:55
    assert fleet_rows[-1]["departure_time"] == "15:55"

    # Confirms no ServiceSchedule exists yet: frequency must be empty/unconfigured, NOT derived from 06:30 vs 15:55
    sched_resp = client.get(
        f"/api/admin/services/{svc.id}/schedules",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sched_resp.status_code == 200
    assert sched_resp.json() == []


def test_service_update_cross_tenant_isolation(
    client: TestClient, admin_token: str, session: Session
):
    other_org = Organization(name=f"Isolated Org {uuid.uuid4().hex[:6]}")
    session.add(other_org)
    session.commit()

    other_route = Route(
        organization_id=other_org.id,
        route_code=f"RT_ISO_{uuid.uuid4().hex[:6]}",
        route_name="Isolated Route",
        distance_km=12.0,
    )
    session.add(other_route)
    session.commit()

    other_svc = Service(
        organization_id=other_org.id,
        route_id=other_route.id,
        service_code=f"SVC_ISO_{uuid.uuid4().hex[:6]}",
        service_name="Isolated Service",
        status=ServiceStatus.ACTIVE,
    )
    session.add(other_svc)
    session.commit()

    # Admin from different org attempts to update other_svc -> 404
    resp = client.put(
        f"/api/admin/services/{other_svc.id}",
        json={"service_name": "Hacked Name"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404

