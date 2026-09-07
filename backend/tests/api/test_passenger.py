import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import ORG_ID, VEH_IDS, seed_dev_data, TRIP_PLANNED_ID, SVC_AC4B_ID
from app.main import app
from app.models.state import BusCurrentState
from app.models.trip import Trip

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        session.execute(text("DELETE FROM bus_current_state"))
        session.commit()
        seed_dev_data(session)


def test_list_organizations():
    """Test retrieving organizations list."""
    response = client.get("/api/passenger/organizations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    # verify org wbtc is in list
    assert any(org["id"] == str(ORG_ID) for org in data)
    assert all(org["name"] for org in data)


def test_list_stops_scoped_to_organization():
    """Test retrieving stops, ensuring org scoping and search."""
    # List all stops for WBTC
    response = client.get(f"/api/passenger/stops?organization_id={ORG_ID}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(stop["organization_id"] == str(ORG_ID) for stop in data)

    # Test search filter
    response_search = client.get(f"/api/passenger/stops?organization_id={ORG_ID}&search=Airport")
    assert response_search.status_code == 200
    search_data = response_search.json()
    assert len(search_data) > 0
    assert "Airport" in search_data[0]["name"]


def test_list_services_scoped_to_organization():
    """Test retrieving services, ensuring org scoping."""
    response = client.get(f"/api/passenger/services?organization_id={ORG_ID}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(srv["organization_id"] == str(ORG_ID) for srv in data)
    assert any(srv["service_code"] == "AC4B" for srv in data)


def test_get_service_details():
    """Test fetching detailed service schedules and stops."""
    response = client.get(f"/api/passenger/services/{SVC_AC4B_ID}?organization_id={ORG_ID}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(SVC_AC4B_ID)
    assert data["service_code"] == "AC4B"
    assert "stops" in data
    assert "schedules" in data
    assert len(data["stops"]) > 0
    # Check stop ordering
    stops = data["stops"]
    assert all(
        stops[i]["sequence_number"] <= stops[i + 1]["sequence_number"]
        for i in range(len(stops) - 1)
    )


def test_get_vehicle_state_with_live_eta():
    """Test that a vehicle with LIVE ETA returns the exact eta_seconds."""
    vehicle_id = VEH_IDS["PNB005234"]
    with Session(engine) as session:
        # Seed a live state with ETA
        state = BusCurrentState(
            vehicle_id=vehicle_id,
            state="LIVE",
            eta_seconds=120,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(state)
        session.commit()

    response = client.get(f"/api/passenger/vehicles/{vehicle_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["eta_seconds"] == 120
    assert data["eta_status"] == "LIVE"


def test_get_vehicle_state_with_unavailable_eta():
    """Test that an UNAVAILABLE ETA status coerces eta_seconds to null."""
    vehicle_id = VEH_IDS["PNB005234"]
    with Session(engine) as session:
        # Seed a live state with ETA
        state = BusCurrentState(
            vehicle_id=vehicle_id,
            state="LIVE",
            eta_seconds=0,
            eta_status="UNAVAILABLE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(state)
        session.commit()

    response = client.get(f"/api/passenger/vehicles/{vehicle_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["eta_seconds"] is None
    assert data["eta_status"] == "UNAVAILABLE"
