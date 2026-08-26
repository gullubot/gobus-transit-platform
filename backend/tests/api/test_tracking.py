"""
Transit Platform — Telemetry Ingestion API Tests.

BUILD 2: Tests for batch telemetry upload, deduplication, partial ACK,
out-of-order handling, and device heartbeat.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import TRIP_PLANNED_ID, seed_dev_data
from app.main import app
from app.models.tracking import TrackingEvent

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        seed_dev_data(session)


def get_authenticated_driver_headers() -> tuple[dict[str, str], str]:
    """Helper to authenticate DRV001, start a tracking session, and return headers + session_id."""
    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "DRV001", "password": "operator123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    start_resp = client.post(f"/api/trips/{TRIP_PLANNED_ID}/start", headers=headers)
    session_id = start_resp.json()["tracking_session_id"]
    return headers, session_id


def test_valid_telemetry_batch_ingestion():
    """Batch of valid telemetry packets is ingested and returns accepted packet IDs."""
    headers, session_id = get_authenticated_driver_headers()

    now = datetime.now(timezone.utc).isoformat()
    pkt1 = uuid.uuid4()
    pkt2 = uuid.uuid4()

    batch_payload = {
        "session_id": session_id,
        "packets": [
            {
                "packet_id": str(pkt1),
                "latitude": 30.7333,
                "longitude": 76.7794,
                "accuracy_m": 5.0,
                "speed_mps": 8.5,
                "heading": 90.0,
                "observed_at": now,
                "device_sequence": 1,
                "battery_level": 95.0,
                "network_type": "4G",
                "gps_status": "AVAILABLE",
            },
            {
                "packet_id": str(pkt2),
                "latitude": 30.7350,
                "longitude": 76.7850,
                "accuracy_m": 4.5,
                "speed_mps": 10.2,
                "heading": 92.0,
                "observed_at": now,
                "device_sequence": 2,
                "battery_level": 94.0,
                "network_type": "4G",
                "gps_status": "AVAILABLE",
            },
        ],
    }

    response = client.post("/api/tracking/batch", json=batch_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert str(pkt1) in data["accepted"]
    assert str(pkt2) in data["accepted"]
    assert len(data["duplicates"]) == 0
    assert len(data["rejected"]) == 0

    # Verify server created received_at in database
    with Session(engine) as session:
        events = (
            session.execute(select(TrackingEvent).where(TrackingEvent.packet_id.in_([pkt1, pkt2])))
            .scalars()
            .all()
        )
        assert len(events) == 2
        for evt in events:
            assert evt.received_at is not None
            assert evt.observed_at is not None


def test_duplicate_packet_deduplication():
    """Re-submitting the same packet returns it in duplicates list without double insertion."""
    headers, session_id = get_authenticated_driver_headers()
    now = datetime.now(timezone.utc).isoformat()
    pkt = uuid.uuid4()

    payload = {
        "session_id": session_id,
        "packets": [
            {
                "packet_id": str(pkt),
                "latitude": 30.7333,
                "longitude": 76.7794,
                "observed_at": now,
                "device_sequence": 10,
            }
        ],
    }

    # 1. First upload -> accepted
    resp1 = client.post("/api/tracking/batch", json=payload, headers=headers)
    assert resp1.status_code == 200
    assert str(pkt) in resp1.json()["accepted"]

    # 2. Duplicate upload -> recognized as duplicate
    resp2 = client.post("/api/tracking/batch", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert str(pkt) in resp2.json()["duplicates"]
    assert str(pkt) not in resp2.json()["accepted"]


def test_partial_batch_with_invalid_coordinates_handled():
    """Batch with mixed valid and invalid coordinate packets acknowledges both accordingly."""
    headers, session_id = get_authenticated_driver_headers()
    now = datetime.now(timezone.utc).isoformat()
    valid_pkt = uuid.uuid4()
    invalid_pkt = uuid.uuid4()

    payload = {
        "session_id": session_id,
        "packets": [
            {
                "packet_id": str(valid_pkt),
                "latitude": 30.7333,
                "longitude": 76.7794,
                "observed_at": now,
                "device_sequence": 20,
            },
            {
                "packet_id": str(invalid_pkt),
                "latitude": 195.0,  # Invalid latitude (> 90)
                "longitude": 76.7794,
                "observed_at": now,
                "device_sequence": 21,
            },
        ],
    }

    response = client.post("/api/tracking/batch", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert str(valid_pkt) in data["accepted"]
    assert any(r["packet_id"] == str(invalid_pkt) for r in data["rejected"])


def test_out_of_order_packets_stored_successfully():
    """Packets arriving out of chronological order are stored with their respective timestamps."""
    headers, session_id = get_authenticated_driver_headers()
    now = datetime.now(timezone.utc).isoformat()
    pkt_later = uuid.uuid4()
    pkt_earlier = uuid.uuid4()

    # Upload sequence 30 first
    client.post(
        "/api/tracking/batch",
        json={
            "session_id": session_id,
            "packets": [
                {
                    "packet_id": str(pkt_later),
                    "latitude": 30.7400,
                    "longitude": 76.7900,
                    "observed_at": now,
                    "device_sequence": 30,
                }
            ],
        },
        headers=headers,
    )

    # Upload sequence 29 later
    resp = client.post(
        "/api/tracking/batch",
        json={
            "session_id": session_id,
            "packets": [
                {
                    "packet_id": str(pkt_earlier),
                    "latitude": 30.7350,
                    "longitude": 76.7850,
                    "observed_at": now,
                    "device_sequence": 29,
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert str(pkt_earlier) in resp.json()["accepted"]


def test_heartbeat_updates_device_health():
    """Heartbeat updates device status and returns ok."""
    headers, session_id = get_authenticated_driver_headers()
    payload = {
        "session_id": session_id,
        "battery_level": 88.0,
        "network_type": "WIFI",
        "gps_status": "AVAILABLE",
        "app_version": "0.1.0",
    }
    response = client.post("/api/tracking/heartbeat", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "received_at" in data
    assert data["device_status"] == "ACTIVE"


def test_batch_upload_without_active_session_rejected():
    """Attempting batch upload with an invalid/unauthorized session ID returns 403 or 400."""
    login_resp = client.post(
        "/api/auth/operator/login",
        json={"employee_code": "DRV001", "password": "operator123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    random_session_id = uuid.uuid4()
    payload = {
        "session_id": str(random_session_id),
        "packets": [
            {
                "packet_id": str(uuid.uuid4()),
                "latitude": 30.7333,
                "longitude": 76.7794,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "device_sequence": 1,
            }
        ],
    }
    response = client.post("/api/tracking/batch", json=payload, headers=headers)
    assert response.status_code in (400, 403)


def test_duplicate_device_sequence_handling():
    """Uploading a different packet_id with an already ingested device_sequence is deduplicated."""
    headers, session_id = get_authenticated_driver_headers()
    now = datetime.now(timezone.utc).isoformat()
    pkt1 = uuid.uuid4()
    pkt2 = uuid.uuid4()

    # Ingest sequence 50
    resp1 = client.post(
        "/api/tracking/batch",
        json={
            "session_id": session_id,
            "packets": [
                {
                    "packet_id": str(pkt1),
                    "latitude": 30.7333,
                    "longitude": 76.7794,
                    "observed_at": now,
                    "device_sequence": 50,
                }
            ],
        },
        headers=headers,
    )
    assert resp1.status_code == 200
    assert str(pkt1) in resp1.json()["accepted"]

    # Ingest sequence 50 with a different packet_id (e.g. re-serialized packet)
    resp2 = client.post(
        "/api/tracking/batch",
        json={
            "session_id": session_id,
            "packets": [
                {
                    "packet_id": str(pkt2),
                    "latitude": 30.7333,
                    "longitude": 76.7794,
                    "observed_at": now,
                    "device_sequence": 50,
                }
            ],
        },
        headers=headers,
    )
    assert resp2.status_code == 200
    assert str(pkt2) in resp2.json()["duplicates"]


def test_session_ended_rejects_new_telemetry():
    """After trip tracking is ended, subsequent batch uploads are rejected."""
    headers, session_id = get_authenticated_driver_headers()

    # End the trip session
    client.post(f"/api/trips/{TRIP_PLANNED_ID}/end", headers=headers)

    # Attempt to upload telemetry for the ended session
    payload = {
        "session_id": session_id,
        "packets": [
            {
                "packet_id": str(uuid.uuid4()),
                "latitude": 30.7333,
                "longitude": 76.7794,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "device_sequence": 99,
            }
        ],
    }
    response = client.post("/api/tracking/batch", json=payload, headers=headers)
    assert response.status_code == 400
    assert "ended" in response.json()["detail"].lower()
