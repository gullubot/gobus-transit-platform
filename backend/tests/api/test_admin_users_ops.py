import uuid
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.main import app
from app.db.database import engine
from app.models.enums import UserRole
from app.models.user import OperatorProfile, User
from app.models.organization import Organization
from app.core.security import get_password_hash


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def session():
    with Session(engine) as s:
        yield s


@pytest.fixture
def org_a(session: Session):
    org = Organization(name=f"Org_A_{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def org_b(session: Session):
    org = Organization(name=f"Org_B_{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture
def fleet_admin_a(session: Session, org_a: Organization):
    email = f"fleet_a_{uuid.uuid4().hex[:8]}@example.com"
    admin = User(
        organization_id=org_a.id,
        name="Fleet Admin Alpha",
        email=email,
        phone="+919876543210",
        password_hash=get_password_hash("securepass123"),
        role=UserRole.FLEET_ADMIN,
        status="ACTIVE",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def token_a(client: TestClient, fleet_admin_a: User):
    response = client.post(
        "/api/admin/login",
        json={"email": fleet_admin_a.email, "password": "securepass123"},
    )
    return response.json()["access_token"]


@pytest.fixture
def fleet_admin_b(session: Session, org_b: Organization):
    email = f"fleet_b_{uuid.uuid4().hex[:8]}@example.com"
    admin = User(
        organization_id=org_b.id,
        name="Fleet Admin Bravo",
        email=email,
        password_hash=get_password_hash("securepass123"),
        role=UserRole.FLEET_ADMIN,
        status="ACTIVE",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def token_b(client: TestClient, fleet_admin_b: User):
    response = client.post(
        "/api/admin/login",
        json={"email": fleet_admin_b.email, "password": "securepass123"},
    )
    return response.json()["access_token"]


@pytest.fixture
def depot_admin_a(session: Session, org_a: Organization):
    email = f"depot_a_{uuid.uuid4().hex[:8]}@example.com"
    admin = User(
        organization_id=org_a.id,
        name="Depot Admin Alpha",
        email=email,
        password_hash=get_password_hash("securepass123"),
        role=UserRole.DEPOT_ADMIN,
        status="ACTIVE",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def token_depot_a(client: TestClient, depot_admin_a: User):
    response = client.post(
        "/api/admin/login",
        json={"email": depot_admin_a.email, "password": "securepass123"},
    )
    return response.json()["access_token"]


# 1. Users list loads and returns users in org
def test_users_list_loads(client: TestClient, token_a: str, fleet_admin_a: User):
    response = client.get(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    user_ids = [u["id"] for u in data]
    assert str(fleet_admin_a.id) in user_ids


# 2 & 3. Role filters work for all supported roles
def test_role_filters_and_operator_profiles(client: TestClient, session: Session, token_a: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    # Create driver
    driver = User(
        organization_id=org_a.id,
        name=f"Driver {suffix}",
        email=f"driver_{suffix}@test.com",
        password_hash=get_password_hash("pass"),
        role=UserRole.DRIVER,
        status="ACTIVE",
    )
    session.add(driver)
    session.flush()
    session.add(OperatorProfile(user_id=driver.id, employee_code=f"DR_{suffix}", operator_type="CITY_BUS"))

    # Create conductor
    conductor = User(
        organization_id=org_a.id,
        name=f"Conductor {suffix}",
        email=f"cond_{suffix}@test.com",
        password_hash=get_password_hash("pass"),
        role=UserRole.CONDUCTOR,
        status="INACTIVE",
    )
    session.add(conductor)
    session.flush()
    session.add(OperatorProfile(user_id=conductor.id, employee_code=f"CD_{suffix}", operator_type="EXPRESS"))

    session.commit()

    # Filter by DRIVER
    res_driver = client.get(
        f"/api/admin/users/?role={UserRole.DRIVER.value}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_driver.status_code == status.HTTP_200_OK
    drivers = res_driver.json()
    assert all(u["role"] == UserRole.DRIVER.value for u in drivers)
    found_driver = next(u for u in drivers if u["id"] == str(driver.id))
    assert found_driver["operator_profile"]["employee_code"] == f"DR_{suffix}"

    # Filter by CONDUCTOR
    res_cond = client.get(
        f"/api/admin/users/?role={UserRole.CONDUCTOR.value}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_cond.status_code == status.HTTP_200_OK
    conductors = res_cond.json()
    assert all(u["role"] == UserRole.CONDUCTOR.value for u in conductors)


# 4. Status filter works for actual supported statuses (ACTIVE, INACTIVE, SUSPENDED)
def test_status_filters(client: TestClient, session: Session, token_a: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    user_susp = User(
        organization_id=org_a.id,
        name=f"Suspended User {suffix}",
        email=f"susp_{suffix}@test.com",
        password_hash=get_password_hash("pass"),
        role=UserRole.DEPOT_ADMIN,
        status="SUSPENDED",
    )
    session.add(user_susp)
    session.commit()

    res = client.get(
        "/api/admin/users/?user_status=SUSPENDED",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == status.HTTP_200_OK
    suspended_users = res.json()
    assert any(u["id"] == str(user_susp.id) for u in suspended_users)
    assert all(u["status"] == "SUSPENDED" for u in suspended_users)


# 5, 8, 9. Contact fields handle missing values and long email/phone gracefully
def test_contact_fields_and_long_values(client: TestClient, session: Session, token_a: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    long_email = f"extremely.long.enterprise.transporter.email.address.{suffix}@subdomain.kolkatatransit.local"
    user_long = User(
        organization_id=org_a.id,
        name="Long Contact User",
        email=long_email,
        phone="+91-33-2222-3333",
        password_hash=get_password_hash("pass"),
        role=UserRole.DEPOT_ADMIN,
        status="ACTIVE",
    )
    # User with missing email and phone
    user_sparse = User(
        organization_id=org_a.id,
        name="Sparse Contact User",
        email=None,
        phone=None,
        password_hash=get_password_hash("pass"),
        role=UserRole.DEPOT_ADMIN,
        status="ACTIVE",
    )
    session.add_all([user_long, user_sparse])
    session.commit()

    res = client.get(
        f"/api/admin/users/{user_long.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["email"] == long_email
    assert data["phone"] == "+91-33-2222-3333"

    res_sparse = client.get(
        f"/api/admin/users/{user_sparse.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_sparse.status_code == status.HTTP_200_OK
    data_sparse = res_sparse.json()
    assert data_sparse["email"] is None
    assert data_sparse["phone"] is None


# 10, 11. Add User validation matches backend
def test_add_driver_requires_operator_profile(client: TestClient, token_a: str):
    # Attempt to create driver without operator_profile
    res = client.post(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Invalid Driver",
            "phone": "+919000000001",
            "password": "validpassword123",
            "role": UserRole.DRIVER.value,
        },
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Operator profile is required" in res.json()["detail"]


# 15. Duplicate email and duplicate employee code rejection
def test_duplicate_email_and_employee_code(client: TestClient, session: Session, token_a: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    existing_email = f"duplicate_{suffix}@test.com"
    existing_code = f"CODE_{suffix}"

    # First user
    res1 = client.post(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Original Operator",
            "email": existing_email,
            "password": "validpassword123",
            "role": UserRole.DRIVER.value,
            "operator_profile": {
                "employee_code": existing_code,
                "operator_type": "CITY_BUS",
            },
        },
    )
    assert res1.status_code == status.HTTP_201_CREATED

    # Duplicate email
    res_dup_email = client.post(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Another Operator",
            "email": existing_email,
            "password": "validpassword123",
            "role": UserRole.DEPOT_ADMIN.value,
        },
    )
    assert res_dup_email.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in res_dup_email.json()["detail"]

    # Duplicate employee code
    res_dup_code = client.post(
        "/api/admin/users/",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Conductor With Same Code",
            "email": f"other_{suffix}@test.com",
            "password": "validpassword123",
            "role": UserRole.CONDUCTOR.value,
            "operator_profile": {
                "employee_code": existing_code,
                "operator_type": "CITY_BUS",
            },
        },
    )
    assert res_dup_code.status_code == status.HTTP_400_BAD_REQUEST
    assert "Employee code already in use" in res_dup_code.json()["detail"]


# 12, 13, 14. Edit User loads and saves metadata
def test_edit_user_metadata(client: TestClient, session: Session, token_a: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    user = User(
        organization_id=org_a.id,
        name=f"Pre-Edit User {suffix}",
        email=f"pre_{suffix}@test.com",
        phone="+919000000002",
        password_hash=get_password_hash("pass"),
        role=UserRole.DRIVER,
        status="ACTIVE",
    )
    session.add(user)
    session.flush()
    session.add(OperatorProfile(user_id=user.id, employee_code=f"PRE_{suffix}", operator_type="CITY_BUS"))
    session.commit()

    # Update metadata
    res = client.put(
        f"/api/admin/users/{user.id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": f"Post-Edit User {suffix}",
            "phone": "+919999999999",
            "employee_code": f"POST_{suffix}",
            "operator_type": "EXPRESS",
        },
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["name"] == f"Post-Edit User {suffix}"
    assert data["phone"] == "+919999999999"
    assert data["operator_profile"]["employee_code"] == f"POST_{suffix}"
    assert data["operator_profile"]["operator_type"] == "EXPRESS"


# 14 & 21. Self role change rejection
def test_cannot_change_own_role(client: TestClient, token_a: str, fleet_admin_a: User):
    res = client.put(
        f"/api/admin/users/{fleet_admin_a.id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "role": UserRole.DEPOT_ADMIN.value,
        },
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "Cannot change your own role" in res.json()["detail"]


# 16, 19, 20. Credential action updates password, and password hashes / raw passwords NEVER returned
def test_password_update_and_security(client: TestClient, session: Session, token_a: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    user = User(
        organization_id=org_a.id,
        name=f"Security User {suffix}",
        email=f"sec_{suffix}@test.com",
        password_hash=get_password_hash("initial_pass"),
        role=UserRole.DEPOT_ADMIN,
        status="ACTIVE",
    )
    session.add(user)
    session.commit()

    old_hash = user.password_hash

    res = client.put(
        f"/api/admin/users/{user.id}/password",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"password": "new_secret_password_123"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    # Verify response schema does NOT leak password_hash or raw password
    assert "password_hash" not in data
    assert "password" not in data

    # Verify password hash changed in DB
    session.refresh(user)
    assert user.password_hash != old_hash
    assert user.password_hash != "new_secret_password_123"


# 17. Activate, Deactivate, and Suspend user
def test_activate_deactivate_suspend(client: TestClient, session: Session, token_a: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    user = User(
        organization_id=org_a.id,
        name=f"Status User {suffix}",
        email=f"status_{suffix}@test.com",
        password_hash=get_password_hash("pass"),
        role=UserRole.DEPOT_ADMIN,
        status="ACTIVE",
    )
    session.add(user)
    session.commit()

    # Deactivate
    res_deact = client.put(
        f"/api/admin/users/{user.id}/status",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"status": "INACTIVE"},
    )
    assert res_deact.status_code == status.HTTP_200_OK
    assert res_deact.json()["status"] == "INACTIVE"

    # Suspend
    res_susp = client.put(
        f"/api/admin/users/{user.id}/status",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"status": "SUSPENDED"},
    )
    assert res_susp.status_code == status.HTTP_200_OK
    assert res_susp.json()["status"] == "SUSPENDED"

    # Reactivate
    res_act = client.put(
        f"/api/admin/users/{user.id}/status",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"status": "ACTIVE"},
    )
    assert res_act.status_code == status.HTTP_200_OK
    assert res_act.json()["status"] == "ACTIVE"


# 21. Self status change rejection
def test_cannot_deactivate_or_suspend_self(client: TestClient, token_a: str, fleet_admin_a: User):
    res = client.put(
        f"/api/admin/users/{fleet_admin_a.id}/status",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"status": "INACTIVE"},
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "Cannot deactivate your own account" in res.json()["detail"]


# 18. Strict tenant isolation: Admin B cannot access, edit, change password, or status of Admin A's user
def test_strict_tenant_isolation(client: TestClient, session: Session, token_b: str, org_a: Organization):
    suffix = uuid.uuid4().hex[:6]
    user_a = User(
        organization_id=org_a.id,
        name=f"Org A Private User {suffix}",
        email=f"priv_a_{suffix}@test.com",
        password_hash=get_password_hash("pass"),
        role=UserRole.DRIVER,
        status="ACTIVE",
    )
    session.add(user_a)
    session.commit()

    # Org B trying to get User A -> 404
    res_get = client.get(
        f"/api/admin/users/{user_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_get.status_code == status.HTTP_404_NOT_FOUND

    # Org B trying to edit User A -> 404
    res_edit = client.put(
        f"/api/admin/users/{user_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"name": "Hacked Name"},
    )
    assert res_edit.status_code == status.HTTP_404_NOT_FOUND

    # Org B trying to change password -> 404
    res_pwd = client.put(
        f"/api/admin/users/{user_a.id}/password",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"password": "hacked_password"},
    )
    assert res_pwd.status_code == status.HTTP_404_NOT_FOUND

    # Org B trying to change status -> 404
    res_status = client.put(
        f"/api/admin/users/{user_a.id}/status",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"status": "INACTIVE"},
    )
    assert res_status.status_code == status.HTTP_404_NOT_FOUND
