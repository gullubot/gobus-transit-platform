import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.service import Service
from app.models.route import Route
from app.models.vehicle import Vehicle
from app.models.trip import Trip
from app.models.crowding import CrowdingReport
from app.models.enums import CrowdingState, TripStatus, Direction, VehicleStatus, CrowdingSource
from app.services.insights_service import InsightsService
from app.db.database import engine

@pytest.fixture
def db():
    with Session(engine) as s:
        yield s

@pytest.fixture
def mock_org_data(db: Session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org Ins Svc {suffix}")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    route = Route(organization_id=org.id, route_code=f"RT_{suffix}", route_name="Route", geometry="SRID=4326;LINESTRING(0 0, 1 1)")
    db.add(route)
    db.commit()
    db.refresh(route)
    
    service = Service(organization_id=org.id, route_id=route.id, service_code=f"SVC_{suffix}", service_name="Service")
    db.add(service)
    db.commit()
    db.refresh(service)
    
    vehicle = Vehicle(organization_id=org.id, vehicle_number=f"V_{suffix}", vehicle_type="MINI_BUS", status=VehicleStatus.ACTIVE)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    
    return org, route, service, vehicle

def _create_trip(db, org_id, service_id, route_id, vehicle_id, status=TripStatus.COMPLETED, delay_mins=0):
    start = datetime.now(timezone.utc) - timedelta(days=1, minutes=delay_mins)
    actual = datetime.now(timezone.utc) - timedelta(days=1)
    t = Trip(
        organization_id=org_id,
        service_id=service_id,
        route_id=route_id,
        vehicle_id=vehicle_id,
        direction=Direction.A_TO_B,
        operating_date=start.date(),
        planned_start_at=start,
        actual_start_at=actual if status == TripStatus.COMPLETED else None,
        status=status
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def test_crowding_insight_thresholds(db: Session, mock_org_data):
    org, route, service, vehicle = mock_org_data
    insights_service = InsightsService(db, org.id)
    
    trip = _create_trip(db, org.id, service.id, route.id, vehicle.id)
    
    # Insert 4 high reports (below min 5)
    for _ in range(4):
        cr = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=org.id,
            vehicle_id=vehicle.id,
            trip_id=trip.id,
            crowding_state=CrowdingState.FULL,
            confidence=1.0,
            source_type=CrowdingSource.PASSENGER,
            observed_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.add(cr)
    db.commit()
    
    insights = insights_service.analyze_recurring_crowding()
    assert len(insights) == 0
    
    # Add 2 more low reports (total 6, high 4 -> 66% HIGH/FULL)
    for _ in range(2):
        cr = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=org.id,
            vehicle_id=vehicle.id,
            trip_id=trip.id,
            crowding_state=CrowdingState.LOW,
            confidence=1.0,
            source_type=CrowdingSource.PASSENGER,
            observed_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.add(cr)
    db.commit()
    
    insights = insights_service.analyze_recurring_crowding()
    assert len(insights) == 1
    assert insights[0].insight_type == "CROWDING"
    assert insights[0].evidence.total_observations == 6
    assert insights[0].evidence.matched_observations == 4
    
    # Add 4 more low reports (total 10, high 4 -> 40% HIGH/FULL)
    for _ in range(4):
        cr = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=org.id,
            vehicle_id=vehicle.id,
            trip_id=trip.id,
            crowding_state=CrowdingState.LOW,
            confidence=1.0,
            source_type=CrowdingSource.PASSENGER,
            observed_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.add(cr)
    db.commit()
    
    insights = insights_service.analyze_recurring_crowding()
    assert len(insights) == 0


def test_performance_delay_insight(db: Session, mock_org_data):
    org, route, service, vehicle = mock_org_data
    insights_service = InsightsService(db, org.id)
    
    # Add 5 delayed trips (20 mins late)
    for _ in range(5):
        _create_trip(db, org.id, service.id, route.id, vehicle.id, status=TripStatus.COMPLETED, delay_mins=20)
    db.commit()
    
    insights = insights_service.analyze_service_performance()
    assert len(insights) == 1
    assert insights[0].insight_type == "PERFORMANCE"
    assert insights[0].evidence.matched_observations == 5


def test_missed_trips_insight(db: Session, mock_org_data):
    org, route, service, vehicle = mock_org_data
    insights_service = InsightsService(db, org.id)
    
    # Add 8 completed, 3 cancelled (total 11, 27% cancelled)
    for _ in range(8):
        _create_trip(db, org.id, service.id, route.id, vehicle.id, status=TripStatus.COMPLETED)
    for _ in range(3):
        _create_trip(db, org.id, service.id, route.id, vehicle.id, status=TripStatus.CANCELLED)
    db.commit()
    
    insights = insights_service.analyze_missed_trips()
    assert len(insights) == 1
    assert insights[0].insight_type == "PERFORMANCE"
    assert insights[0].evidence.total_observations == 11
    assert insights[0].evidence.matched_observations == 3


def test_fleet_capacity_insight(db: Session, mock_org_data):
    org, route, service, vehicle = mock_org_data # vehicle is MINI_BUS
    insights_service = InsightsService(db, org.id)
    
    trip = _create_trip(db, org.id, service.id, route.id, vehicle.id)
    
    # Insert 6 high reports for MINI_BUS
    for _ in range(6):
        cr = CrowdingReport(
            report_id=uuid.uuid4(),
            organization_id=org.id,
            vehicle_id=vehicle.id,
            trip_id=trip.id,
            crowding_state=CrowdingState.FULL,
            confidence=1.0,
            source_type=CrowdingSource.PASSENGER,
            observed_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.add(cr)
    db.commit()
    
    insights = insights_service.analyze_fleet_capacity()
    assert len(insights) == 1
    assert insights[0].insight_type == "FLEET"
    assert "lower-capacity" in insights[0].evidence.statement
