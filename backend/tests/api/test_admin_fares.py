import uuid
from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.models.enums import UserRole, RouteStatus, ServiceStatus
from app.models.route import Route
from app.models.service import Service
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
    org = Organization(name=f"Org A Fare {suffix}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org

@pytest.fixture
def admin_token(client: TestClient, session: Session, org_a: Organization):
    from app.core.security import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_fare_a_{suffix}@demo.com"
    admin = User(
        organization_id=org_a.id,
        name="Admin Fare A",
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
def auth_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}


def test_admin_create_fare_config(
    client: TestClient,
    auth_headers: dict,
):
    payload = {
        "name": "Standard Fare 2026",
        "currency": "INR",
        "effective_from": date.today().isoformat(),
        "slabs": [
            {"min_distance_km": 0.0, "max_distance_km": 2.0, "fare_amount": 10},
            {"min_distance_km": 2.0, "max_distance_km": 5.0, "fare_amount": 15},
            {"min_distance_km": 5.0, "max_distance_km": None, "fare_amount": 20},
        ]
    }
    
    response = client.post(
        "/api/admin/fares/",
        json=payload,
        headers=auth_headers
    )
    
    if response.status_code != 200:
        print(f"FAILED: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Standard Fare 2026"
    assert len(data["slabs"]) == 3
    assert float(data["slabs"][0]["min_distance_km"]) == 0.0
    assert float(data["slabs"][0]["max_distance_km"]) == 2.0


def test_admin_create_fare_config_invalid_slabs(
    client: TestClient,
    auth_headers: dict,
):
    payload = {
        "name": "Invalid Fare",
        "currency": "INR",
        "effective_from": date.today().isoformat(),
        "slabs": [
            {"min_distance_km": 1.0, "max_distance_km": 2.0, "fare_amount": 10},
        ]
    }
    
    response = client.post(
        "/api/admin/fares/",
        json=payload,
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "first fare slab must start at 0.0" in response.json()["detail"]


def test_admin_activate_fare_config(
    client: TestClient,
    auth_headers: dict,
):
    # Create config 1
    payload1 = {
        "name": "Fare 1",
        "currency": "INR",
        "effective_from": date.today().isoformat(),
        "slabs": [{"min_distance_km": 0.0, "max_distance_km": None, "fare_amount": 10}]
    }
    r1 = client.post("/api/admin/fares/", json=payload1, headers=auth_headers)
    config1_id = r1.json()["id"]

    # Create config 2
    payload2 = {
        "name": "Fare 2",
        "currency": "INR",
        "effective_from": date.today().isoformat(),
        "slabs": [{"min_distance_km": 0.0, "max_distance_km": None, "fare_amount": 15}]
    }
    r2 = client.post("/api/admin/fares/", json=payload2, headers=auth_headers)
    config2_id = r2.json()["id"]

    # Activate config 1
    r_act1 = client.post(f"/api/admin/fares/{config1_id}/activate", headers=auth_headers)
    assert r_act1.status_code == 200
    assert r_act1.json()["is_active"] is True

    # Activate config 2
    r_act2 = client.post(f"/api/admin/fares/{config2_id}/activate", headers=auth_headers)
    assert r_act2.status_code == 200
    assert r_act2.json()["is_active"] is True

    # Verify config 1 is STILL active (multiple active configs allowed)
    r_get1 = client.get(f"/api/admin/fares/{config1_id}", headers=auth_headers)
    assert r_get1.json()["is_active"] is True


def test_admin_get_fares_list_with_service_enrichment(
    client: TestClient,
    session: Session,
    org_a: Organization,
    auth_headers: dict,
):
    """Fare list endpoint enriches configurations with attached service info."""
    # Create route and service
    route = Route(
        organization_id=org_a.id,
        route_code="R-FARE-1",
        route_name="Route for Fare Test",
        status=RouteStatus.ACTIVE,
    )
    session.add(route)
    session.commit()
    session.refresh(route)

    # Create fare config
    payload = {
        "name": "Fare - SVC-99",
        "currency": "INR",
        "effective_from": date.today().isoformat(),
        "slabs": [
            {"min_distance_km": 0.0, "max_distance_km": 5.0, "fare_amount": 10},
            {"min_distance_km": 5.0, "max_distance_km": None, "fare_amount": 20},
        ],
    }
    r_create = client.post("/api/admin/fares/", json=payload, headers=auth_headers)
    assert r_create.status_code == 200
    fare_id = r_create.json()["id"]

    # Attach service to this fare config
    service = Service(
        organization_id=org_a.id,
        route_id=route.id,
        service_code="SVC-99",
        service_name="Express 99",
        fare_configuration_id=uuid.UUID(fare_id),
        status=ServiceStatus.ACTIVE,
    )
    session.add(service)
    session.commit()

    # Get fare list
    r_list = client.get("/api/admin/fares/", headers=auth_headers)
    assert r_list.status_code == 200
    fares = r_list.json()
    matching = [f for f in fares if f["id"] == fare_id]
    assert len(matching) == 1
    assert matching[0]["service_code"] == "SVC-99"
    assert matching[0]["service_name"] == "Express 99"
    assert matching[0]["service_id"] == str(service.id)


def test_admin_get_fare_detail_loads_and_slab_ordering(
    client: TestClient,
    auth_headers: dict,
):
    """Fare detail loads and slabs are ordered by min_distance_km with string decimal representation."""
    payload = {
        "name": "Multi Slab Fare",
        "currency": "INR",
        "effective_from": date.today().isoformat(),
        "slabs": [
            {"min_distance_km": 0.0, "max_distance_km": 3.0, "fare_amount": 10},
            {"min_distance_km": 3.0, "max_distance_km": 7.5, "fare_amount": 15},
            {"min_distance_km": 7.5, "max_distance_km": 12.0, "fare_amount": 20},
            {"min_distance_km": 12.0, "max_distance_km": None, "fare_amount": 25},
        ],
    }
    r_create = client.post("/api/admin/fares/", json=payload, headers=auth_headers)
    assert r_create.status_code == 200
    fare_id = r_create.json()["id"]

    # Detail request
    r_detail = client.get(f"/api/admin/fares/{fare_id}", headers=auth_headers)
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert detail["name"] == "Multi Slab Fare"
    assert len(detail["slabs"]) == 4

    slabs = detail["slabs"]
    # Check ordering and numeric values
    assert float(slabs[0]["min_distance_km"]) == 0.0
    assert float(slabs[0]["max_distance_km"]) == 3.0
    assert float(slabs[0]["fare_amount"]) == 10.0

    assert float(slabs[1]["min_distance_km"]) == 3.0
    assert float(slabs[1]["max_distance_km"]) == 7.5
    assert float(slabs[1]["fare_amount"]) == 15.0

    assert float(slabs[2]["min_distance_km"]) == 7.5
    assert float(slabs[2]["max_distance_km"]) == 12.0
    assert float(slabs[2]["fare_amount"]) == 20.0

    assert float(slabs[3]["min_distance_km"]) == 12.0
    assert slabs[3]["max_distance_km"] is None
    assert float(slabs[3]["fare_amount"]) == 25.0


def test_admin_update_existing_active_fare_config_and_slabs(
    client: TestClient,
    auth_headers: dict,
):
    """
    Updating an existing active fare configuration updates its slabs and metadata
    without creating duplicate configurations or failing if active.
    """
    payload = {
        "name": "Initial Fare",
        "currency": "INR",
        "effective_from": "2026-01-01",
        "slabs": [
            {"min_distance_km": 0.0, "max_distance_km": 5.0, "fare_amount": 10},
            {"min_distance_km": 5.0, "max_distance_km": None, "fare_amount": 20},
        ],
    }
    r_create = client.post("/api/admin/fares/", json=payload, headers=auth_headers)
    fare_id = r_create.json()["id"]

    # Activate it
    client.post(f"/api/admin/fares/{fare_id}/activate", headers=auth_headers)

    # Update the existing active fare configuration
    update_payload = {
        "name": "Updated Active Fare",
        "effective_from": "2026-02-01",
        "slabs": [
            {"min_distance_km": 0.0, "max_distance_km": 4.0, "fare_amount": 12},
            {"min_distance_km": 4.0, "max_distance_km": 8.0, "fare_amount": 18},
            {"min_distance_km": 8.0, "max_distance_km": None, "fare_amount": 25},
        ],
    }
    r_update = client.put(f"/api/admin/fares/{fare_id}", json=update_payload, headers=auth_headers)
    assert r_update.status_code == 200
    updated = r_update.json()

    assert updated["id"] == fare_id  # Same identity
    assert updated["name"] == "Updated Active Fare"
    assert updated["effective_from"] == "2026-02-01"
    assert updated["is_active"] is True  # Retains active state
    assert len(updated["slabs"]) == 3
    assert float(updated["slabs"][0]["max_distance_km"]) == 4.0
    assert float(updated["slabs"][0]["fare_amount"]) == 12.0
    assert float(updated["slabs"][1]["fare_amount"]) == 18.0
    assert float(updated["slabs"][2]["fare_amount"]) == 25.0


def test_admin_update_fare_config_invalid_slabs_rejected(
    client: TestClient,
    auth_headers: dict,
):
    """Invalid slab definitions (gaps, overlaps, non-zero start) are rejected with HTTP 400."""
    payload = {
        "name": "Base Fare",
        "currency": "INR",
        "effective_from": "2026-01-01",
        "slabs": [
            {"min_distance_km": 0.0, "max_distance_km": None, "fare_amount": 10},
        ],
    }
    r_create = client.post("/api/admin/fares/", json=payload, headers=auth_headers)
    fare_id = r_create.json()["id"]

    # Invalid: gap between 3.0 and 5.0
    bad_gap_payload = {
        "slabs": [
            {"min_distance_km": 0.0, "max_distance_km": 3.0, "fare_amount": 10},
            {"min_distance_km": 5.0, "max_distance_km": None, "fare_amount": 20},
        ],
    }
    r_gap = client.put(f"/api/admin/fares/{fare_id}", json=bad_gap_payload, headers=auth_headers)
    assert r_gap.status_code == 400
    assert "Slab gap or overlap detected" in r_gap.json()["detail"]

    # Invalid: non-zero start
    bad_start_payload = {
        "slabs": [
            {"min_distance_km": 1.0, "max_distance_km": None, "fare_amount": 10},
        ],
    }
    r_start = client.put(f"/api/admin/fares/{fare_id}", json=bad_start_payload, headers=auth_headers)
    assert r_start.status_code == 400
    assert "first fare slab must start at 0.0" in r_start.json()["detail"]


def test_admin_fare_tenant_isolation(
    client: TestClient,
    session: Session,
    auth_headers: dict,
):
    """Admins cannot view or modify fare configurations of other organizations."""
    from app.core.security import get_password_hash
    org_other = Organization(name=f"Other Org Fares {uuid.uuid4().hex[:8]}")
    session.add(org_other)
    session.commit()
    session.refresh(org_other)

    admin_other = User(
        organization_id=org_other.id,
        name="Other Admin",
        email=f"other_{uuid.uuid4().hex[:6]}@demo.com",
        password_hash=get_password_hash("password"),
        role=UserRole.FLEET_ADMIN,
    )
    session.add(admin_other)
    session.commit()

    r_login = client.post("/api/admin/login", json={"email": admin_other.email, "password": "password"})
    other_headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    # Other org creates a fare
    payload = {
        "name": "Other Org Secret Fare",
        "currency": "INR",
        "effective_from": "2026-01-01",
        "slabs": [{"min_distance_km": 0.0, "max_distance_km": None, "fare_amount": 50}],
    }
    r_other_create = client.post("/api/admin/fares/", json=payload, headers=other_headers)
    other_fare_id = r_other_create.json()["id"]

    # Org A tries to GET other org's fare -> 404
    r_get = client.get(f"/api/admin/fares/{other_fare_id}", headers=auth_headers)
    assert r_get.status_code == 404

    # Org A tries to PUT other org's fare -> 404
    r_put = client.put(f"/api/admin/fares/{other_fare_id}", json={"name": "Hacked"}, headers=auth_headers)
    assert r_put.status_code == 404


