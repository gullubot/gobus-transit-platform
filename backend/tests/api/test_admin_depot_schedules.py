import uuid
from datetime import datetime, timezone, timedelta, date, time
import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, Direction, VehicleStatus, ServiceStatus, RouteStatus, StopStatus
from app.models.vehicle import Vehicle
from app.models.service import Service, DepotSchedule
from app.models.route import Route, Stop, RouteStop
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
    org = Organization(name=f"Org A DepotSched {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def admin_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_depot_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Depot A",
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
    org = Organization(name=f"Org B DepotSched {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def admin_b_token(client: TestClient, session: Session, org_b: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_depot_b_{suffix}@demo.com"
    admin = User(
        organization_id=org_b.id,
        name="Admin Depot B",
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


def _create_stop(session: Session, org_id: uuid.UUID, code: str, name: str) -> Stop:
    stop = Stop(
        organization_id=org_id,
        stop_code=code,
        name=name,
        location="SRID=4326;POINT(88.3639 22.5726)",
        status=StopStatus.ACTIVE,
    )
    session.add(stop)
    session.commit()
    session.refresh(stop)
    return stop


def _create_route_with_stops(session: Session, org_id: uuid.UUID, code: str, name: str, stops: list[Stop]) -> Route:
    route = Route(
        organization_id=org_id,
        route_code=code,
        route_name=name,
        status=RouteStatus.ACTIVE,
    )
    session.add(route)
    session.commit()
    session.refresh(route)

    for seq, st in enumerate(stops, start=1):
        rs = RouteStop(
            route_id=route.id,
            stop_id=st.id,
            sequence_number=seq,
        )
        session.add(rs)
    session.commit()
    return route


def _create_service(session: Session, org_id: uuid.UUID, route_id: uuid.UUID, code: str, name: str) -> Service:
    svc = Service(
        organization_id=org_id,
        route_id=route_id,
        service_code=code,
        service_name=name,
        status=ServiceStatus.ACTIVE,
    )
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc


def _create_vehicle(session: Session, org_id: uuid.UUID, number: str, reg_number: str) -> Vehicle:
    veh = Vehicle(
        organization_id=org_id,
        vehicle_number=number,
        registration_number=reg_number,
        vehicle_type="BUS",
        status=VehicleStatus.ACTIVE,
    )
    session.add(veh)
    session.commit()
    session.refresh(veh)
    return veh


def _create_schedule(session: Session, svc_id: uuid.UUID, veh_id: uuid.UUID, dep_time_str: str, direction: Direction, status_val: str = "PLANNED") -> DepotSchedule:
    h, m = map(int, dep_time_str.split(":"))
    sched = DepotSchedule(
        service_id=svc_id,
        vehicle_id=veh_id,
        direction=direction,
        operating_date=date.today(),
        planned_departure=datetime.combine(date.today(), time(h, m)),
        status=status_val,
        source="RECURRING_DAILY",
    )
    session.add(sched)
    session.commit()
    session.refresh(sched)
    return sched


# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------

def test_get_major_depots_discovers_route_endpoints_and_counts(client: TestClient, session: Session, org_a: Organization, admin_token: str):
    """Major depots are route endpoints (sequence 1 and max sequence) with counts and deduplication."""
    stop_hub = _create_stop(session, org_a.id, "HUB01", "Central Terminus Hub")
    stop_north = _create_stop(session, org_a.id, "NTH01", "North Depot")
    stop_south = _create_stop(session, org_a.id, "STH01", "South Depot")
    stop_mid = _create_stop(session, org_a.id, "MID01", "Intermediate Waypoint")

    # Route 1: North -> Hub (seq 1: North, seq 2: Waypoint, seq 3: Hub)
    _create_route_with_stops(session, org_a.id, "R1", "Route North to Central", [stop_north, stop_mid, stop_hub])
    # Route 2: Hub -> South (seq 1: Hub, seq 2: South)
    _create_route_with_stops(session, org_a.id, "R2", "Route Central to South", [stop_hub, stop_south])

    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/depot-schedules/major-depots", headers=headers)
    assert res.status_code == 200
    depots = res.json()

    # Intermediate Waypoint is NOT an endpoint, so only 3 major depots
    names = {d["stop_name"]: d for d in depots}
    assert "Intermediate Waypoint" not in names
    assert "Central Terminus Hub" in names
    assert "North Depot" in names
    assert "South Depot" in names

    # Central Terminus Hub is an endpoint of 2 routes (End of R1, Start of R2)
    assert names["Central Terminus Hub"]["routes_count"] == 2
    assert names["North Depot"]["routes_count"] == 1
    assert names["South Depot"]["routes_count"] == 1


def test_major_depots_tenant_isolation(client: TestClient, session: Session, org_a: Organization, admin_token: str, org_b: Organization, admin_b_token: str):
    """Admin of Org A cannot see major depots of Org B."""
    stop_a = _create_stop(session, org_a.id, "OA01", "Org A Depot")
    stop_a_end = _create_stop(session, org_a.id, "OA02", "Org A Far End")
    _create_route_with_stops(session, org_a.id, "RA1", "Route Org A", [stop_a, stop_a_end])

    stop_b = _create_stop(session, org_b.id, "OB01", "Org B Depot")
    stop_b_end = _create_stop(session, org_b.id, "OB02", "Org B Far End")
    _create_route_with_stops(session, org_b.id, "RB1", "Route Org B", [stop_b, stop_b_end])

    headers_a = {"Authorization": f"Bearer {admin_token}"}
    res_a = client.get("/api/admin/depot-schedules/major-depots", headers=headers_a)
    assert res_a.status_code == 200
    names_a = [d["stop_name"] for d in res_a.json()]
    assert "Org A Depot" in names_a
    assert "Org B Depot" not in names_a

    headers_b = {"Authorization": f"Bearer {admin_b_token}"}
    res_b = client.get("/api/admin/depot-schedules/major-depots", headers=headers_b)
    assert res_b.status_code == 200
    names_b = [d["stop_name"] for d in res_b.json()]
    assert "Org B Depot" in names_b
    assert "Org A Depot" not in names_b


def test_depot_departures_independent_route_destination_derivation(client: TestClient, session: Session, org_a: Organization, admin_token: str):
    """
    Every departure independently derives Origin -> Destination based on:
    Selected Major Depot + Service + Route + Direction.
    """
    stop_hub = _create_stop(session, org_a.id, "HUB10", "Main Junction Depot")
    stop_beach = _create_stop(session, org_a.id, "BCH10", "Beach Terminal")
    stop_airport = _create_stop(session, org_a.id, "AIR10", "Airport Station")

    # Route 1: Hub -> Beach (Hub is Start Stop A, Beach is End Stop B)
    route_beach = _create_route_with_stops(session, org_a.id, "RT-BCH", "Hub to Beach", [stop_hub, stop_beach])
    svc_beach = _create_service(session, org_a.id, route_beach.id, "SVC-BCH", "Beach Express")

    # Route 2: Airport -> Hub (Airport is Start Stop A, Hub is End Stop B)
    route_airport = _create_route_with_stops(session, org_a.id, "RT-AIR", "Airport to Hub", [stop_airport, stop_hub])
    svc_airport = _create_service(session, org_a.id, route_airport.id, "SVC-AIR", "Airport Shuttle")

    veh1 = _create_vehicle(session, org_a.id, "BUS-01", "WB-01-AA-1111")
    veh2 = _create_vehicle(session, org_a.id, "BUS-02", "WB-02-BB-2222")

    # Departure 1: Beach Express departing from Main Junction Depot:
    # Main Junction Depot is Start Stop (A), so direction is A_TO_B, heading to Beach Terminal
    _create_schedule(session, svc_beach.id, veh1.id, "08:00", Direction.A_TO_B)

    # Departure 2: Airport Shuttle departing from Main Junction Depot:
    # Main Junction Depot is End Stop (B), so departures from Main Junction Depot use direction B_TO_A, heading to Airport Station
    _create_schedule(session, svc_airport.id, veh2.id, "07:30", Direction.B_TO_A)

    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get(f"/api/admin/depot-schedules/departures?depot_stop_id={stop_hub.id}", headers=headers)
    assert res.status_code == 200
    deps = res.json()
    assert len(deps) == 2

    # Chronologically sorted: 07:30 before 08:00
    assert deps[0]["departure_time"] == "07:30"
    assert deps[0]["service_code"] == "SVC-AIR"
    assert deps[0]["vehicle_number"] == "BUS-02"
    assert deps[0]["registration_number"] == "WB-02-BB-2222"
    assert deps[0]["origin_stop_name"] == "Main Junction Depot"
    assert deps[0]["destination_stop_name"] == "Airport Station"
    assert deps[0]["direction"] == Direction.B_TO_A.value

    assert deps[1]["departure_time"] == "08:00"
    assert deps[1]["service_code"] == "SVC-BCH"
    assert deps[1]["vehicle_number"] == "BUS-01"
    assert deps[1]["registration_number"] == "WB-01-AA-1111"
    assert deps[1]["origin_stop_name"] == "Main Junction Depot"
    assert deps[1]["destination_stop_name"] == "Beach Terminal"
    assert deps[1]["direction"] == Direction.A_TO_B.value


def test_depot_departures_excludes_cancelled_and_ignores_crew(client: TestClient, session: Session, org_a: Organization, admin_token: str):
    """Cancelled schedules are excluded and driver/conductor are not exposed."""
    stop_a = _create_stop(session, org_a.id, "STA01", "Station Alpha")
    stop_b = _create_stop(session, org_a.id, "STB01", "Station Beta")
    route = _create_route_with_stops(session, org_a.id, "R-AB", "Alpha to Beta", [stop_a, stop_b])
    svc = _create_service(session, org_a.id, route.id, "SVC-AB", "Alpha Service")
    veh = _create_vehicle(session, org_a.id, "BUS-99", "WB-99-ZZ-9999")

    # Planned schedule
    _create_schedule(session, svc.id, veh.id, "09:00", Direction.A_TO_B, status_val="PLANNED")
    # Cancelled schedule
    _create_schedule(session, svc.id, veh.id, "10:00", Direction.A_TO_B, status_val="CANCELLED")

    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get(f"/api/admin/depot-schedules/departures?depot_stop_id={stop_a.id}", headers=headers)
    assert res.status_code == 200
    deps = res.json()
    assert len(deps) == 1
    assert deps[0]["departure_time"] == "09:00"

    # Verify no driver or conductor keys in the departure item
    assert "driver" not in deps[0]
    assert "conductor" not in deps[0]


def test_depot_departures_unauthorized_stop_returns_404(client: TestClient, org_b: Organization, session: Session, admin_token: str):
    """Requesting departures for a depot belonging to another organization returns 404."""
    stop_b = _create_stop(session, org_b.id, "EXT01", "External Org Stop")
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get(f"/api/admin/depot-schedules/departures?depot_stop_id={stop_b.id}", headers=headers)
    assert res.status_code == 404
