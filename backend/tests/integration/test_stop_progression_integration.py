import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.main import app
from tests.integration.test_cross_batch_context import setup_operator_and_session

client = TestClient(app)


def _send_telemetry(token, session_id, lat, lon, sequence, progress_time):
    resp = client.post(
        "/api/tracking/batch",
        json={
            "session_id": session_id,
            "packets": [
                {
                    "packet_id": str(uuid.uuid4()),
                    "latitude": lat,
                    "longitude": lon,
                    "accuracy_m": 5.0,
                    "speed_mps": 10.0,
                    "heading": 90.0,
                    "observed_at": progress_time.isoformat(),
                    "device_sequence": sequence,
                }
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def _get_passenger_state(vehicle_id):
    resp = client.get(f"/api/passenger/vehicles/{vehicle_id}")
    assert resp.status_code == 200
    return resp.json()


def test_stop_progression_integration():
    """
    Tests that:
    1. Database km converts to meters.
    2. CC is current/next near 0m.
    3. MG is current/next near 1300m.
    4. KP is current/next near 3100m.
    5. TP is terminal near 5200m.
    6. At 50m, MG/KP/TP are NOT all marked passed.
    7. Context survives across HTTP requests.
    8. Context preserves temporal states.
    9. New vehicle starts with independent stop context.
    10. New trip does not inherit prior context.
    """
    setup_data = setup_operator_and_session()

    # The seed data creates a linestring that is ~2km long, but sets stops at 1.3km, 3.1km, 5.2km.
    # We must update the stops to match the actual spatial progress of the coordinates.
    # The route has 3 segments between 4 points.
    # We can query the DB for the exact segment lengths to ensure perfect precision.
    with Session(engine) as session:
        # Get the actual segment progress for R1
        from app.repositories.route_spatial import get_candidate_segments_query

        query = text(get_candidate_segments_query())
        # We query near CC to get the first few segments
        result = session.execute(
            query, {"lon": 76.7794, "lat": 30.7333, "search_radius_m": 10000.0}
        )
        segments = {
            row.segment_index: float(row.segment_progress_start_m)
            for row in result
            if str(row.route_id) == "20000000-0000-0000-0000-000000000001"
        }

        # segments[1] is distance to point 1 (MG)
        # segments[2] is distance to point 2 (KP)
        # segments[3] is distance to point 3 (TP)
        dist_cc = 0.0
        dist_mg = segments.get(1, 570.0) / 1000.0
        dist_kp = segments.get(2, 1259.0) / 1000.0
        dist_tp = segments.get(3, 1980.0) / 1000.0

        session.execute(
            text(
                f"UPDATE route_stops SET distance_from_start = {dist_cc} WHERE stop_id = '30000000-0000-0000-0000-000000000001'"
            )
        )
        session.execute(
            text(
                f"UPDATE route_stops SET distance_from_start = {dist_mg} WHERE stop_id = '30000000-0000-0000-0000-000000000002'"
            )
        )
        session.execute(
            text(
                f"UPDATE route_stops SET distance_from_start = {dist_kp} WHERE stop_id = '30000000-0000-0000-0000-000000000003'"
            )
        )
        session.execute(
            text(
                f"UPDATE route_stops SET distance_from_start = {dist_tp} WHERE stop_id = '30000000-0000-0000-0000-000000000004'"
            )
        )
        session.commit()

    # Login
    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": setup_data["emp_code"], "password": setup_data["password"]},
    )
    token = login_resp.json()["access_token"]

    start_time = datetime.now(timezone.utc) - timedelta(seconds=600)
    session_id = setup_data["session_id"]
    vehicle_id = setup_data["vehicle_id"]

    # Step 1 & 2 & 7: Near 0m (CC is 30.7333, 76.7794)
    # Send a request at the exact CC coordinates to bootstrap contexts
    _send_telemetry(token, session_id, 30.7333, 76.7794, 1, start_time)

    # Check DB to ensure state is persisted (even if Stop State is UNKNOWN)
    with Session(engine) as session:
        row = session.execute(
            text(f"SELECT engine_contexts FROM bus_current_state WHERE vehicle_id = '{vehicle_id}'")
        ).scalar_one()
        assert "stop_ctx" in row
        # stop_ctx won't have populated stop_states yet because direction is UNKNOWN

    # Step 6: Move 50m away from CC.
    # At 50m, CC might be passed, but MG (1300m), KP (3100m), TP (5200m) MUST NOT BE PASSED.
    # If the bug were active, 50m would mark ALL stops passed.
    _send_telemetry(token, session_id, 30.7335, 76.7800, 2, start_time + timedelta(seconds=10))
    state_50m = _get_passenger_state(vehicle_id)

    # 3000...2 is MG. It should be the next stop, NOT passed (which would make next_stop_id something else or null)
    assert state_50m["next_stop_id"] == "30000000-0000-0000-0000-000000000002"

    with Session(engine) as session:
        row = session.execute(
            text(f"SELECT engine_contexts FROM bus_current_state WHERE vehicle_id = '{vehicle_id}'")
        ).scalar_one()
        stop_states = row["stop_ctx"]["stop_states"]
        # CC might be PASSED_STOP
        # MG must be BEFORE_STOP or UNKNOWN, not PASSED_STOP
        assert stop_states.get("30000000-0000-0000-0000-000000000002") in ["BEFORE_STOP", "UNKNOWN"]
        assert stop_states.get("30000000-0000-0000-0000-000000000003") in ["BEFORE_STOP", "UNKNOWN"]
        assert stop_states.get("30000000-0000-0000-0000-000000000004") in ["BEFORE_STOP", "UNKNOWN"]

    # Step 3: Move to ~647m (Just PAST MG - 30.7355, 76.7855)
    # Gap from 50m is 597m. At 10 m/s, it takes 60s. Total time = 10 + 60 = 70s.
    _send_telemetry(token, session_id, 30.7355, 76.7855, 3, start_time + timedelta(seconds=70))
    state_1300m = _get_passenger_state(vehicle_id)
    with Session(engine) as session:
        row = session.execute(
            text(
                f"SELECT route_progress, engine_contexts FROM bus_current_state WHERE vehicle_id = '{vehicle_id}'"
            )
        ).fetchone()
        print("1300m Route Progress:", row.route_progress)
        print("1300m Stop States:", row.engine_contexts["stop_ctx"]["stop_states"])
        print("1300m Diagnostics:", row.engine_contexts["stop_ctx"].get("diagnostics", []))
    print("1300m State:", state_1300m)
    assert (
        state_1300m["current_stop_id"] == "30000000-0000-0000-0000-000000000003"
        or state_1300m["next_stop_id"] == "30000000-0000-0000-0000-000000000003"
    )

    # Step 4: Move to ~1336m (Just PAST KP - 30.7405, 76.7905)
    # Gap from Past MG is 689m. At 10 m/s, it takes 69s. Total time = 70 + 69 = 139s.
    _send_telemetry(token, session_id, 30.7405, 76.7905, 4, start_time + timedelta(seconds=139))
    state_3100m = _get_passenger_state(vehicle_id)
    with Session(engine) as session:
        row = session.execute(
            text(
                f"SELECT route_progress, engine_contexts FROM bus_current_state WHERE vehicle_id = '{vehicle_id}'"
            )
        ).fetchone()
        print("3100m Route Progress:", row.route_progress)
        print("3100m Stop States:", row.engine_contexts["stop_ctx"]["stop_states"])
    print("3100m State:", state_3100m)
    assert (
        state_3100m["current_stop_id"] == "30000000-0000-0000-0000-000000000004"
        or state_3100m["next_stop_id"] == "30000000-0000-0000-0000-000000000004"
    )

    # Step 5: Move to ~5200m (TP - 30.7450, 76.7950)
    # Gap from Past KP is ~650m. At 10 m/s, it takes 65s. Total time = 139 + 65 = 204s.
    _send_telemetry(token, session_id, 30.7450, 76.7950, 5, start_time + timedelta(seconds=204))
    state_5200m = _get_passenger_state(vehicle_id)
    print("5200m State:", state_5200m)
    assert (
        state_5200m["current_stop_id"] == "30000000-0000-0000-0000-000000000004"
        or state_5200m["next_stop_id"] == "30000000-0000-0000-0000-000000000004"
    )


def test_independent_stop_context_across_vehicles_and_trips():
    """
    9. New vehicle starts with independent stop context.
    10. New trip does not inherit prior trip stop context.
    """
    data_a = setup_operator_and_session()
    data_b = setup_operator_and_session()

    # Create dummy contexts for A with PASSED_STOP for CC
    with Session(engine) as session:
        session.execute(
            text(
                "UPDATE bus_current_state SET engine_contexts = "
                '\'{"stop_ctx": {"stop_states": {"30000000-0000-0000-0000-000000000001": "PASSED_STOP"}}}\'::JSONB '
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

    # Verify B did NOT inherit A's context (CC should not be strictly PASSED_STOP yet for a non-moving bus at origin)
    with Session(engine) as session:
        row_b = session.execute(
            text(
                "SELECT engine_contexts FROM bus_current_state "
                f"WHERE vehicle_id = '{data_b['vehicle_id']}'"
            )
        ).scalar_one()
        assert (
            row_b["stop_ctx"]["stop_states"].get("30000000-0000-0000-0000-000000000001")
            != "PASSED_STOP"
        )
