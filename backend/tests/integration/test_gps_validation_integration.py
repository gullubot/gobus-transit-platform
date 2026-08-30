import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.db.database import engine
from app.models.state import BusCurrentState
from app.schemas.tracking import TrackingBatchRequest, TrackingPacketIn
from app.services.tracking_service import ingest_telemetry_batch
from tests.integration.test_end_to_end import ensure_seed, setup_operator_and_session

_ = ensure_seed


@pytest.fixture(autouse=True)
def apply_seed(request):
    request.getfixturevalue("ensure_seed")


@pytest.fixture
def mock_user():
    class MockUser:
        id = None

    return MockUser()


def test_gps_validation_rejects_impossible_jump(mock_user):
    setup_data = setup_operator_and_session(has_trip=True)
    mock_user.id = uuid.UUID(setup_data["user_id"])
    vehicle_id = uuid.UUID(setup_data["vehicle_id"])
    trip_id = uuid.UUID(setup_data["trip_id"])
    session_id = uuid.UUID(setup_data["session_id"])

    with Session(engine) as db_session:
        now = datetime.now(timezone.utc)

        # Add an existing canonical state (e.g. at Chandigarh)
        bcs = BusCurrentState(
            vehicle_id=vehicle_id,
            trip_id=trip_id,
            latitude=30.745,
            longitude=76.795,
            speed=10.0,
            state="LIVE",
            last_observed_at=now - timedelta(seconds=10),
            last_received_at=now - timedelta(seconds=10),
        )
        db_session.add(bcs)
        db_session.commit()

        # Simulate a batch containing a Kolkata coordinate (1500km jump in 10 seconds)
        req = TrackingBatchRequest(
            session_id=session_id,
            packets=[
                TrackingPacketIn(
                    packet_id=uuid.uuid4(),
                    latitude=22.459,
                    longitude=88.309,
                    accuracy_m=5.0,
                    speed_mps=5.0,
                    heading=0.0,
                    observed_at=now,
                    device_sequence=1,
                    battery_level=100.0,
                    network_type="WIFI",
                    gps_status="AVAILABLE",
                )
            ],
        )

        resp = ingest_telemetry_batch(db_session, mock_user, req)
        assert len(resp.accepted) == 1

        db_session.expire_all()
        updated_bcs = db_session.get(BusCurrentState, vehicle_id)

        assert updated_bcs.latitude == 30.745
        assert updated_bcs.longitude == 76.795


def test_gps_validation_accepts_valid_sequential_movement(mock_user):
    setup_data = setup_operator_and_session(has_trip=True)
    mock_user.id = uuid.UUID(setup_data["user_id"])
    vehicle_id = uuid.UUID(setup_data["vehicle_id"])
    trip_id = uuid.UUID(setup_data["trip_id"])
    session_id = uuid.UUID(setup_data["session_id"])

    with Session(engine) as db_session:
        now = datetime.now(timezone.utc)

        # Initial state
        bcs = BusCurrentState(
            vehicle_id=vehicle_id,
            trip_id=trip_id,
            latitude=30.745,
            longitude=76.795,
            speed=10.0,
            state="LIVE",
            last_observed_at=now - timedelta(seconds=10),
            last_received_at=now - timedelta(seconds=10),
        )
        db_session.add(bcs)
        db_session.commit()

        # Move a realistic distance
        new_lat = 30.745 + 0.0009

        req = TrackingBatchRequest(
            session_id=session_id,
            packets=[
                TrackingPacketIn(
                    packet_id=uuid.uuid4(),
                    latitude=new_lat,
                    longitude=76.795,
                    accuracy_m=5.0,
                    speed_mps=10.0,
                    heading=0.0,
                    observed_at=now,
                    device_sequence=1,
                    battery_level=100.0,
                    network_type="WIFI",
                    gps_status="AVAILABLE",
                )
            ],
        )

        ingest_telemetry_batch(db_session, mock_user, req)

        db_session.expire_all()
        updated_bcs = db_session.get(BusCurrentState, vehicle_id)

        assert updated_bcs.latitude == new_lat
