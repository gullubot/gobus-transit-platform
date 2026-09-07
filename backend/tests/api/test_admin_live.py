import uuid
from datetime import datetime, timezone
import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, VehicleStatus, Confidence
from app.models.vehicle import Vehicle
from app.models.state import BusCurrentState
from app.db.database import engine
from app.db.seed import seed_dev_data
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        seed_dev_data(session)

@pytest.fixture
def session():
    with Session(engine) as s:
        yield s

@pytest.fixture
def org_a(session: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org A Live {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_a_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_live_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Live A",
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
    org = Organization(name=f"Org B Live {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_b_token(client: TestClient, session: Session, org_b: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_live_b_{suffix}@demo.com"
    admin = User(
        organization_id=org_b.id,
        name="Admin Live B",
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

def test_unauthenticated_rejected(client: TestClient):
    resp = client.get("/api/admin/operations/live")
    assert resp.status_code == 401

def test_passenger_operator_rejected(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import create_access_token
    
    p_token = create_access_token("fake-passenger-id", claims={"role": "PASSENGER"})
    o_token = create_access_token("fake-operator-id", claims={"role": "DRIVER"})
    
    resp = client.get("/api/admin/operations/live", headers={"Authorization": f"Bearer {p_token}"})
    assert resp.status_code in (401, 403)
    
    resp = client.get("/api/admin/operations/live", headers={"Authorization": f"Bearer {o_token}"})
    assert resp.status_code in (401, 403)

def test_empty_fleet_returns_empty_list(client: TestClient, admin_a_token: str):
    resp = client.get("/api/admin/operations/live", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert resp.status_code == 200
    assert resp.json() == []

def test_live_operations_isolation_and_payload(
    client: TestClient, admin_a_token: str, admin_b_token: str,
    session: Session, org_a: Organization, org_b: Organization
):
    # Setup vehicle and state for Org A
    veh_a = Vehicle(
        organization_id=org_a.id, vehicle_number="VA_LIVE",
        vehicle_type="BUS", status=VehicleStatus.ACTIVE
    )
    session.add(veh_a)
    session.commit()
    
    dt_now = datetime.now(timezone.utc)
    state_a = BusCurrentState(
        vehicle_id=veh_a.id,
        latitude=10.0, longitude=20.0,
        speed=15.5,
        state="MOVING",
        confidence=Confidence.HIGH,
        last_observed_at=dt_now
    )
    session.add(state_a)
    session.commit()
    
    # Setup vehicle and state for Org B
    veh_b = Vehicle(
        organization_id=org_b.id, vehicle_number="VB_LIVE",
        vehicle_type="BUS", status=VehicleStatus.ACTIVE
    )
    session.add(veh_b)
    session.commit()
    state_b = BusCurrentState(
        vehicle_id=veh_b.id,
        latitude=30.0, longitude=40.0,
        state="STOPPED",
        confidence=Confidence.MEDIUM,
        last_observed_at=dt_now
    )
    session.add(state_b)
    session.commit()
    
    # Admin A should only see VA_LIVE
    resp_a = client.get("/api/admin/operations/live", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert len(data_a) == 1
    
    item_a = data_a[0]
    assert item_a["vehicle_id"] == str(veh_a.id)
    assert item_a["vehicle_number"] == "VA_LIVE"
    assert item_a["latitude"] == 10.0
    assert item_a["speed"] == 15.5
    assert item_a["state"] == "MOVING"
    assert item_a["confidence"] == "HIGH"
    assert "engine_contexts" not in item_a
    
    # Admin B should only see VB_LIVE
    resp_b = client.get("/api/admin/operations/live", headers={"Authorization": f"Bearer {admin_b_token}"})
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert len(data_b) == 1
    assert data_b[0]["vehicle_id"] == str(veh_b.id)
