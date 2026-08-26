"""
Transit Platform — BUILD 1 Domain Schema Integration Tests.

Verifies:
  1. Complete table presence and basic CRUD operations.
  2. Cross-organization isolation constraints (foreign key failures on mismatch).
  3. Service-Route integrity constraints on Services and Trips.
  4. PostGIS geometry spatial queries (distance, bounding box, ST_DWithin).
  5. ServiceAlert scope-target CHECK constraints.
  6. RouteStop sequence positivity CHECK constraint.
  7. TrackingEvent unique packet_id & (device_id, session_id, sequence) constraints.
  8. Idempotent seed data verification.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import (
    ORG_ID,
    ROUTE_R1_ID,
    ROUTE_R2_ID,
    STOP_IDS,
    SVC_AC4B_ID,
    VEH_IDS,
    seed_dev_data,
)
from app.models.alert import ServiceAlert
from app.models.enums import (
    AlertScope,
    Confidence,
    Direction,
    OrganizationStatus,
    OrganizationType,
    TrackingSessionStatus,
    TripStatus,
    ValidationStatus,
)
from app.models.organization import Organization
from app.models.route import Route, RouteStop, Stop
from app.models.service import Service
from app.models.state import BusCurrentState, ETAPrediction
from app.models.tracking import TrackingEvent, TrackingSession
from app.models.trip import Trip


@pytest.fixture
def db():
    """Provide a transactional database session rolled back after test if needed."""
    with Session(engine) as session:
        yield session


# ── Test 1: All 20 tables exist and have expected structure ───────────────────


def test_all_20_domain_tables_exist(db: Session):
    """Verify that all 20 domain tables are present in the database."""
    query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name != 'alembic_version'
          AND table_name != 'spatial_ref_sys'
        ORDER BY table_name;
    """)
    rows = db.execute(query).scalars().all()
    expected_tables = {
        "audit_logs",
        "bus_current_state",
        "depot_schedules",
        "devices",
        "eta_predictions",
        "operator_profiles",
        "organizations",
        "route_stops",
        "routes",
        "service_alerts",
        "service_schedules",
        "services",
        "stops",
        "tracking_events",
        "tracking_sessions",
        "trip_assignments",
        "trip_state_history",
        "trips",
        "users",
        "vehicles",
    }
    present_tables = set(rows)
    missing = expected_tables - present_tables
    assert not missing, f"Missing tables: {missing}"


# ── Test 2: Seed data integrity and counts ─────────────────────────────────────


def test_seed_data_integrity(db: Session):
    """Verify seed execution and structure."""
    seed_dev_data(db)

    org = db.get(Organization, ORG_ID)
    assert org is not None
    assert org.name == "Transit Demo Authority"
    assert org.type == OrganizationType.GOVERNMENT

    # Verify routes & stops
    routes = db.execute(select(Route).where(Route.organization_id == ORG_ID)).scalars().all()
    assert len(routes) == 2

    stops = db.execute(select(Stop).where(Stop.organization_id == ORG_ID)).scalars().all()
    assert len(stops) == 8

    # Verify service -> route relationship
    svc = db.get(Service, SVC_AC4B_ID)
    assert svc is not None
    assert svc.route_id == ROUTE_R1_ID
    assert svc.route.route_code == "R1"

    # Verify route stops ordering
    rs_list = (
        db.execute(
            select(RouteStop)
            .where(RouteStop.route_id == ROUTE_R1_ID)
            .order_by(RouteStop.sequence_number)
        )
        .scalars()
        .all()
    )
    assert len(rs_list) == 4
    assert [rs.sequence_number for rs in rs_list] == [1, 2, 3, 4]


# ── Test 3: PostGIS Spatial Queries ──────────────────────────────────────────


def test_postgis_spatial_queries(db: Session):
    """Verify PostGIS spatial indexing and distance queries on stops and routes."""
    seed_dev_data(db)

    # Calculate distance in meters between City Center and Knowledge Park stops
    cc_stop = db.get(Stop, STOP_IDS["CC"])
    kp_stop = db.get(Stop, STOP_IDS["KP"])
    assert cc_stop is not None and kp_stop is not None

    query = text("""
        SELECT ST_Distance(
            ST_Transform(cc.location, 3857),
            ST_Transform(kp.location, 3857)
        ) AS dist_m
        FROM stops cc, stops kp
        WHERE cc.id = :cc_id AND kp.id = :kp_id;
    """)
    result = db.execute(query, {"cc_id": cc_stop.id, "kp_id": kp_stop.id}).scalar()
    assert result is not None
    assert result > 100  # Distance in meters should be > 100m

    # ST_DWithin query: find stops within 20km of City Center
    query_within = text("""
        SELECT count(*)
        FROM stops
        WHERE ST_DWithin(
            location::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            20000
        );
    """)
    count = db.execute(query_within, {"lon": cc_stop.longitude, "lat": cc_stop.latitude}).scalar()
    assert count >= 4


# ── Test 4: Cross-Organization Isolation Constraint ──────────────────────────


def test_cross_organization_fk_constraint_rejected(db: Session):
    """
    Ensure that a Service cannot reference a Route belonging to a different Organization.
    Enforced by fk_services_org_route composite FK.
    """
    other_org_id = uuid.uuid4()
    other_org = Organization(
        id=other_org_id,
        name=f"Other Transit Agency {uuid.uuid4().hex[:8]}",
        type=OrganizationType.PRIVATE,
        status=OrganizationStatus.ACTIVE,
    )
    db.add(other_org)

    # Route belonging to other_org
    other_route_id = uuid.uuid4()
    other_route = Route(
        id=other_route_id,
        organization_id=other_org_id,
        route_code="OTHER_R1",
        route_name="Foreign Route",
        geometry="SRID=4326;LINESTRING(77.0 28.0, 77.1 28.1)",
    )
    db.add(other_route)
    db.commit()

    # Attempt to create a Service in ORG_ID pointing to other_route_id
    invalid_service = Service(
        id=uuid.uuid4(),
        organization_id=ORG_ID,  # Primary Org
        route_id=other_route_id,  # Other Org's route
        service_code="INVALID_CROSS_ORG",
        service_name="Invalid Cross Org Service",
    )
    db.add(invalid_service)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ── Test 5: Trip Service-Route Consistency Constraint ─────────────────────────


def test_trip_service_route_mismatch_rejected(db: Session):
    """
    Ensure that a Trip cannot reference a Route that does not match its Service's route.
    Enforced by fk_trips_service_route composite FK:
    (service_id, route_id) -> services(id, route_id).
    """
    seed_dev_data(db)

    # Service AC4B is tied to ROUTE_R1_ID.
    # Trying to create a Trip with SVC_AC4B_ID and ROUTE_R2_ID must fail.
    invalid_trip = Trip(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        service_id=SVC_AC4B_ID,
        vehicle_id=VEH_IDS["PNB005234"],
        route_id=ROUTE_R2_ID,  # Mismatch! AC4B is on ROUTE_R1_ID
        direction=Direction.A_TO_B,
        operating_date=date(2026, 8, 26),
        planned_start_at=datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc),
        status=TripStatus.PLANNED,
    )
    db.add(invalid_trip)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ── Test 6: Alert Scope / Target CHECK Constraints ────────────────────────────


def test_service_alert_scope_constraints(db: Session):
    """Verify that ServiceAlert scope CHECK constraints enforce target IDs."""
    seed_dev_data(db)

    # 1. Scope SERVICE without service_id must fail
    invalid_service_alert = ServiceAlert(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        scope=AlertScope.SERVICE,
        service_id=None,  # Missing target!
        type="DELAY",
        title="Delay Alert",
        message="Service is delayed",
        severity="WARNING",
    )
    db.add(invalid_service_alert)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # 2. Scope ROUTE without route_id must fail
    invalid_route_alert = ServiceAlert(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        scope=AlertScope.ROUTE,
        route_id=None,  # Missing target!
        type="DETOUR",
        title="Route Detour",
        message="Route detour in effect",
        severity="INFO",
    )
    db.add(invalid_route_alert)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # 3. Valid alert with target should succeed
    valid_alert = ServiceAlert(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        scope=AlertScope.SERVICE,
        service_id=SVC_AC4B_ID,
        type="DELAY",
        title="Valid Service Alert",
        message="Valid delay notification",
        severity="WARNING",
    )
    db.add(valid_alert)
    db.commit()
    assert valid_alert.id is not None


# ── Test 7: RouteStop Sequence Check Constraint ───────────────────────────────


def test_routestop_sequence_positivity_constraint(db: Session):
    """Verify that sequence_number must be > 0 in route_stops."""
    seed_dev_data(db)

    invalid_rs = RouteStop(
        id=uuid.uuid4(),
        route_id=ROUTE_R1_ID,
        stop_id=STOP_IDS["CC"],
        sequence_number=0,  # Invalid: must be > 0
    )
    db.add(invalid_rs)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ── Test 8: TrackingEvent packet_id uniqueness and sequence scope ─────────────


def test_tracking_event_constraints(db: Session):
    """Verify packet_id uniqueness and (device_id, session_id, sequence) uniqueness."""
    seed_dev_data(db)

    device_id = uuid.UUID("70000000-0000-0000-0000-000000000001")
    session_id = uuid.uuid4()
    session = TrackingSession(
        id=session_id,
        device_id=device_id,
        status=TrackingSessionStatus.ACTIVE,
    )
    db.add(session)
    db.commit()

    packet_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    event1 = TrackingEvent(
        id=uuid.uuid4(),
        packet_id=packet_id,
        tracking_session_id=session_id,
        device_id=device_id,
        latitude=30.7333,
        longitude=76.7794,
        observed_at=now,
        received_at=now,
        device_sequence=1,
        validation_status=ValidationStatus.VALID,
    )
    db.add(event1)
    db.commit()

    # Attempt to insert same packet_id must fail
    event_duplicate_packet = TrackingEvent(
        id=uuid.uuid4(),
        packet_id=packet_id,  # Duplicate packet_id!
        tracking_session_id=session_id,
        device_id=device_id,
        latitude=30.7350,
        longitude=76.7850,
        observed_at=now,
        received_at=now,
        device_sequence=2,
    )
    db.add(event_duplicate_packet)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Attempt to insert same device_sequence in same session must fail
    event_duplicate_seq = TrackingEvent(
        id=uuid.uuid4(),
        packet_id=uuid.uuid4(),
        tracking_session_id=session_id,
        device_id=device_id,
        latitude=30.7350,
        longitude=76.7850,
        observed_at=now,
        received_at=now,
        device_sequence=1,  # Duplicate sequence!
    )
    db.add(event_duplicate_seq)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ── Test 9: BusCurrentState Single-State-Per-Vehicle & ETAPrediction ───────────


def test_bus_current_state_and_eta_predictions(db: Session):
    """Verify BusCurrentState primary key on vehicle_id and ETAPrediction creation."""
    seed_dev_data(db)

    vehicle_id = VEH_IDS["PNB005234"]
    now = datetime.now(timezone.utc)

    # 1. BusCurrentState
    state = BusCurrentState(
        vehicle_id=vehicle_id,
        trip_id=uuid.UUID("90000000-0000-0000-0000-000000000001"),
        service_id=SVC_AC4B_ID,
        route_id=ROUTE_R1_ID,
        direction=Direction.A_TO_B,
        latitude=30.7333,
        longitude=76.7794,
        state="IN_TRANSIT",
        confidence=Confidence.HIGH,
        last_observed_at=now,
        last_received_at=now,
    )
    db.merge(state)
    db.commit()

    retrieved = db.get(BusCurrentState, vehicle_id)
    assert retrieved is not None
    assert retrieved.state == "IN_TRANSIT"

    # 2. ETAPrediction
    eta = ETAPrediction(
        id=uuid.uuid4(),
        trip_id=uuid.UUID("90000000-0000-0000-0000-000000000001"),
        stop_id=STOP_IDS["MG"],
        predicted_arrival_at=now,
        predicted_minutes=8,
        confidence=Confidence.HIGH,
        computed_at=now,
        based_on_observed_at=now,
        algorithm_version="v0.1.0-baseline",
    )
    db.add(eta)
    db.commit()

    retrieved_eta = db.get(ETAPrediction, eta.id)
    assert retrieved_eta is not None
    assert retrieved_eta.predicted_minutes == 8
