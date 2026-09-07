import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.main import app
from app.db.database import engine
from app.models.organization import Organization
from app.models.route import Route, Stop, RouteStop
from app.models.service import Service, ServiceSchedule
from app.models.enums import Direction

client = TestClient(app)



@pytest.fixture
def org_and_service():
    uid = str(uuid.uuid4())[:8]
    with Session(engine) as session:
        # Create Organization
        org = Organization(name=f"Test Geometry Org {uid}")
        session.add(org)
        session.commit()
        session.refresh(org)

        # Create Stops
        stop1 = Stop(organization_id=org.id, stop_code=f"STP1-{uid}", name="Stop One", latitude=22.1, longitude=88.1, location="POINT(88.1 22.1)")
        stop2 = Stop(organization_id=org.id, stop_code=f"STP2-{uid}", name="Stop Two", latitude=22.2, longitude=88.2, location="POINT(88.2 22.2)")
        session.add_all([stop1, stop2])
        session.commit()

        # Create Route
        route = Route(organization_id=org.id, route_code=f"GEO1-{uid}", route_name="Geo Route", geometry="LINESTRING(88.1 22.1, 88.2 22.2)")
        session.add(route)
        session.commit()

        # Create Route Stops
        rs1 = RouteStop(route_id=route.id, stop_id=stop1.id, sequence_number=1, distance_from_start=0)
        rs2 = RouteStop(route_id=route.id, stop_id=stop2.id, sequence_number=2, distance_from_start=10)
        session.add_all([rs1, rs2])

        # Create Service
        service = Service(organization_id=org.id, route_id=route.id, service_code=f"S-GEO-{uid}", service_name="Service Geo")
        session.add(service)
        session.commit()
        
        # Create Schedule
        sched = ServiceSchedule(service_id=service.id, direction=Direction.A_TO_B, start_time="08:00:00", end_time="20:00:00", typical_interval_minutes=15)
        session.add(sched)
        session.commit()
        
        session.refresh(service)
        session.refresh(org)
        return org, service

def test_service_detail_contains_geometry_and_stop_coords(org_and_service):
    org, service = org_and_service

    response = client.get(
        f"/api/passenger/services/{service.id}?organization_id={org.id}"
    )
    assert response.status_code == 200
    data = response.json()

    # Verify route geometry is exposed
    assert "route_geometry" in data
    assert data["route_geometry"] is not None
    assert data["route_geometry"]["type"] == "LineString"
    
    # Verify stop ordering and coordinates
    stops = data["stops"]
    assert len(stops) == 2
    
    # Ensure correct ordering
    assert stops[0]["sequence_number"] == 1
    assert stops[1]["sequence_number"] == 2
    
    # Ensure coordinates and name exist
    assert stops[0]["stop_name"] == "Stop One"
    assert stops[0]["latitude"] == 22.1
    assert stops[0]["longitude"] == 88.1

    assert stops[1]["stop_name"] == "Stop Two"
    assert stops[1]["latitude"] == 22.2
    assert stops[1]["longitude"] == 88.2

def test_organization_scoping_remains_enforced(org_and_service):
    org, service = org_and_service
    fake_org_id = uuid.uuid4()
    
    response = client.get(
        f"/api/passenger/services/{service.id}?organization_id={fake_org_id}"
    )
    assert response.status_code == 404
