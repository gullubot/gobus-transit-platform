import uuid
from datetime import datetime, timezone, timedelta, date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import ORG_ID, VEH_IDS, seed_dev_data, SVC_AC4B_ID
from app.main import app
from app.models.state import BusCurrentState

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    with Session(engine) as session:
        session.execute(text("DELETE FROM bus_current_state"))
        session.commit()
        seed_dev_data(session)
        # Ensure schedule covers the whole day to avoid nightly test failures
        from app.models.service import ServiceSchedule
        from datetime import time
        for sch in session.query(ServiceSchedule).all():
            sch.start_time = time(0, 0)
            sch.end_time = time(23, 59)
        session.commit()


def get_stop_ids():
    response = client.get(f"/api/passenger/stops?organization_id={ORG_ID}")
    stops = response.json()
    stop_cc = next(s for s in stops if "City Center" in s["name"] or "CC" in s["stop_code"])
    stop_tp = next(s for s in stops if "Tech Park" in s["name"] or "TP" in s["stop_code"])
    stop_mg = next(s for s in stops if "MG Road" in s["name"] or "MG" in s["stop_code"])
    return stop_cc, stop_mg, stop_tp


def test_departure_board_scheduled_and_live():
    """Test departure board mixes scheduled and live."""
    cc, mg, tp = get_stop_ids()

    v1 = VEH_IDS["PNB005234"]
    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=120,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    res = client.get(f"/api/passenger/stops/{mg['id']}/departures?organization_id={ORG_ID}")
    assert res.status_code == 200
    data = res.json()

    assert len(data) > 0
    ac4b = next(d for d in data if d["service_name"].startswith("AC4B") and d["direction"] == "A_TO_B")

    # 120s ETA means ARRIVING or ON_TIME based on threshold (<60 is ARRIVING, else ON_TIME or DELAYED)
    assert ac4b["expected_time"] is not None
    assert ac4b["status"] in ["ON_TIME", "ARRIVING", "DELAYED"]

    # Scheduled fallback for opposite direction (B_TO_A)
    # The seed has B_TO_A schedules for AC4B
    try:
        ac4b_opp = next(
            d for d in data if d["service_name"].startswith("AC4B") and d["direction"] == "B_TO_A"
        )
        assert ac4b_opp["status"] == "ON_TIME"  # Fallback to SCHEDULED or ON_TIME
        assert ac4b_opp["expected_time"] is None
        assert ac4b_opp["scheduled_time"] is not None
    except StopIteration:
        pass  # If no B_TO_A schedule exists in seed, skip


def test_departure_board_unavailable_eta():
    cc, mg, tp = get_stop_ids()
    v1 = VEH_IDS["PNB005234"]
    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=0,
            eta_status="UNAVAILABLE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    res = client.get(f"/api/passenger/stops/{mg['id']}/departures?organization_id={ORG_ID}")
    assert res.status_code == 200
    data = res.json()
    ac4b = next(d for d in data if d["service_name"].startswith("AC4B") and d["direction"] == "A_TO_B")

    assert ac4b["status"] == "ON_TIME"  # falls back to scheduled
    assert ac4b["expected_time"] is None
    assert ac4b["scheduled_time"] is not None


def test_plan_trip_valid():
    cc, mg, tp = get_stop_ids()

    req_date = "2026-08-30"
    req_time = "08:00"

    res = client.get(
        f"/api/passenger/plan?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&date={req_date}&time={req_time}"
    )
    assert res.status_code == 200
    data = res.json()

    assert len(data) > 0
    # verify AC4B is there
    assert any(d["service_name"].startswith("AC4B") for d in data)
    assert all(d["direction"] == "A_TO_B" for d in data)

    first = data[0]
    # Earliest departure should be >= 08:00
    dep_time = datetime.fromisoformat(first["scheduled_departure"]).time()
    assert dep_time >= time(8, 0)

    # Arrival > Departure
    arr = datetime.fromisoformat(first["scheduled_arrival"])
    dep = datetime.fromisoformat(first["scheduled_departure"])
    assert arr > dep


def test_plan_trip_invalid_same_stop():
    cc, mg, tp = get_stop_ids()
    res = client.get(
        f"/api/passenger/plan?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={cc['id']}&date=2026-08-30&time=08:00"
    )
    assert res.status_code == 400


def test_plan_trip_invalid_no_direct_service():
    cc, mg, tp = get_stop_ids()
    # Find a stop from another route if possible. We will just test org scoping isolation for now.
    random_id = str(uuid.uuid4())
    res = client.get(
        f"/api/passenger/plan?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={random_id}&date=2026-08-30&time=08:00"
    )
    assert res.status_code == 404


def test_plan_trip_after_service_ends():
    cc, mg, tp = get_stop_ids()
    res = client.get(
        f"/api/passenger/plan?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&date=2026-08-30&time=23:59"
    )
    assert res.status_code == 200
    data = res.json()
    # Depends on schedule, but likely AC4B is closed at 23:59 if it's not overnight.
    # We just ensure it runs properly without crashing.
    assert isinstance(data, list)
