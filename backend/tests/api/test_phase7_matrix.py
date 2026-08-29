import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import ORG_ID, TRIP_COMPLETED_ID, VEH_IDS
from app.intelligence.crowding_engine import CrowdingEngine
from app.main import app
from app.models.crowding import CrowdingReport
from app.models.enums import CrowdingSource, CrowdingState

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    from sqlalchemy import text

    from app.db.seed import seed_dev_data

    with Session(engine) as session:
        session.execute(text("DELETE FROM crowding_reports"))
        session.commit()
        seed_dev_data(session)


# Case 8: Client source spoofing
def test_case_08_client_source_spoofing():
    """Client cannot elevate source_type."""
    vehicle_id = str(VEH_IDS["PNB005781"])
    report_id = str(uuid.uuid4())
    payload = {
        "report_id": report_id,
        "vehicle_id": vehicle_id,
        "crowding_state": CrowdingState.MODERATE.value,
        "confidence": 0.8,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_type": "OPERATOR",  # Attempt spoof
    }
    resp = client.post("/api/crowding/reports", json=payload)
    assert resp.status_code == 200
    assert resp.json()["source_type"] == "PASSENGER"


# Case 16, 17: Future timestamp, allowed clock skew
def test_case_16_17_future_timestamp_and_skew():
    vehicle_id = str(VEH_IDS["PNB005781"])
    # Skew just within 300s (5 mins) -> Allowed
    payload_ok = {
        "report_id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "crowding_state": CrowdingState.LOW.value,
        "confidence": 0.8,
        "observed_at": (datetime.now(timezone.utc) + timedelta(minutes=4)).isoformat(),
    }
    resp1 = client.post("/api/crowding/reports", json=payload_ok)
    assert resp1.status_code == 200

    # Skew beyond 300s -> Rejected
    payload_bad = {
        "report_id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "crowding_state": CrowdingState.LOW.value,
        "confidence": 0.8,
        "observed_at": (datetime.now(timezone.utc) + timedelta(minutes=6)).isoformat(),
    }
    resp2 = client.post("/api/crowding/reports", json=payload_bad)
    assert resp2.status_code == 400


# Case 20: >60 minute rejection
def test_case_20_rejection_over_60_mins():
    vehicle_id = str(VEH_IDS["PNB005781"])
    payload = {
        "report_id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "crowding_state": CrowdingState.LOW.value,
        "confidence": 0.8,
        "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=61)).isoformat(),
    }
    resp = client.post("/api/crowding/reports", json=payload)
    assert resp.status_code == 400


# Case 18, 19: 0-20 LIVE, 20-60 HISTORICAL (Tested via engine)
def test_case_18_19_freshness_boundaries():
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        # At 15 mins -> LIVE_REPORTED
        r1 = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=ORG_ID,
            vehicle_id=VEH_IDS["PNB005781"],
            trip_id=TRIP_COMPLETED_ID,
            crowding_state=CrowdingState.MODERATE,
            confidence=1.0,
            observed_at=now - timedelta(minutes=15),
            source_type=CrowdingSource.PASSENGER,
        )
        session.add(r1)
        session.commit()
        res1 = CrowdingEngine.aggregate_vehicle_crowding(
            session, VEH_IDS["PNB005781"], reference_time=now
        )
        print(f"Debug res1: {res1}")
        assert res1.evidence_type == "LIVE_REPORTED"

        # Move to 30 old
        r1.observed_at = now - timedelta(minutes=30)
        session.commit()
        res2 = CrowdingEngine.aggregate_vehicle_crowding(
            session, VEH_IDS["PNB005781"], reference_time=now
        )
        # Even if trip_id was set, the test checks historical fallback. But since we used TRIP_COMPLETED_ID, it should be HISTORICAL_REPORTED.  # noqa: E501
        assert res2.evidence_type == "HISTORICAL_REPORTED"

        # Move to 59 old
        r1.observed_at = now - timedelta(minutes=59)
        session.commit()
        res3 = CrowdingEngine.aggregate_vehicle_crowding(
            session, VEH_IDS["PNB005781"], reference_time=now
        )
        assert res3.evidence_type == "HISTORICAL_REPORTED"

        session.delete(r1)
        session.commit()


# Case 31, 32: Conflict penalty, operator/passenger conflict
def test_case_31_conflict_penalty():
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.execute(text("DELETE FROM crowding_reports"))
        r1 = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=ORG_ID,
            vehicle_id=VEH_IDS["PNB005781"],
            trip_id=TRIP_COMPLETED_ID,
            crowding_state=CrowdingState.LOW,
            confidence=1.0,
            observed_at=now,
            source_type=CrowdingSource.PASSENGER,
        )
        r2 = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=ORG_ID,
            vehicle_id=VEH_IDS["PNB005781"],
            trip_id=TRIP_COMPLETED_ID,
            crowding_state=CrowdingState.FULL,
            confidence=1.0,
            observed_at=now,
            source_type=CrowdingSource.PASSENGER,
        )
        session.add_all([r1, r2])
        session.commit()

        res = CrowdingEngine.aggregate_vehicle_crowding(
            session, VEH_IDS["PNB005781"], reference_time=now
        )
        # States: 1 and 4. Mean = 2.5. Midpoint rounding -> 3 (HIGH)
        assert res.state == CrowdingState.HIGH
        # Variance: mean=2.5. (1-2.5)^2 + (4-2.5)^2 = 2.25 + 2.25 = 4.5. 4.5/2 = 2.25. stddev = 1.5
        # Conflict penalty = 0.15 * 1.5 = 0.225.
        # Base confidence = sum(w^2)/sum(w) = (0.6^2 + 0.6^2) / 1.2 = 0.60
        # Final = 0.60 - 0.225 = 0.375
        import math

        assert math.isclose(res.confidence, 0.375, rel_tol=1e-5, abs_tol=1e-5)

        session.delete(r1)
        session.delete(r2)
        session.commit()


# Case 33: Passenger rate limit
def test_case_33_passenger_rate_limit():
    vehicle_id = str(VEH_IDS["PNB006421"])
    import uuid

    # passenger can submit 2 per 5 min
    p1 = {
        "report_id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "crowding_state": "LOW",
        "confidence": 0.8,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    p2 = {
        "report_id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "crowding_state": "LOW",
        "confidence": 0.8,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    p3 = {
        "report_id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "crowding_state": "LOW",
        "confidence": 0.8,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Try 3 requests in a row
    client.post("/api/crowding/reports", json=p1)
    client.post("/api/crowding/reports", json=p2)
    resp3 = client.post("/api/crowding/reports", json=p3)
    assert resp3.status_code == 429


# Case 41: Passenger-safe output
def test_case_41_passenger_safe_output():
    vehicle_id = str(VEH_IDS["PNB005781"])
    resp = client.get(f"/api/passenger/vehicles/{vehicle_id}/crowding")
    assert resp.status_code == 200
    data = resp.json()
    assert "state" in data
    assert "confidence" in data
    assert "evidence_type" in data
    assert "stale" in data
    assert "report_id" not in data
    assert "device_id" not in data
    assert "internal" not in data


# Case 42: received_at server-generated
def test_case_42_received_at():
    vehicle_id = str(VEH_IDS["PNB005781"])
    report_id = str(uuid.uuid4())
    payload = {
        "report_id": report_id,
        "vehicle_id": vehicle_id,
        "crowding_state": CrowdingState.MODERATE.value,
        "confidence": 0.8,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "received_at": "1999-01-01T00:00:00Z",  # Spoof attempt
    }
    resp = client.post("/api/crowding/reports", json=payload)
    assert resp.status_code in [200, 429]
    if resp.status_code == 200:
        assert resp.json()["received_at"] != "1999-01-01T00:00:00Z"
