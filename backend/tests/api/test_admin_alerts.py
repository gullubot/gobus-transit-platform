import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.alert import ServiceAlert
from app.models.enums import AlertStatus, AlertSeverity, AlertScope
from app.services.alert_engine import AlertEngine
from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole
from app.main import app
from app.db.database import engine

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def session():
    with Session(engine) as s:
        yield s

@pytest.fixture
def org_a(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org A Alerts {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_a_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_alerts_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Alerts A",
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
def service_a(session: Session, org_a: Organization):
    from app.models.service import Service
    from app.models.route import Route
    from app.models.enums import ServiceStatus
    route = Route(organization_id=org_a.id, route_code="RT_TEST", route_name="Test Route", geometry="SRID=4326;LINESTRING(0 0, 1 1)")
    session.add(route)
    session.commit()
    session.refresh(route)
    
    svc = Service(organization_id=org_a.id, route_id=route.id, service_code="SVC_TEST", service_name="Test Svc", status=ServiceStatus.ACTIVE)
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc

@pytest.fixture
def sample_alert(session: Session, org_a: Organization, service_a):
    alert = ServiceAlert(
        organization_id=org_a.id,
        type="TEST_ALERT",
        incident_fingerprint=f"TEST_ALERT_{org_a.id}",
        title="Test Alert",
        message="This is a test alert",
        severity=AlertSeverity.INFO,
        scope=AlertScope.SERVICE,
        service_id=service_a.id,
        status=AlertStatus.OPEN
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert

def test_get_alerts(client: TestClient, admin_a_token: str, sample_alert: ServiceAlert):
    response = client.get("/api/admin/alerts", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(a["id"] == str(sample_alert.id) for a in data["data"])

def test_acknowledge_alert(client: TestClient, admin_a_token: str, session: Session, sample_alert: ServiceAlert):
    response = client.put(f"/api/admin/alerts/{sample_alert.id}/acknowledge", headers={"Authorization": f"Bearer {admin_a_token}"}, json={})
    assert response.status_code == 200
    assert response.json()["status"] == "ACKNOWLEDGED"

    session.refresh(sample_alert)
    assert sample_alert.status == AlertStatus.ACKNOWLEDGED
    assert sample_alert.acknowledged_by is not None

def test_resolve_alert(client: TestClient, admin_a_token: str, session: Session, sample_alert: ServiceAlert):
    response = client.put(f"/api/admin/alerts/{sample_alert.id}/resolve", headers={"Authorization": f"Bearer {admin_a_token}"}, json={})
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"

    session.refresh(sample_alert)
    assert sample_alert.status == AlertStatus.RESOLVED
    assert sample_alert.resolved_by is not None

def test_alert_engine_upsert(session: Session, org_a: Organization, service_a):
    engine = AlertEngine(session)
    
    # First insert
    alert1 = engine._upsert_alert(
        organization_id=org_a.id,
        type_="TEST_ENGINE",
        fingerprint=f"TEST_ENGINE_{org_a.id}",
        title="Engine Test",
        message="Test msg",
        suggested_solution="N/A",
        severity=AlertSeverity.WARNING,
        scope=AlertScope.SERVICE,
        service_id=service_a.id
    )
    session.commit()
    
    assert alert1.status == AlertStatus.OPEN
    
    # Second insert with same fingerprint should return the same object and not insert duplicate
    alert2 = engine._upsert_alert(
        organization_id=org_a.id,
        type_="TEST_ENGINE",
        fingerprint=f"TEST_ENGINE_{org_a.id}",
        title="Engine Test 2",
        message="Test msg 2",
        suggested_solution="N/A",
        severity=AlertSeverity.WARNING,
        scope=AlertScope.SERVICE,
        service_id=service_a.id
    )
    assert alert1.id == alert2.id
    
    stmt = select(ServiceAlert).where(ServiceAlert.incident_fingerprint == f"TEST_ENGINE_{org_a.id}")
    res = session.execute(stmt)
    rows = res.scalars().all()
    assert len(rows) == 1
