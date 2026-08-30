import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.database import engine
from app.db.seed import ORG_ID, ROUTE_R1_ID, SVC_AC4B_ID, seed_dev_data
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        session.execute(text("DELETE FROM tracking_events"))
        session.execute(text("DELETE FROM tracking_sessions"))
        session.execute(text("DELETE FROM bus_current_state"))
        session.execute(text("DELETE FROM trip_assignments"))
        session.commit()
        seed_dev_data(session)


def setup_operator_and_session(has_trip=True):
    unique_trip_id = uuid.uuid4()
    unique_vehicle_id = uuid.uuid4()
    unique_user_id = uuid.uuid4()
    unique_org_id = ORG_ID
    emp_code = f"DRV-{uuid.uuid4().hex[:6]}"
    device_id = uuid.uuid4()
    session_id = uuid.uuid4()

    with Session(engine) as session:
        pass_hash = get_password_hash("testpass123")
        session.execute(
            text(
                f"INSERT INTO users (id, organization_id, name, phone, role, "
                f"password_hash, status, created_at, updated_at) "
                f"VALUES ('{unique_user_id}', '{unique_org_id}', 'Iso Driver', "
                f"'{uuid.uuid4().hex[:10]}', 'DRIVER', '{pass_hash}', 'ACTIVE', now(), now())"
            )
        )
        session.execute(
            text(
                f"INSERT INTO operator_profiles (id, user_id, employee_code, "
                f"operator_type, verification_status, created_at, updated_at) "
                f"VALUES ('{uuid.uuid4()}', '{unique_user_id}', '{emp_code}', "
                f"'DRIVER', 'VERIFIED', now(), now())"
            )
        )

        session.execute(
            text(
                f"INSERT INTO devices (id, organization_id, device_name, "
                f"platform, status, created_at, updated_at) "
                f"VALUES ('{device_id}', '{unique_org_id}', 'Iso Device', "
                f"'ANDROID', 'ACTIVE', now(), now())"
            )
        )

        session.execute(
            text(
                f"INSERT INTO vehicles (id, organization_id, vehicle_number, "
                f"vehicle_type, status, created_at, updated_at) "
                f"VALUES ('{unique_vehicle_id}', '{unique_org_id}', "
                f"'V-TEST-{unique_vehicle_id}', 'BUS', 'ACTIVE', now(), now())"
            )
        )

        trip_id_str = f"'{unique_trip_id}'" if has_trip else "NULL"
        if has_trip:
            session.execute(
                text(
                    f"INSERT INTO trips (id, organization_id, service_id, vehicle_id, route_id, "
                    f"direction, operating_date, planned_start_at, status, created_at, updated_at) "
                    f"VALUES ('{unique_trip_id}', '{unique_org_id}', '{SVC_AC4B_ID}', "
                    f"'{unique_vehicle_id}', '{ROUTE_R1_ID}', 'A_TO_B', '2026-08-26', "
                    f"now(), 'ACTIVE', now(), now())"
                )
            )
            session.execute(
                text(
                    f"INSERT INTO trip_assignments (id, trip_id, user_id, device_id, role, "
                    f"assigned_at, status) VALUES ('{uuid.uuid4()}', '{unique_trip_id}', "
                    f"'{unique_user_id}', '{device_id}', 'PRIMARY_DRIVER', now(), 'ACTIVE')"
                )
            )

        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        session.execute(
            text(
                f"INSERT INTO tracking_sessions (id, device_id, operator_id, trip_id, "
                f"started_at, status, created_at, updated_at) VALUES ('{session_id}', "
                f"'{device_id}', '{unique_user_id}', {trip_id_str}, '{past_time.isoformat()}', "
                f"'ACTIVE', now(), now())"
            )
        )

        session.commit()

    return {
        "emp_code": emp_code,
        "password": "testpass123",
        "vehicle_id": str(unique_vehicle_id),
        "trip_id": str(unique_trip_id) if has_trip else None,
        "session_id": str(session_id),
        "device_id": str(device_id),
        "user_id": str(unique_user_id),
    }


def test_end_to_end_telemetry_to_passenger():
    """
    Test the full chain: Operator submits telemetry -> Orchestrator fuses to
    Canonical State -> Passenger queries ETA.
    """
    setup_data = setup_operator_and_session(has_trip=True)

    # 1. Login
    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": setup_data["emp_code"], "password": setup_data["password"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Submit Telemetry
    now = datetime.now(timezone.utc)
    packet_id = str(uuid.uuid4())
    payload = {
        "session_id": setup_data["session_id"],
        "packets": [
            {
                "packet_id": packet_id,
                "latitude": 12.0,
                "longitude": 77.0,
                "accuracy_m": 10.0,
                "speed_mps": 15.0,
                "heading": 90.0,
                "observed_at": now.isoformat(),
                "device_sequence": 1,
            }
        ],
    }

    resp = client.post("/api/tracking/batch", json=payload, headers=headers)
    assert resp.status_code == 200
    assert packet_id in resp.json()["accepted"]

    # 3. Verify Passenger Endpoint
    passenger_resp = client.get(f"/api/passenger/vehicles/{setup_data['vehicle_id']}")
    assert passenger_resp.status_code == 200
    passenger_data = passenger_resp.json()

    # Because of orchestrator, we expect canonical state to be created
    assert passenger_data["vehicle_id"] == setup_data["vehicle_id"]
    assert passenger_data["state"] in ["LIVE", "DEGRADED", "STALE", "UNKNOWN"]
    # ETA might be 0 or populated depending on route matching, but the payload must be well-formed
    assert "eta_seconds" in passenger_data


def test_end_to_end_no_trip():
    """
    Test negative case: Session without a trip produces tracking rows but no canonical ETA state.
    """
    setup_data = setup_operator_and_session(has_trip=False)

    # 1. Login
    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": setup_data["emp_code"], "password": setup_data["password"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Submit Telemetry
    now = datetime.now(timezone.utc)
    packet_id = str(uuid.uuid4())
    payload = {
        "session_id": setup_data["session_id"],
        "packets": [
            {
                "packet_id": packet_id,
                "latitude": 12.0,
                "longitude": 77.0,
                "accuracy_m": 10.0,
                "speed_mps": 15.0,
                "heading": 90.0,
                "observed_at": now.isoformat(),
                "device_sequence": 1,
            }
        ],
    }

    resp = client.post("/api/tracking/batch", json=payload, headers=headers)
    assert resp.status_code == 200
    assert packet_id in resp.json()["accepted"]

    # 3. Verify DB has tracking event
    with Session(engine) as session:
        count = session.execute(
            text(f"SELECT count(*) FROM tracking_events WHERE packet_id='{packet_id}'")
        ).scalar()
        assert count == 1

    # 4. Verify Passenger Endpoint returns 404
    # (No canonical state without trip inference/orchestrator assigning trip)
    passenger_resp = client.get(f"/api/passenger/vehicles/{setup_data['vehicle_id']}")
    assert passenger_resp.status_code == 404
