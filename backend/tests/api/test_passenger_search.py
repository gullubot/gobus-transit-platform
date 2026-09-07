import uuid
from datetime import datetime, timezone, timedelta

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


def test_service_search_valid_route():
    """Test searching for a valid origin -> destination route."""
    # We need two stop IDs from the seed. Let's just fetch them.
    response = client.get(f"/api/passenger/stops?organization_id={ORG_ID}")
    stops = response.json()

    stop_orig = next(s for s in stops if "City Center" in s["name"] or "CC" in s["stop_code"])
    stop_dest = next(s for s in stops if "Tech Park" in s["name"] or "TP" in s["stop_code"])

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={stop_orig['id']}&destination_id={stop_dest['id']}"
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0
    assert any(srv["service_name"].startswith("AC4B") for srv in data)

    # Check that direction is correct. City Center -> Tech Park is A_TO_B typically.
    ac4b = next(srv for srv in data if srv["service_name"].startswith("AC4B"))
    assert ac4b["direction"] == "A_TO_B"
    assert ac4b["active_buses_count"] == 0
    assert ac4b["nearest_bus"] is None


def test_service_search_invalid_route():
    """Test searching for opposite direction (TP -> CC)"""
    response = client.get(f"/api/passenger/stops?organization_id={ORG_ID}")
    stops = response.json()

    stop_orig = next(s for s in stops if "City Center" in s["name"] or "CC" in s["stop_code"])
    stop_dest = next(s for s in stops if "Tech Park" in s["name"] or "TP" in s["stop_code"])

    # Opposite direction: TP to CC. AC4B only operates A_TO_B? Wait, the seed actually has B_TO_A schedules.
    # The endpoint should return direction B_TO_A.
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={stop_dest['id']}&destination_id={stop_orig['id']}"
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0

    ac4b = next(srv for srv in data if srv["service_name"].startswith("AC4B"))
    assert ac4b["direction"] == "B_TO_A"


def test_service_search_active_bus_ranking_and_crowding():
    response = client.get(f"/api/passenger/stops?organization_id={ORG_ID}")
    stops = response.json()
    stop_orig = next(s for s in stops if "City Center" in s["name"] or "CC" in s["stop_code"])
    stop_dest = next(s for s in stops if "Tech Park" in s["name"] or "TP" in s["stop_code"])

    # Insert two active buses for A_TO_B
    v1 = VEH_IDS["PNB005234"]
    v2 = VEH_IDS["PNB005781"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=300,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        b2 = BusCurrentState(
            vehicle_id=v2,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="DEGRADED",
            eta_seconds=100,  # nearest
            eta_status="DEGRADED",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.add(b2)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={stop_orig['id']}&destination_id={stop_dest['id']}"
    )
    assert res.status_code == 200
    data = res.json()

    ac4b = next(srv for srv in data if srv["service_name"].startswith("AC4B"))
    assert ac4b["active_buses_count"] == 2
    # Nearest should be v2 (100 seconds)
    assert ac4b["nearest_bus"]["vehicle_id"] == str(v2)
    assert ac4b["nearest_bus"]["eta_seconds"] == 100
    assert ac4b["nearest_bus"]["eta_status"] == "DEGRADED"


def test_service_live_bus_filtering():
    """Test active bus API."""
    v1 = VEH_IDS["PNB005234"]
    v2 = VEH_IDS["PNB005781"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=300,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        # b2 is stale (11 mins ago)
        b2 = BusCurrentState(
            vehicle_id=v2,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=100,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc) - timedelta(minutes=11),
            last_received_at=datetime.now(timezone.utc) - timedelta(minutes=11),
        )
        session.add(b1)
        session.add(b2)
        session.commit()

    res = client.get(f"/api/passenger/services/{SVC_AC4B_ID}/live?organization_id={ORG_ID}")
    assert res.status_code == 200
    data = res.json()

    assert len(data) == 1
    assert data[0]["vehicle_id"] == str(v1)
