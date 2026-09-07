import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole
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
def org_a(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org A Ins {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_ins_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Ins A",
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


def test_get_crowding_insights(client: TestClient, admin_token: str):
    response = client.get("/api/admin/insights/crowding", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "insights" in data
    assert isinstance(data["insights"], list)


def test_get_performance_insights(client: TestClient, admin_token: str):
    response = client.get("/api/admin/insights/performance", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "insights" in data


def test_get_fleet_insights(client: TestClient, admin_token: str):
    response = client.get("/api/admin/insights/fleet", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "insights" in data


def test_get_summary_insights(client: TestClient, admin_token: str):
    response = client.get("/api/admin/insights/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "insights" in data
