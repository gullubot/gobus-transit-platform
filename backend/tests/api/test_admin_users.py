import pytest
import uuid
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.main import app
from app.db.database import engine
from app.models.enums import UserRole
from app.models.user import OperatorProfile, User
from app.models.organization import Organization

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def session():
    with Session(engine) as s:
        yield s

@pytest.fixture
def organization(session: Session):
    org = Organization(name=f"Org_{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def other_organization(session: Session):
    org = Organization(name=f"Org_Other_{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def fleet_admin_user(session: Session, organization: Organization):
    from app.core.security import get_password_hash
    email = f"fleet_{uuid.uuid4().hex[:8]}@example.com"
    admin = User(
        organization_id=organization.id,
        name="Fleet Admin",
        email=email,
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin

@pytest.fixture
def fleet_admin_token(client: TestClient, fleet_admin_user: User):
    response = client.post(
        "/api/admin/login",
        json={"email": fleet_admin_user.email, "password": "password"},
    )
    return response.json()["access_token"]

@pytest.fixture
def depot_admin_user(session: Session, organization: Organization):
    from app.core.security import get_password_hash
    email = f"depot_{uuid.uuid4().hex[:8]}@example.com"
    admin = User(
        organization_id=organization.id,
        name="Depot Admin",
        email=email,
        password_hash=get_password_hash("password"),
        role=UserRole.DEPOT_ADMIN,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin

@pytest.fixture
def depot_admin_token(client: TestClient, depot_admin_user: User):
    response = client.post(
        "/api/admin/login",
        json={"email": depot_admin_user.email, "password": "password"},
    )
    return response.json()["access_token"]


def test_fleet_admin_can_create_driver(client, session, fleet_admin_token, organization):
    response = client.post(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {fleet_admin_token}"},
        json={
            "name": "New Driver",
            "phone": "+1234567890",
            "password": "securepassword",
            "role": UserRole.DRIVER.value,
            "operator_profile": {
                "employee_code": "EMP-001",
                "operator_type": "CITY_BUS",
                "verification_status": "PENDING"
            }
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "New Driver"
    assert data["role"] == UserRole.DRIVER.value
    assert data["operator_profile"]["employee_code"] == "EMP-001"

    db_user = session.query(User).filter(User.id == data["id"]).first()
    assert db_user.organization_id == organization.id
    assert db_user.operator_profile.employee_code == "EMP-001"
    assert db_user.password_hash is not None

def test_depot_admin_cannot_create_fleet_admin(client, depot_admin_token):
    response = client.post(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {depot_admin_token}"},
        json={
            "name": "Another Fleet Admin",
            "email": "newfleet@example.com",
            "password": "securepassword",
            "role": UserRole.FLEET_ADMIN.value,
        }
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Depot Admin cannot manage Fleet Admin roles" in response.json()["detail"]

def test_admin_cannot_create_passenger(client, fleet_admin_token):
    response = client.post(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {fleet_admin_token}"},
        json={
            "name": "Sneaky Passenger",
            "phone": "+99999999",
            "password": "securepassword",
            "role": "PASSENGER",
        }
    )
    assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

def test_admin_cannot_access_other_org_user(client, fleet_admin_token, other_organization, session):
    other_user = User(
        organization_id=other_organization.id,
        name="Other Org User",
        email="other@example.com",
        password_hash="hash",
        role=UserRole.FLEET_ADMIN,
        status="ACTIVE"
    )
    session.add(other_user)
    session.commit()

    response = client.get(
        f"/api/admin/users/{other_user.id}",
        headers={"Authorization": f"Bearer {fleet_admin_token}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_update_user_password(client, fleet_admin_token, session, organization):
    user = User(
        organization_id=organization.id,
        name="Dummy Driver",
        password_hash="oldhash",
        role=UserRole.DRIVER,
        status="ACTIVE"
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    response = client.put(
        f"/api/admin/users/{user.id}/password",
        headers={"Authorization": f"Bearer {fleet_admin_token}"},
        json={
            "password": "new_secure_password"
        }
    )
    assert response.status_code == status.HTTP_200_OK

    session.refresh(user)
    assert user.password_hash != "oldhash"
    assert user.password_hash != "new_secure_password"

def test_deactivate_user(client, fleet_admin_token, session, organization):
    user = User(
        organization_id=organization.id,
        name="Dummy User",
        password_hash="hash",
        role=UserRole.DRIVER,
        status="ACTIVE"
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    response = client.put(
        f"/api/admin/users/{user.id}/status",
        headers={"Authorization": f"Bearer {fleet_admin_token}"},
        json={
            "status": "INACTIVE"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "INACTIVE"

    session.refresh(user)
    assert user.status == "INACTIVE"

def test_cannot_deactivate_self(client, fleet_admin_token, fleet_admin_user):
    response = client.put(
        f"/api/admin/users/{fleet_admin_user.id}/status",
        headers={"Authorization": f"Bearer {fleet_admin_token}"},
        json={
            "status": "INACTIVE"
        }
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Cannot deactivate your own account" in response.json()["detail"]
