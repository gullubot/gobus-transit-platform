import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole
from app.db.database import engine
from app.main import app
from app.models.service import Service
from app.models.route import Route

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
    org = Organization(name=f"Org A Sch {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_sch_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Sch A",
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
    route = Route(organization_id=org_a.id, route_code="RT_SCH", route_name="Sch Route", geometry="SRID=4326;LINESTRING(0 0, 1 1)")
    session.add(route)
    session.commit()
    session.refresh(route)
    svc = Service(organization_id=org_a.id, route_id=route.id, service_code="SVC_SCH", service_name="Sch Svc")
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc

def test_crud_service_schedule(client: TestClient, admin_token: str, service_a: Service):
    service_id = str(service_a.id)
    
    # Create Schedule
    create_payload = {
        "direction": "A_TO_B",
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "typical_interval_minutes": 15,
        "days_of_week": [1, 2, 3, 4, 5],
        "effective_from": datetime.now(timezone.utc).isoformat()
    }
    
    resp = client.post(
        f"/api/admin/services/{service_id}/schedules",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=create_payload
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["direction"] == "A_TO_B"
    assert data["typical_interval_minutes"] == 15
    schedule_id = data["id"]
    
    # Read schedules
    resp = client.get(f"/api/admin/services/{service_id}/schedules", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    
    # Update schedule
    update_payload = {
        "typical_interval_minutes": 10
    }
    resp = client.put(
        f"/api/admin/services/{service_id}/schedules/{schedule_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=update_payload
    )
    assert resp.status_code == 200
    assert resp.json()["typical_interval_minutes"] == 10
    
    # Delete schedule
    resp = client.delete(
        f"/api/admin/services/{service_id}/schedules/{schedule_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 204
    
    # Read schedules (should be empty)
    resp = client.get(f"/api/admin/services/{service_id}/schedules", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_cross_tenant_schedule_access(client: TestClient, admin_token: str, session: Session):
    suffix = uuid.uuid4().hex[:8]
    other_org = Organization(name=f"Other Org Sch {suffix}")
    session.add(other_org)
    session.commit()
    session.refresh(other_org)

    route = Route(organization_id=other_org.id, route_code="RT_OTHER", route_name="Other", geometry="SRID=4326;LINESTRING(0 0, 1 1)")
    session.add(route)
    session.commit()
    session.refresh(route)
    
    other_service = Service(organization_id=other_org.id, route_id=route.id, service_code="SVC_OTHER", service_name="Other")
    session.add(other_service)
    session.commit()
    session.refresh(other_service)
    
    resp = client.get(f"/api/admin/services/{other_service.id}/schedules", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404
