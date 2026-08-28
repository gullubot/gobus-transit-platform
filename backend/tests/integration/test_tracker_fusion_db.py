import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import seed_dev_data, ORG_ID, VEH_IDS, SVC_AC4B_ID, ROUTE_R1_ID
from app.intelligence.core_models import (
    CanonicalStateContext,
    CanonicalState,
    DwellState,
)
from app.models.state import BusCurrentState
from app.models.enums import Direction, Confidence
from app.repositories.state_repository import upsert_canonical_state

@pytest.fixture
def db_session():
    with Session(engine) as session:
        yield session

@pytest.fixture
def seeded_db(db_session):
    seed_dev_data(db_session)
    db_session.execute(text("DELETE FROM bus_current_state"))
    db_session.commit()
    yield db_session


def test_db_01_canonical_write_and_speed_heading_dwell(seeded_db: Session):
    vehicle_id = VEH_IDS["PNB005234"]
    now = datetime.now(timezone.utc)
    
    ctx = CanonicalStateContext(
        vehicle_id=str(vehicle_id),
        trip_id=None,
        service_id=None,
        route_id=None,
        direction=None,
        lat=30.0,
        lon=76.0,
        speed_mps=15.5,
        heading=270.0,
        dwell_state=DwellState.MOVING,
        state=CanonicalState.LIVE,
        confidence="HIGH",
        canonical_source="dr",
        last_observed_at=now,
        last_received_at=now,
    )
    
    upsert_canonical_state(seeded_db, ctx)
    seeded_db.commit()
    
    row = seeded_db.execute(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)).scalar_one()
    assert row.speed == 15.5
    assert row.heading == 270.0
    assert row.dwell_state == DwellState.MOVING.value
    assert row.canonical_source == "dr"
    assert row.confidence == Confidence.HIGH
    assert row.state == "LIVE"


def test_db_02_nullable_speed_heading_dwell(seeded_db: Session):
    vehicle_id = VEH_IDS["PNB005234"]
    now = datetime.now(timezone.utc)
    
    ctx = CanonicalStateContext(
        vehicle_id=str(vehicle_id),
        lat=30.0,
        lon=76.0,
        speed_mps=None,
        heading=None,
        dwell_state=None,
        state=CanonicalState.LIVE,
        confidence="LOW",
        last_observed_at=now,
    )
    
    upsert_canonical_state(seeded_db, ctx)
    seeded_db.commit()
    
    row = seeded_db.execute(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)).scalar_one()
    assert row.speed is None
    assert row.heading is None
    assert row.dwell_state is None


def test_db_03_high_water_invariant(seeded_db: Session):
    vehicle_id = VEH_IDS["PNB005234"]
    now = datetime.now(timezone.utc)
    
    # Write canonical at 10:05
    ctx_10_05 = CanonicalStateContext(
        vehicle_id=str(vehicle_id),
        lat=30.0, lon=76.0, speed_mps=15.0, heading=90.0,
        canonical_source="dr", last_observed_at=now
    )
    upsert_canonical_state(seeded_db, ctx_10_05)
    seeded_db.commit()
    
    # Try to write older packet at 10:01
    ctx_10_01 = CanonicalStateContext(
        vehicle_id=str(vehicle_id),
        lat=31.0, lon=77.0, speed_mps=20.0, heading=100.0,
        canonical_source="co", last_observed_at=now - timedelta(minutes=4)
    )
    upsert_canonical_state(seeded_db, ctx_10_01)
    seeded_db.commit()
    
    # Verify it was rejected
    row = seeded_db.execute(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)).scalar_one()
    assert row.last_observed_at == now.replace(tzinfo=None)
    assert row.speed == 15.0
    assert row.canonical_source == "dr"
    
    # Now write 10:06
    ctx_10_06 = CanonicalStateContext(
        vehicle_id=str(vehicle_id),
        lat=32.0, lon=78.0, speed_mps=25.0, heading=110.0,
        canonical_source="co", last_observed_at=now + timedelta(minutes=1)
    )
    upsert_canonical_state(seeded_db, ctx_10_06)
    seeded_db.commit()
    
    # Verify it advanced
    row = seeded_db.execute(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)).scalar_one()
    assert row.last_observed_at == (now + timedelta(minutes=1)).replace(tzinfo=None)
    assert row.speed == 25.0
    assert row.canonical_source == "co"


def test_db_04_concurrency_race(seeded_db: Session):
    """
    Real PostgreSQL concurrency test.
    Transaction A: newer packet
    Transaction B: older packet
    """
    vehicle_id = VEH_IDS["PNB005234"]
    now = datetime.now(timezone.utc)
    
    # Seed a baseline so row exists (with_for_update needs a row, though upsert handles insert)
    baseline = CanonicalStateContext(vehicle_id=str(vehicle_id), last_observed_at=now - timedelta(minutes=10))
    upsert_canonical_state(seeded_db, baseline)
    seeded_db.commit()
    
    errs = []
    
    def tx_older():
        try:
            with Session(engine) as sess:
                ctx_older = CanonicalStateContext(
                    vehicle_id=str(vehicle_id), speed_mps=10.0,
                    last_observed_at=now - timedelta(minutes=5), canonical_source="old"
                )
                upsert_canonical_state(sess, ctx_older)
                time.sleep(0.1) # hold lock briefly
                sess.commit()
        except Exception as e:
            errs.append(e)
            
    def tx_newer():
        try:
            with Session(engine) as sess:
                ctx_newer = CanonicalStateContext(
                    vehicle_id=str(vehicle_id), speed_mps=20.0,
                    last_observed_at=now, canonical_source="new"
                )
                upsert_canonical_state(sess, ctx_newer)
                sess.commit()
        except Exception as e:
            errs.append(e)

    # If newer runs first and commits, older should be discarded by high-water.
    # If older runs first and commits, newer should overwrite it.
    # If they run concurrently, the lock ensures they are serialized, preventing lost updates.
    
    # Let's start both at the exact same time
    t1 = threading.Thread(target=tx_older)
    t2 = threading.Thread(target=tx_newer)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    if errs:
        raise errs[0]
    
    # The newer packet (now) must be the final state regardless of race
    row = seeded_db.execute(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)).scalar_one()
    assert row.last_observed_at == now.replace(tzinfo=None)
    assert row.speed == 20.0
    assert row.canonical_source == "new"

def test_db_05_dwell_state_enum(seeded_db: Session):
    vehicle_id = VEH_IDS["PNB005234"]
    for dwell in [DwellState.MOVING, DwellState.DWELL_AT_STOP, DwellState.DWELL_NON_STOP, DwellState.UNKNOWN]:
        ctx = CanonicalStateContext(
            vehicle_id=str(vehicle_id),
            dwell_state=dwell,
            last_observed_at=datetime.now(timezone.utc)
        )
        upsert_canonical_state(seeded_db, ctx)
        seeded_db.commit()
        
        row = seeded_db.execute(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)).scalar_one()
        assert row.dwell_state == dwell.value
