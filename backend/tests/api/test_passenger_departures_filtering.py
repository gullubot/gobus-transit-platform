import uuid
from datetime import datetime, time, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.main import app
from app.db.database import engine
from app.models.organization import Organization
from app.models.route import Route, Stop, RouteStop
from app.models.service import Service, ServiceSchedule
from app.models.enums import Direction

client = TestClient(app)

@pytest.fixture
def org_service_and_stop():
    uid = str(uuid.uuid4())[:8]
    with Session(engine) as session:
        # Create Organization
        org = Organization(name=f"Test Dep Org {uid}")
        session.add(org)
        session.commit()

        # Create Route
        route = Route(
            organization_id=org.id,
            route_code=f"DEP-{uid}",
            route_name="Dep Route",
            geometry="LINESTRING(88.3639 22.5726, 88.4000 22.5800)",
        )
        session.add(route)
        session.commit()

        # Create Stops
        stop1 = Stop(
            organization_id=org.id,
            stop_code=f"S1-{uid}",
            name="Stop 1",
            location="POINT(88.3639 22.5726)"
        )
        session.add(stop1)
        session.commit()

        # Create RouteStop
        rs1 = RouteStop(
            route_id=route.id,
            stop_id=stop1.id,
            sequence_number=1,
            nominal_travel_time_seconds=0
        )
        session.add(rs1)
        session.commit()

        # Create Service
        service = Service(
            organization_id=org.id,
            route_id=route.id,
            service_code=f"SRV-{uid}",
            service_name="Dep Service",
        )
        session.add(service)
        session.commit()

        # Create ServiceSchedule
        sch = ServiceSchedule(
            service_id=service.id,
            direction=Direction.A_TO_B,
            start_time=time(6, 0),
            end_time=time(22, 0),
            typical_interval_minutes=15,
            days_of_week=[0,1,2,3,4,5,6]
        )
        session.add(sch)
        session.commit()

        yield org, service, stop1

def test_get_departures_filtering(org_service_and_stop):
    org, service, stop = org_service_and_stop
    
    # 1. No filters
    resp = client.get(
        f"/api/passenger/stops/{stop.id}/departures",
        params={"organization_id": str(org.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    base_len = len(data)

    # 2. service_id filter
    resp2 = client.get(
        f"/api/passenger/stops/{stop.id}/departures",
        params={
            "organization_id": str(org.id),
            "service_id": str(service.id)
        },
    )
    assert resp2.status_code == 200
    assert len(resp2.json()) == base_len

    # Invalid service_id
    resp3 = client.get(
        f"/api/passenger/stops/{stop.id}/departures",
        params={
            "organization_id": str(org.id),
            "service_id": str(uuid.uuid4())
        },
    )
    assert resp3.status_code == 200
    assert len(resp3.json()) == 0

    # 3. direction filter (valid)
    resp4 = client.get(
        f"/api/passenger/stops/{stop.id}/departures",
        params={
            "organization_id": str(org.id),
            "direction": "A_TO_B"
        },
    )
    assert resp4.status_code == 200
    assert len(resp4.json()) == base_len

    # direction filter (invalid/other direction)
    resp5 = client.get(
        f"/api/passenger/stops/{stop.id}/departures",
        params={
            "organization_id": str(org.id),
            "direction": "B_TO_A"
        },
    )
    assert resp5.status_code == 200
    assert len(resp5.json()) == 0

    # 4. Both filters
    resp6 = client.get(
        f"/api/passenger/stops/{stop.id}/departures",
        params={
            "organization_id": str(org.id),
            "service_id": str(service.id),
            "direction": "A_TO_B"
        },
    )
    assert resp6.status_code == 200
    assert len(resp6.json()) == base_len

