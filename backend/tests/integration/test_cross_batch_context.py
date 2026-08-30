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
    with Session(engine) as session:
        session.execute(text("DELETE FROM tracking_events"))
        session.execute(text("DELETE FROM tracking_sessions"))
        session.execute(text("DELETE FROM bus_current_state"))
        session.execute(text("DELETE FROM trip_assignments"))
        session.commit()
        seed_dev_data(session)


def setup_operator_and_session():
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

        now_utc = datetime.now(timezone.utc).isoformat()

        # Insert a trip starting NOW
        session.execute(
            text(
                f"INSERT INTO trips (id, organization_id, service_id, vehicle_id, route_id, "
                f"direction, operating_date, planned_start_at, status, created_at, updated_at) "
                f"VALUES ('{unique_trip_id}', '{unique_org_id}', '{SVC_AC4B_ID}', "
                f"'{unique_vehicle_id}', '{ROUTE_R1_ID}', 'A_TO_B', '2026-08-26', "
                f"'{now_utc}', 'PLANNED', '{now_utc}', '{now_utc}')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO trip_assignments (id, trip_id, user_id, device_id, role, "
                f"assigned_at, status) VALUES ('{uuid.uuid4()}', '{unique_trip_id}', "
                f"'{unique_user_id}', '{device_id}', 'PRIMARY_DRIVER', '{now_utc}', 'ACTIVE')"
            )
        )

        session.execute(
            text(
                f"INSERT INTO tracking_sessions (id, device_id, operator_id, trip_id, started_at, "
                f"status, created_at, updated_at) VALUES ('{session_id}', '{device_id}', "
                f"'{unique_user_id}', '{unique_trip_id}', '{now_utc}', 'ACTIVE', "
                f"'{now_utc}', '{now_utc}')"
            )
        )

        session.commit()

    return {
        "emp_code": emp_code,
        "password": "testpass123",
        "vehicle_id": str(unique_vehicle_id),
        "trip_id": str(unique_trip_id),
        "session_id": str(session_id),
    }


def test_cross_batch_context_accumulation():
    """
    Simulates the actual Android pattern: multiple HTTP requests with small batches.
    Validates that TripInference score accumulates, StopProgression survives,
    and Canonical State updates properly.
    """
    setup_data = setup_operator_and_session()

    # Login
    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": setup_data["emp_code"], "password": setup_data["password"]},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Simulate moving from City Center (CC) to MG Road
    # CC: 30.7333, 76.7794
    # MG: 30.735, 76.785
    start_time = datetime.now(timezone.utc) - timedelta(minutes=2)

    # 5 sequential single-event batches
    coords = [
        (30.7333, 76.7794),
        (30.7336, 76.7805),
        (30.7340, 76.7820),
        (30.7345, 76.7835),
        (30.7350, 76.7850),  # MG Road
    ]

    for i, (lat, lon) in enumerate(coords):
        observed_at = start_time + timedelta(seconds=i * 15)

        payload = {
            "session_id": setup_data["session_id"],
            "packets": [
                {
                    "packet_id": str(uuid.uuid4()),
                    "latitude": lat,
                    "longitude": lon,
                    "accuracy_m": 5.0,
                    "speed_mps": 10.0,
                    "heading": 90.0,
                    "observed_at": observed_at.isoformat(),
                    "device_sequence": i + 1,
                }
            ],
        }
        resp = client.post("/api/tracking/batch", json=payload, headers=headers)
        assert resp.status_code == 200

        # After each batch, query the passenger API to see if state evolved
        passenger_resp = client.get(f"/api/passenger/vehicles/{setup_data['vehicle_id']}")
        assert passenger_resp.status_code == 200
        p_data = passenger_resp.json()
        print(
            f"Batch {i}: passenger state = {p_data['state']}, trip_status = {p_data['trip_status']}"
        )

        with Session(engine) as session:
            row = session.execute(
                text(
                    "SELECT engine_contexts FROM bus_current_state "
                    f"WHERE vehicle_id = '{setup_data['vehicle_id']}'"
                )
            ).scalar_one()
            print(f"Batch {i} DB Contexts:", row)

        # Verify DirectionEngine crash is fixed (state should not be stuck/missing)
        # Because we match R1, tracker is fused.
        assert p_data["state"] in ["LIVE", "DEGRADED", "STALE"]

    # Final verification - since context survived, score accumulated across 5 requests!
    # Trip should be ACTIVE
    passenger_resp = client.get(f"/api/passenger/vehicles/{setup_data['vehicle_id']}")
    p_data = passenger_resp.json()

    assert p_data["trip_status"] == "ACTIVE"

    # Ensure current_stop_id or next_stop_id progressed and is not null
    # (Since it moved from CC to MG)
    assert p_data["next_stop_id"] is not None

    # Verify context isolation across vehicles/trips by ensuring engine_contexts
    # is populated properly in DB
    with Session(engine) as session:
        row = session.execute(
            text(
                "SELECT engine_contexts FROM bus_current_state "
                f"WHERE vehicle_id = '{setup_data['vehicle_id']}'"
            )
        ).scalar_one()
        assert row is not None
        assert "trip_ctx" in row
        assert "stop_ctx" in row
        assert row["trip_ctx"]["score"] >= 80.0


def test_cross_batch_isolation():
    # Prove Vehicle A cannot inherit Vehicle B context
    data_a = setup_operator_and_session()
    data_b = setup_operator_and_session()

    # Create dummy contexts for A
    with Session(engine) as session:
        session.execute(
            text(
                "UPDATE bus_current_state SET engine_contexts = "
                '\'{"trip_ctx": {"score": 99.0}}\'::JSONB '
                f"WHERE vehicle_id = '{data_a['vehicle_id']}'"
            )
        )
        session.commit()

    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": data_b["emp_code"], "password": data_b["password"]},
    )
    token_b = login_resp.json()["access_token"]

    # Send telemetry for B
    resp = client.post(
        "/api/tracking/batch",
        json={
            "session_id": data_b["session_id"],
            "packets": [
                {
                    "packet_id": str(uuid.uuid4()),
                    "latitude": 30.7333,
                    "longitude": 76.7794,
                    "accuracy_m": 5.0,
                    "speed_mps": 0.0,
                    "heading": 90.0,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "device_sequence": 1,
                }
            ],
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 200

    # Verify B did NOT inherit A's context (score 99.0)
    with Session(engine) as session:
        row_b = session.execute(
            text(
                "SELECT engine_contexts FROM bus_current_state "
                f"WHERE vehicle_id = '{data_b['vehicle_id']}'"
            )
        ).scalar_one()
        assert row_b["trip_ctx"]["score"] != 99.0


def test_corrupt_engine_context_recovery():
    # Prove Missing/corrupt engine_contexts fails safely and recovers
    data = setup_operator_and_session()

    # Set corrupt JSON context
    with Session(engine) as session:
        session.execute(
            text(
                "UPDATE bus_current_state SET engine_contexts = "
                '\'{"trip_ctx": "garbage_string_not_dict"}\'::JSONB '
                f"WHERE vehicle_id = '{data['vehicle_id']}'"
            )
        )
        session.commit()

    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": data["emp_code"], "password": data["password"]},
    )
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/api/tracking/batch",
        json={
            "session_id": data["session_id"],
            "packets": [
                {
                    "packet_id": str(uuid.uuid4()),
                    "latitude": 30.7333,
                    "longitude": 76.7794,
                    "accuracy_m": 5.0,
                    "speed_mps": 10.0,
                    "heading": 90.0,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "device_sequence": 1,
                }
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Context should be successfully overwritten with valid new context
    with Session(engine) as session:
        row = session.execute(
            text(
                "SELECT engine_contexts FROM bus_current_state "
                f"WHERE vehicle_id = '{data['vehicle_id']}'"
            )
        ).scalar_one()
        assert isinstance(row["trip_ctx"], dict)
        assert "score" in row["trip_ctx"]
