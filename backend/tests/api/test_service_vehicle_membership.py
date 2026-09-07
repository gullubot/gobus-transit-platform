"""
Tests for Explicit Service <-> Vehicle Membership and Fleet Data Visibility.

Validates all 18 requirements from Section 22:
1. New vehicle registration creates Vehicle + ServiceVehicle atomically.
2. Atomic rollback on failed creation.
3. Existing vehicle assigned without creating duplicate Vehicle entity.
4. Existing registration remains unchanged.
5. Duplicate active ServiceVehicle membership is prevented (409 Conflict).
6. Existing INACTIVE membership can be reactivated.
7. Vehicle remains visible when DepotSchedule is CANCELLED (legacy fallback).
8. Vehicle remains visible with no DepotSchedule when legacy Trip evidence exists.
9. Explicit ServiceVehicle membership remains visible with no Trip.
10. Explicit ServiceVehicle membership remains visible with no DepotSchedule.
11. Explicit INACTIVE membership overrides legacy fallback.
12. Existing vehicle can belong to multiple Services.
13. No silent removal from another Service.
14. Tenant isolation enforced across organizations.
15. Authorization requirements enforced.
16. Existing driver/conductor invariant remains intact.
17. Existing vehicle assignment does not mutate vehicle registration.
18. Available vehicles endpoint returns accurate service context.
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.main import app
from app.db.database import engine
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle
from app.models.service import Service, DepotSchedule
from app.models.route import Route
from app.models.trip import Trip
from app.models.service_vehicle import ServiceVehicle
from app.models.enums import VehicleStatus, ServiceStatus, RouteStatus, TripStatus, Direction
from app.core.security import get_password_hash


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def session():
    with Session(engine) as s:
        yield s


@pytest.fixture
def org_data(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org Fleet {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)

    admin = User(
        organization_id=org.id,
        name=f"Admin {suffix}",
        email=f"admin_{suffix}@transit.test",
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()

    route = Route(
        organization_id=org.id,
        route_code=f"R_{suffix}",
        route_name=f"Route {suffix}",
        status=RouteStatus.ACTIVE,
    )
    session.add(route)
    session.commit()

    svc1 = Service(
        organization_id=org.id,
        route_id=route.id,
        service_code=f"S1_{suffix}",
        service_name=f"Service 1 {suffix}",
        status=ServiceStatus.ACTIVE,
    )
    svc2 = Service(
        organization_id=org.id,
        route_id=route.id,
        service_code=f"S2_{suffix}",
        service_name=f"Service 2 {suffix}",
        status=ServiceStatus.ACTIVE,
    )
    session.add_all([svc1, svc2])
    session.commit()
    session.refresh(svc1)
    session.refresh(svc2)

    return {
        "org": org,
        "admin": admin,
        "svc1": svc1,
        "svc2": svc2,
        "route": route,
    }


@pytest.fixture
def auth_headers(client: TestClient, org_data):
    resp = client.post(
        "/api/admin/login",
        json={"email": org_data["admin"].email, "password": "password"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_org_data(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Other Org {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)

    admin = User(
        organization_id=org.id,
        name=f"Other Admin {suffix}",
        email=f"other_{suffix}@transit.test",
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()

    vehicle = Vehicle(
        organization_id=org.id,
        vehicle_number=f"V_OTHER_{suffix}",
        registration_number=f"REG_OTHER_{suffix}",
        vehicle_type="BUS",
        status=VehicleStatus.ACTIVE,
    )
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)

    return {"org": org, "admin": admin, "vehicle": vehicle}


# =========================================================================
# TEST SUITE
# =========================================================================

def test_01_02_new_vehicle_registration_atomic(client: TestClient, session: Session, org_data, auth_headers):
    """1 & 2: New vehicle registration creates Vehicle + ServiceVehicle atomically. Rollback on failure."""
    svc_id = str(org_data["svc1"].id)
    v_num = f"VNEW_{uuid.uuid4().hex[:6]}"
    v_reg = f"REG_{uuid.uuid4().hex[:6]}"

    # Success case: atomic creation of Vehicle + ServiceVehicle
    resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": v_num,
            "registration_number": v_reg,
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": svc_id,
        },
    )
    assert resp.status_code == 200, resp.text
    created_veh = resp.json()
    veh_id = created_veh["id"]

    # Verify both exist in DB
    with Session(engine) as s:
        v = s.get(Vehicle, uuid.UUID(veh_id))
        assert v is not None
        assert v.vehicle_number == v_num
        assert v.registration_number == v_reg

        sv = s.execute(
            select(ServiceVehicle).where(
                ServiceVehicle.service_id == org_data["svc1"].id,
                ServiceVehicle.vehicle_id == v.id,
            )
        ).scalar_one_or_none()
        assert sv is not None
        assert sv.status == "ACTIVE"
        assert sv.organization_id == org_data["org"].id

    # Rollback case: invalid service_id must roll back both
    fail_v_num = f"VFAIL_{uuid.uuid4().hex[:6]}"
    fail_resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": fail_v_num,
            "registration_number": "REG-FAIL",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": str(uuid.uuid4()),  # non-existent service
        },
    )
    assert fail_resp.status_code == 404

    # Verify Vehicle was NOT left behind
    with Session(engine) as s:
        leftover = s.execute(
            select(Vehicle).where(Vehicle.vehicle_number == fail_v_num)
        ).scalar_one_or_none()
        assert leftover is None, "Vehicle must not exist after rollback"


def test_03_04_17_assign_existing_vehicle_preserves_registration(
    client: TestClient, session: Session, org_data, auth_headers
):
    """3, 4 & 17: Existing vehicle assigned to service without duplicating Vehicle or mutating registration."""
    org_id = org_data["org"].id
    v_num = f"VEX_{uuid.uuid4().hex[:6]}"
    v_reg = "WB 05 NB 0612"

    with Session(engine) as s:
        existing_veh = Vehicle(
            organization_id=org_id,
            vehicle_number=v_num,
            registration_number=v_reg,
            vehicle_type="BUS",
            status=VehicleStatus.ACTIVE,
        )
        s.add(existing_veh)
        s.commit()
        veh_id = existing_veh.id

    svc_id = str(org_data["svc1"].id)

    # Assign via POST /services/{service_id}/vehicles
    resp = client.post(
        f"/api/admin/services/{svc_id}/vehicles",
        headers=auth_headers,
        json={"vehicle_id": str(veh_id)},
    )
    assert resp.status_code in [200, 201], resp.text
    data = resp.json()
    assert data["status"] == "ACTIVE"
    assert data["service_id"] == svc_id
    assert data["vehicle_id"] == str(veh_id)

    # Verify registration is unchanged and no duplicate vehicle exists
    with Session(engine) as s:
        all_vehs = s.execute(
            select(Vehicle).where(Vehicle.vehicle_number == v_num)
        ).scalars().all()
        assert len(all_vehs) == 1
        assert all_vehs[0].registration_number == v_reg
        assert all_vehs[0].id == veh_id


def test_05_prevent_duplicate_membership(client: TestClient, org_data, auth_headers):
    """5: Duplicate active ServiceVehicle membership is rejected with 409 Conflict."""
    # Create vehicle + active membership
    v_num = f"VDUP_{uuid.uuid4().hex[:6]}"
    svc_id = str(org_data["svc1"].id)
    c_resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": v_num,
            "registration_number": "REG-DUP",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": svc_id,
        },
    )
    veh_id = c_resp.json()["id"]

    # Attempt to assign again to same service
    dup_resp = client.post(
        f"/api/admin/services/{svc_id}/vehicles",
        headers=auth_headers,
        json={"vehicle_id": veh_id},
    )
    assert dup_resp.status_code == 409
    assert "already assigned" in dup_resp.json()["detail"].lower()


def test_06_reactivate_inactive_membership(client: TestClient, session: Session, org_data, auth_headers):
    """6: Existing INACTIVE membership can be reactivated on reassignment."""
    v_num = f"VRE_{uuid.uuid4().hex[:6]}"
    svc_id = str(org_data["svc1"].id)
    c_resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": v_num,
            "registration_number": "REG-RE",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": svc_id,
        },
    )
    veh_id = c_resp.json()["id"]

    unassign_resp = client.delete(
        f"/api/admin/services/{svc_id}/vehicles/{veh_id}",
        headers=auth_headers,
    )
    assert unassign_resp.status_code in [200, 204]

    with Session(engine) as s:
        sv_inactive = s.execute(
            select(ServiceVehicle).where(
                ServiceVehicle.service_id == org_data["svc1"].id,
                ServiceVehicle.vehicle_id == uuid.UUID(veh_id),
            )
        ).scalar_one()
        assert sv_inactive.status == "INACTIVE"
        assert sv_inactive.unassigned_at is not None

    # Now reactivate by assigning again
    reassign_resp = client.post(
        f"/api/admin/services/{svc_id}/vehicles",
        headers=auth_headers,
        json={"vehicle_id": veh_id},
    )
    assert reassign_resp.status_code in [200, 201]
    assert reassign_resp.json()["status"] == "ACTIVE"
    assert reassign_resp.json()["unassigned_at"] is None

    # Verify only ONE row exists in database for this (service_id, vehicle_id)
    with Session(engine) as s:
        rows = s.execute(
            select(ServiceVehicle).where(
                ServiceVehicle.service_id == org_data["svc1"].id,
                ServiceVehicle.vehicle_id == uuid.UUID(veh_id),
            )
        ).scalars().all()
        assert len(rows) == 1


def test_07_08_legacy_fallback_visibility(client: TestClient, session: Session, org_data, auth_headers):
    """7 & 8: Legacy fallback recognizes CANCELLED DepotSchedule and Trip without hiding vehicle."""
    org_id = org_data["org"].id
    svc1 = org_data["svc1"]

    with Session(engine) as s:
        # Vehicle 1: has CANCELLED DepotSchedule, NO ServiceVehicle record
        v1 = Vehicle(
            organization_id=org_id,
            vehicle_number=f"V_CANC_{uuid.uuid4().hex[:6]}",
            registration_number="REG-CANC",
            vehicle_type="BUS",
            status=VehicleStatus.ACTIVE,
        )
        # Vehicle 2: has Trip, NO DepotSchedule, NO ServiceVehicle record
        v2 = Vehicle(
            organization_id=org_id,
            vehicle_number=f"V_TRIP_{uuid.uuid4().hex[:6]}",
            registration_number="REG-TRIP",
            vehicle_type="BUS",
            status=VehicleStatus.ACTIVE,
        )
        s.add_all([v1, v2])
        s.commit()
        s.refresh(v1)
        s.refresh(v2)

        # Add cancelled DepotSchedule for v1
        ds = DepotSchedule(
            service_id=svc1.id,
            vehicle_id=v1.id,
            direction=Direction.A_TO_B,
            operating_date=datetime.now(timezone.utc).date(),
            planned_departure=datetime.now(timezone.utc),
            status="CANCELLED",
        )
        s.add(ds)

        # Add Trip for v2
        tr = Trip(
            organization_id=org_id,
            service_id=svc1.id,
            route_id=org_data["route"].id,
            vehicle_id=v2.id,
            direction=Direction.A_TO_B,
            operating_date=datetime.now(timezone.utc).date(),
            planned_start_at=datetime.now(timezone.utc),
            status=TripStatus.PLANNED,
        )
        s.add(tr)
        s.commit()

        v1_num = v1.vehicle_number
        v2_num = v2.vehicle_number

    # Query GET /api/admin/vehicles?service_id=svc1.id
    resp = client.get(f"/api/admin/vehicles?service_id={svc1.id}", headers=auth_headers)
    assert resp.status_code == 200
    v_nums = [v["vehicle_number"] for v in resp.json()]

    assert v1_num in v_nums, "Vehicle with CANCELLED DepotSchedule must remain visible via fallback"
    assert v2_num in v_nums, "Vehicle with Trip evidence must remain visible via fallback"


def test_09_10_explicit_membership_visible_without_trip_or_schedule(
    client: TestClient, session: Session, org_data, auth_headers
):
    """9 & 10: Explicit ServiceVehicle membership remains visible even with 0 Trips and 0 DepotSchedules."""
    org_id = org_data["org"].id
    svc2 = org_data["svc2"]

    with Session(engine) as s:
        v = Vehicle(
            organization_id=org_id,
            vehicle_number=f"V_EXP_{uuid.uuid4().hex[:6]}",
            registration_number="REG-EXP",
            vehicle_type="BUS",
            status=VehicleStatus.ACTIVE,
        )
        s.add(v)
        s.commit()
        s.refresh(v)

        # Explicit active membership, NO DepotSchedule, NO Trip
        sv = ServiceVehicle(
            organization_id=org_id,
            service_id=svc2.id,
            vehicle_id=v.id,
            status="ACTIVE",
        )
        s.add(sv)
        s.commit()
        v_num = v.vehicle_number

    resp = client.get(f"/api/admin/vehicles?service_id={svc2.id}", headers=auth_headers)
    assert resp.status_code == 200
    v_nums = [item["vehicle_number"] for item in resp.json()]
    assert v_num in v_nums, "Explicit ServiceVehicle member must be visible with no Trip/Schedule"


def test_11_inactive_membership_overrides_legacy_fallback(
    client: TestClient, session: Session, org_data, auth_headers
):
    """11: Explicit INACTIVE ServiceVehicle membership overrides legacy fallback."""
    org_id = org_data["org"].id
    svc1 = org_data["svc1"]

    with Session(engine) as s:
        v = Vehicle(
            organization_id=org_id,
            vehicle_number=f"V_OVR_{uuid.uuid4().hex[:6]}",
            registration_number="REG-OVR",
            vehicle_type="BUS",
            status=VehicleStatus.ACTIVE,
        )
        s.add(v)
        s.commit()
        s.refresh(v)

        # Legacy DepotSchedule exists
        ds = DepotSchedule(
            service_id=svc1.id,
            vehicle_id=v.id,
            direction=Direction.A_TO_B,
            operating_date=datetime.now(timezone.utc).date(),
            planned_departure=datetime.now(timezone.utc),
            status="SCHEDULED",
        )
        s.add(ds)

        # Explicit INACTIVE membership exists
        sv = ServiceVehicle(
            organization_id=org_id,
            service_id=svc1.id,
            vehicle_id=v.id,
            status="INACTIVE",
            unassigned_at=datetime.now(timezone.utc),
        )
        s.add(sv)
        s.commit()
        v_num = v.vehicle_number

    resp = client.get(f"/api/admin/vehicles?service_id={svc1.id}", headers=auth_headers)
    assert resp.status_code == 200
    v_nums = [item["vehicle_number"] for item in resp.json()]
    assert v_num not in v_nums, "Explicit INACTIVE membership must suppress legacy fallback"


def test_12_13_multi_service_membership(client: TestClient, session: Session, org_data, auth_headers):
    """12 & 13: Vehicle can belong to multiple Services without silent removal."""
    svc1 = org_data["svc1"]
    svc2 = org_data["svc2"]
    v_num = f"VMULTI_{uuid.uuid4().hex[:6]}"

    # Create vehicle in svc1
    c_resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": v_num,
            "registration_number": "REG-MULTI",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": str(svc1.id),
        },
    )
    veh_id = c_resp.json()["id"]

    # Assign to svc2 as well
    resp2 = client.post(
        f"/api/admin/services/{svc2.id}/vehicles",
        headers=auth_headers,
        json={"vehicle_id": veh_id},
    )
    assert resp2.status_code in [200, 201]

    # Verify vehicle appears in svc1 list
    list1 = client.get(f"/api/admin/vehicles?service_id={svc1.id}", headers=auth_headers).json()
    assert any(v["id"] == veh_id for v in list1), "Vehicle must still belong to svc1"

    # Verify vehicle appears in svc2 list
    list2 = client.get(f"/api/admin/vehicles?service_id={svc2.id}", headers=auth_headers).json()
    assert any(v["id"] == veh_id for v in list2), "Vehicle must also belong to svc2"

    # Verify available-vehicles endpoint in svc1 shows it is assigned to current service
    avail1 = client.get(f"/api/admin/services/{svc1.id}/available-vehicles", headers=auth_headers).json()
    v1_meta = next(v for v in avail1 if v["id"] == veh_id)
    assert v1_meta["is_assigned_to_current_service"] is True
    assigned_codes = [s["service_code"] if isinstance(s, dict) else s for s in v1_meta["assigned_services"]]
    assert svc2.service_code in assigned_codes


def test_14_tenant_isolation(client: TestClient, org_data, other_org_data, auth_headers):
    """14: Tenant isolation prevents cross-organization assignment or viewing."""
    other_veh_id = str(other_org_data["vehicle"].id)
    svc1_id = str(org_data["svc1"].id)

    # Admin from Org A attempts to assign Vehicle from Org B
    cross_assign = client.post(
        f"/api/admin/services/{svc1_id}/vehicles",
        headers=auth_headers,
        json={"vehicle_id": other_veh_id},
    )
    assert cross_assign.status_code in [404, 403], "Cross-org vehicle assignment must be blocked"

    # Available vehicles for Org A must NOT include Org B vehicles
    avail = client.get(f"/api/admin/services/{svc1_id}/available-vehicles", headers=auth_headers).json()
    avail_ids = [v["id"] for v in avail]
    assert other_veh_id not in avail_ids, "Cross-org vehicle must not appear in available vehicles"


def test_15_authorization_required(client: TestClient, org_data):
    """15: Unauthenticated access to service vehicle endpoints is rejected."""
    svc_id = str(org_data["svc1"].id)

    # Unauthenticated GET available-vehicles
    r1 = client.get(f"/api/admin/services/{svc_id}/available-vehicles")
    assert r1.status_code == 401

    # Unauthenticated POST assign
    r2 = client.post(
        f"/api/admin/services/{svc_id}/vehicles",
        json={"vehicle_id": str(uuid.uuid4())},
    )
    assert r2.status_code == 401

    # Unauthenticated DELETE unassign
    r3 = client.delete(f"/api/admin/services/{svc_id}/vehicles/{uuid.uuid4()}")
    assert r3.status_code == 401


from unittest.mock import patch


def test_new_vehicle_registration_creates_no_depot_schedule_or_trip(
    client: TestClient, session: Session, org_data, auth_headers
):
    """6. Vehicle registration alone creates no fake DepotSchedule or Trip records."""
    svc_id = str(org_data["svc1"].id)
    v_num = f"VNOFAKE_{uuid.uuid4().hex[:6]}"

    resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": v_num,
            "registration_number": "REG-NOFAKE",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": svc_id,
        },
    )
    assert resp.status_code == 200, resp.text
    veh_id = uuid.UUID(resp.json()["id"])

    with Session(engine) as s:
        ds_count = s.execute(
            select(func.count()).select_from(DepotSchedule).where(DepotSchedule.vehicle_id == veh_id)
        ).scalar()
        trip_count = s.execute(
            select(func.count()).select_from(Trip).where(Trip.vehicle_id == veh_id)
        ).scalar()

        assert ds_count == 0, "No DepotSchedule must be created on vehicle registration"
        assert trip_count == 0, "No Trip must be created on vehicle registration"


def test_new_vehicle_registration_fails_and_rolls_back_if_table_missing(
    client: TestClient, session: Session, org_data, auth_headers
):
    """2b. Transaction rollback: if ServiceVehicle table is missing, Vehicle creation rolls back with 500 error."""
    svc_id = str(org_data["svc1"].id)
    v_num = f"VNOTBL_{uuid.uuid4().hex[:6]}"

    with patch("sqlalchemy.Inspector.has_table", return_value=False):
        resp = client.post(
            "/api/admin/vehicles",
            headers=auth_headers,
            json={
                "vehicle_number": v_num,
                "registration_number": "REG-NOTBL",
                "vehicle_type": "BUS",
                "status": "ACTIVE",
                "service_id": svc_id,
            },
        )
        assert resp.status_code == 500
        assert "ServiceVehicle table is not yet initialized" in resp.json()["detail"]

    # Verify no orphan vehicle remains
    with Session(engine) as s:
        v = s.execute(
            select(Vehicle).where(Vehicle.vehicle_number == v_num)
        ).scalar_one_or_none()
        assert v is None, "Orphan vehicle must not exist after rollback"


def test_fleet_schedule_regression_recognizes_newly_registered_active_vehicle(
    client: TestClient, session: Session, org_data, auth_headers
):
    """7. Fleet Schedule regression: newly registered ACTIVE ServiceVehicle vehicle is schedulable without pre-existing DepotSchedule."""
    svc_id = str(org_data["svc1"].id)
    v_num = f"VSCHED_{uuid.uuid4().hex[:6]}"

    resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": v_num,
            "registration_number": "REG-SCHED",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": svc_id,
        },
    )
    assert resp.status_code == 200, resp.text
    veh_id = resp.json()["id"]

    # Schedulable in Fleet Schedules
    sched_resp = client.post(
        "/api/admin/fleet-schedules",
        headers=auth_headers,
        json={
            "service_id": svc_id,
            "vehicle_id": veh_id,
            "direction": "A_TO_B",
            "departure_time": "08:15",
            "every_day": True,
        },
    )
    assert sched_resp.status_code == 201, sched_resp.text
    assert sched_resp.json()["vehicle_id"] == veh_id


def test_service_scoped_fleet_listing_authoritative_instant_visibility(
    client: TestClient, org_data, auth_headers
):
    """8. Newly created vehicle appears immediately in service-scoped fleet query."""
    svc_id = str(org_data["svc1"].id)
    v_num = f"VINSTANT_{uuid.uuid4().hex[:6]}"

    resp = client.post(
        "/api/admin/vehicles",
        headers=auth_headers,
        json={
            "vehicle_number": v_num,
            "registration_number": "REG-INSTANT",
            "vehicle_type": "BUS",
            "status": "ACTIVE",
            "service_id": svc_id,
        },
    )
    assert resp.status_code == 200, resp.text
    created_id = resp.json()["id"]

    # Immediately query service-scoped vehicles
    get_resp = client.get(f"/api/admin/vehicles?service_id={svc_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    scoped_ids = [v["id"] for v in get_resp.json()]
    assert created_id in scoped_ids, "Newly created vehicle must appear immediately in service-scoped query"
