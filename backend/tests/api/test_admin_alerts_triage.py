import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.main import app
from app.db.database import engine
from app.models.alert import ServiceAlert
from app.models.organization import Organization
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.service import Service
from app.models.route import Route, Stop
from app.models.enums import (
    AlertStatus,
    AlertSeverity,
    AlertScope,
    UserRole,
    VehicleStatus,
    ServiceStatus,
    RouteStatus,
    StopStatus,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def session():
    with Session(engine) as s:
        yield s


@pytest.fixture
def triage_org(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org Triage {suffix}")
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
def triage_admin_token(client: TestClient, session: Session, triage_org: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_triage_{suffix}@demo.com"
    admin = User(
        organization_id=triage_org.id,
        name="Triage Admin",
        email=email,
        password_hash=get_password_hash("password123"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()

    resp = client.post(
        "/api/admin/login",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def triage_entities(session: Session, triage_org: Organization):
    # Stop
    stop = Stop(
        organization_id=triage_org.id,
        stop_code=f"STP_{uuid.uuid4().hex[:6]}",
        name="Triage Terminal",
        latitude=22.5726,
        longitude=88.3639,
        location="SRID=4326;POINT(88.3639 22.5726)",
        status=StopStatus.ACTIVE,
    )
    session.add(stop)
    session.flush()

    # Route
    route = Route(
        organization_id=triage_org.id,
        route_code=f"RT_{uuid.uuid4().hex[:6]}",
        route_name="Triage Route 1",
        geometry="SRID=4326;LINESTRING(88.3639 22.5726, 88.3650 22.5750)",
        status=RouteStatus.ACTIVE,
    )
    session.add(route)
    session.flush()

    # Service
    svc = Service(
        organization_id=triage_org.id,
        route_id=route.id,
        service_code=f"SVC_{uuid.uuid4().hex[:6]}",
        service_name="Triage Express",
        status=ServiceStatus.ACTIVE,
    )
    session.add(svc)
    session.flush()

    # Vehicle
    veh = Vehicle(
        organization_id=triage_org.id,
        vehicle_number=f"VH-{uuid.uuid4().hex[:6]}",
        registration_number=f"WB-{uuid.uuid4().hex[:6]}",
        vehicle_type="BUS",
        status=VehicleStatus.ACTIVE,
    )
    session.add(veh)
    session.commit()
    session.refresh(stop)
    session.refresh(route)
    session.refresh(svc)
    session.refresh(veh)

    return {
        "stop": stop,
        "route": route,
        "service": svc,
        "vehicle": veh,
    }


def test_deterministic_urgency_ordering(
    client: TestClient,
    session: Session,
    triage_org: Organization,
    triage_admin_token: str,
    triage_entities: dict,
):
    """
    Test urgency hierarchy:
      1. OPEN CRITICAL (older outranks newer)
      2. ACKNOWLEDGED CRITICAL
      3. OPEN WARNING
      4. ACKNOWLEDGED WARNING
      5. OPEN INFO
      6. ACKNOWLEDGED INFO
      7. RESOLVED (newer resolution first)
    """
    now = datetime.now(timezone.utc)
    svc = triage_entities["service"]

    # Insert in deliberately scrambled order
    alerts = [
        # A: Resolved (should be last)
        ServiceAlert(
            organization_id=triage_org.id,
            service_id=svc.id,
            type="SERVICE_CROWDING_PATTERN",
            incident_fingerprint=f"TEST_FINGERPRINT_{uuid.uuid4()}",
            title="A: Resolved Alert",
            message="Message A",
            severity=AlertSeverity.CRITICAL,
            scope=AlertScope.SERVICE,
            status=AlertStatus.RESOLVED,
            created_at=now - timedelta(hours=10),
            resolved_at=now - timedelta(hours=1),
        ),
        # B: Open Warning (middle)
        ServiceAlert(
            organization_id=triage_org.id,
            service_id=svc.id,
            type="VEHICLE_OFFLINE_SCHEDULED",
            incident_fingerprint=f"TEST_FINGERPRINT_{uuid.uuid4()}",
            title="B: Open Warning",
            message="Message B",
            severity=AlertSeverity.WARNING,
            scope=AlertScope.SERVICE,
            status=AlertStatus.OPEN,
            created_at=now - timedelta(hours=4),
        ),
        # C: Open Critical Older (should be #1)
        ServiceAlert(
            organization_id=triage_org.id,
            service_id=svc.id,
            type="UNEXPECTED_MAINTENANCE",
            incident_fingerprint=f"TEST_FINGERPRINT_{uuid.uuid4()}",
            title="C: Open Critical Older",
            message="Message C",
            severity=AlertSeverity.CRITICAL,
            scope=AlertScope.SERVICE,
            status=AlertStatus.OPEN,
            created_at=now - timedelta(hours=5),
        ),
        # D: Open Critical Newer (should be #2)
        ServiceAlert(
            organization_id=triage_org.id,
            service_id=svc.id,
            type="UNEXPECTED_MAINTENANCE",
            incident_fingerprint=f"TEST_FINGERPRINT_{uuid.uuid4()}",
            title="D: Open Critical Newer",
            message="Message D",
            severity=AlertSeverity.CRITICAL,
            scope=AlertScope.SERVICE,
            status=AlertStatus.OPEN,
            created_at=now - timedelta(hours=2),
        ),
        # E: Acknowledged Critical (should be #3)
        ServiceAlert(
            organization_id=triage_org.id,
            service_id=svc.id,
            type="UNEXPECTED_MAINTENANCE",
            incident_fingerprint=f"TEST_FINGERPRINT_{uuid.uuid4()}",
            title="E: Acknowledged Critical",
            message="Message E",
            severity=AlertSeverity.CRITICAL,
            scope=AlertScope.SERVICE,
            status=AlertStatus.ACKNOWLEDGED,
            created_at=now - timedelta(hours=3),
        ),
    ]
    for a in alerts:
        session.add(a)
    session.commit()

    resp = client.get(
        "/api/admin/alerts",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 5
    items = data["data"]

    # Verify order of our 5 items
    titles = [item["title"] for item in items if item["title"].startswith(("A:", "B:", "C:", "D:", "E:"))]
    expected_order = [
        "C: Open Critical Older",     # #1: OPEN CRITICAL older
        "D: Open Critical Newer",     # #2: OPEN CRITICAL newer
        "E: Acknowledged Critical",   # #3: ACKNOWLEDGED CRITICAL
        "B: Open Warning",            # #4: OPEN WARNING
        "A: Resolved Alert",          # #5: RESOLVED
    ]
    assert titles == expected_order

    # Verify priority ranks and scores
    c_item = next(item for item in items if item["title"] == "C: Open Critical Older")
    assert c_item["urgency_rank"] == "#1"
    assert c_item["urgency_score"] == 95

    # Summary metrics should also reflect totals
    metrics = data["metrics"]
    assert metrics["active"] >= 4
    assert metrics["critical"] >= 3
    assert metrics["warning"] >= 1
    assert metrics["resolved"] >= 1


def test_search_and_filters(
    client: TestClient,
    session: Session,
    triage_org: Organization,
    triage_admin_token: str,
    triage_entities: dict,
):
    now = datetime.now(timezone.utc)
    svc = triage_entities["service"]
    unique_key = uuid.uuid4().hex[:6]

    a1 = ServiceAlert(
        organization_id=triage_org.id,
        service_id=svc.id,
        type="VEHICLE_OFFLINE_SCHEDULED",
        incident_fingerprint=f"FINGERPRINT_SEARCH_{unique_key}_1",
        title=f"SearchTitle {unique_key} Bravo",
        message="Battery dropped below threshold",
        severity=AlertSeverity.WARNING,
        scope=AlertScope.SERVICE,
        status=AlertStatus.OPEN,
        created_at=now,
    )
    a2 = ServiceAlert(
        organization_id=triage_org.id,
        service_id=svc.id,
        type="UNEXPECTED_MAINTENANCE",
        incident_fingerprint=f"FINGERPRINT_SEARCH_{unique_key}_2",
        title=f"OtherTitle {unique_key} Charlie",
        message="Transmission overheat",
        severity=AlertSeverity.CRITICAL,
        scope=AlertScope.SERVICE,
        status=AlertStatus.ACKNOWLEDGED,
        created_at=now,
    )
    session.add_all([a1, a2])
    session.commit()

    # Search by title keyword
    r1 = client.get(
        f"/api/admin/alerts?search=SearchTitle {unique_key}",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 1
    assert d1["data"][0]["title"] == a1.title

    # Filter by severity
    r2 = client.get(
        "/api/admin/alerts?severity=CRITICAL",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert r2.status_code == 200
    for itm in r2.json()["data"]:
        assert itm["severity"] == "CRITICAL"

    # Filter by status
    r3 = client.get(
        "/api/admin/alerts?status=ACKNOWLEDGED",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert r3.status_code == 200
    for itm in r3.json()["data"]:
        assert itm["status"] == "ACKNOWLEDGED"

    # Filter by type
    r4 = client.get(
        "/api/admin/alerts?type=UNEXPECTED_MAINTENANCE",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert r4.status_code == 200
    for itm in r4.json()["data"]:
        assert itm["type"] == "UNEXPECTED_MAINTENANCE"


def test_suggested_resolution_and_entity_context(
    client: TestClient,
    session: Session,
    triage_org: Organization,
    triage_admin_token: str,
    triage_entities: dict,
):
    svc = triage_entities["service"]
    veh = triage_entities["vehicle"]

    fingerprint = f"VEHICLE_OFFLINE_SCHEDULED_{triage_org.id}_{veh.id}_2026-09-05"
    alert = ServiceAlert(
        organization_id=triage_org.id,
        type="VEHICLE_OFFLINE_SCHEDULED",
        incident_fingerprint=fingerprint,
        title=f"Vehicle {veh.vehicle_number} Offline While Scheduled",
        message=f"Vehicle {veh.vehicle_number} is scheduled to operate today but is not actively tracking.",
        severity=AlertSeverity.WARNING,
        scope=AlertScope.SERVICE,
        service_id=svc.id,
        status=AlertStatus.OPEN,
        created_at=datetime.now(timezone.utc),
    )
    session.add(alert)
    session.commit()

    resp = client.get(
        f"/api/admin/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify Entity Context
    ctx = data["entity_context"]
    assert ctx is not None
    assert ctx["vehicle_id"] == str(veh.id)
    assert ctx["vehicle_number"] == veh.vehicle_number
    assert ctx["service_id"] == str(svc.id)
    assert ctx["service_code"] == svc.service_code

    # Verify Suggested Resolution
    res = data["suggested_resolution"]
    assert res is not None
    assert "Verify vehicle availability" in res["recommended_action"]
    assert "schedule" in res["reason"].lower()
    assert len(res["actions"]) >= 2

    # Check action destinations
    dests = [act["destination"] for act in res["actions"]]
    assert f"/fleet-schedules?serviceId={svc.id}" in dests
    assert f"/vehicles?serviceId={svc.id}" in dests


def test_unsupported_alert_type_fallback(
    client: TestClient,
    session: Session,
    triage_org: Organization,
    triage_admin_token: str,
    triage_entities: dict,
):
    svc = triage_entities["service"]
    alert = ServiceAlert(
        organization_id=triage_org.id,
        type="CUSTOM_UNKNOWN_INCIDENT",
        incident_fingerprint=f"CUSTOM_{uuid.uuid4()}",
        title="Unknown Hardware Incident",
        message="An unprecedented sensor alert was received.",
        severity=AlertSeverity.INFO,
        scope=AlertScope.SERVICE,
        service_id=svc.id,
        status=AlertStatus.OPEN,
        created_at=datetime.now(timezone.utc),
    )
    session.add(alert)
    session.commit()

    resp = client.get(
        f"/api/admin/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    res = data["suggested_resolution"]
    assert res is not None
    assert "No predefined resolution guidance is available for this alert type" in res["recommended_action"]


def test_lifecycle_acknowledge_and_resolve(
    client: TestClient,
    session: Session,
    triage_org: Organization,
    triage_admin_token: str,
    triage_entities: dict,
):
    svc = triage_entities["service"]
    alert = ServiceAlert(
        organization_id=triage_org.id,
        service_id=svc.id,
        type="VEHICLE_TRACKING_STALE",
        incident_fingerprint=f"LIFECYCLE_{uuid.uuid4()}",
        title="Lifecycle Test Alert",
        message="Testing explicit mutations only",
        severity=AlertSeverity.WARNING,
        scope=AlertScope.SERVICE,
        status=AlertStatus.OPEN,
        created_at=datetime.now(timezone.utc),
    )
    session.add(alert)
    session.commit()

    # 1. Opening case MUST NOT mutate status
    r_get = client.get(
        f"/api/admin/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert r_get.status_code == 200
    assert r_get.json()["status"] == "OPEN"

    session.refresh(alert)
    assert alert.status == AlertStatus.OPEN

    # 2. Explicit Acknowledge
    r_ack = client.put(
        f"/api/admin/alerts/{alert.id}/acknowledge",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
        json={},
    )
    assert r_ack.status_code == 200
    assert r_ack.json()["status"] == "ACKNOWLEDGED"

    session.refresh(alert)
    assert alert.status == AlertStatus.ACKNOWLEDGED
    assert alert.acknowledged_by is not None

    # 3. Cannot acknowledge already acknowledged alert
    r_ack2 = client.put(
        f"/api/admin/alerts/{alert.id}/acknowledge",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
        json={},
    )
    assert r_ack2.status_code == 400

    # 4. Explicit Resolve
    r_res = client.put(
        f"/api/admin/alerts/{alert.id}/resolve",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
        json={},
    )
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "RESOLVED"

    session.refresh(alert)
    assert alert.status == AlertStatus.RESOLVED
    assert alert.resolved_by is not None


def test_tenant_isolation(
    client: TestClient,
    session: Session,
    triage_org: Organization,
    other_org: Organization,
    triage_admin_token: str,
):
    # Route & Service for other org
    r_other = Route(
        organization_id=other_org.id,
        route_code=f"RT_OTH_{uuid.uuid4().hex[:6]}",
        route_name="Other Route",
        geometry="SRID=4326;LINESTRING(0 0, 1 1)",
        status=RouteStatus.ACTIVE,
    )
    session.add(r_other)
    session.flush()

    s_other = Service(
        organization_id=other_org.id,
        route_id=r_other.id,
        service_code=f"SVC_OTH_{uuid.uuid4().hex[:6]}",
        service_name="Other Svc",
        status=ServiceStatus.ACTIVE,
    )
    session.add(s_other)
    session.flush()

    # Alert in other org
    other_alert = ServiceAlert(
        organization_id=other_org.id,
        service_id=s_other.id,
        type="VEHICLE_TRACKING_STALE",
        incident_fingerprint=f"OTHER_{uuid.uuid4()}",
        title="Other Org Secret Alert",
        message="Top secret telemetry",
        severity=AlertSeverity.CRITICAL,
        scope=AlertScope.SERVICE,
        status=AlertStatus.OPEN,
        created_at=datetime.now(timezone.utc),
    )
    session.add(other_alert)
    session.commit()

    # Triage Admin should not see other org's alert in list
    r_list = client.get(
        "/api/admin/alerts",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert r_list.status_code == 200
    ids = [item["id"] for item in r_list.json()["data"]]
    assert str(other_alert.id) not in ids

    # Direct GET should return 404
    r_get = client.get(
        f"/api/admin/alerts/{other_alert.id}",
        headers={"Authorization": f"Bearer {triage_admin_token}"},
    )
    assert r_get.status_code == 404
