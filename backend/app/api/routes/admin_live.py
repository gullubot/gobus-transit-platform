from datetime import date
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from app.api.deps import get_db, get_current_admin
from app.models.user import User
from app.models.state import BusCurrentState
from app.models.vehicle import Vehicle
from app.models.service import Service, DepotSchedule
from app.models.route import Route, Stop
from app.schemas.admin_live import AdminLiveOperationResponse

router = APIRouter()

@router.get("/operations/live", response_model=List[AdminLiveOperationResponse])
def get_live_operations(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get live operations state for the authenticated admin's organization.
    Authoritative state is pulled from BusCurrentState, joined with Vehicle
    to enforce organization isolation.
    """
    org_id = current_admin.organization_id

    # Base query for BusCurrentState, heavily joined for contextual details
    stmt = (
        select(
            BusCurrentState,
            Vehicle,
            Service,
            Route,
            Stop.name.label("current_stop_name"),
            # We need to alias Stop for next_stop
        )
        .join(Vehicle, BusCurrentState.vehicle_id == Vehicle.id)
        .outerjoin(Service, BusCurrentState.service_id == Service.id)
        .outerjoin(Route, BusCurrentState.route_id == Route.id)
        .outerjoin(Stop, BusCurrentState.current_stop_id == Stop.id)
        .where(Vehicle.organization_id == org_id)
    )
    
    # Execute base state query
    results = db.execute(stmt).all()

    # To get next_stop_name, we can either do another alias join or batch fetch
    # Since we also need DepotSchedule for today, let's batch fetch related entities
    # to avoid overly complex SQLAlchemy aliases for MVP.
    
    # Collect IDs for batch fetches
    next_stop_ids = {r[0].next_stop_id for r in results if r[0].next_stop_id}
    vehicle_ids = {r[1].id for r in results}

    # Fetch next stops
    next_stops = {}
    if next_stop_ids:
        stop_stmt = select(Stop.id, Stop.name).where(Stop.id.in_(next_stop_ids))
        for sid, sname in db.execute(stop_stmt).all():
            next_stops[sid] = sname
            
    # Fetch today's depot schedules for these vehicles (including recurring daily schedules)
    today = date.today()
    schedules = {}
    if vehicle_ids:
        sched_stmt = select(DepotSchedule).where(
            and_(
                DepotSchedule.vehicle_id.in_(vehicle_ids),
                or_(
                    DepotSchedule.operating_date == today,
                    and_(
                        DepotSchedule.source == "RECURRING_DAILY",
                        DepotSchedule.operating_date <= today,
                        DepotSchedule.status != "CANCELLED",
                    ),
                ),
            )
        )
        for sched in db.scalars(sched_stmt).all():
            # Keep the latest or most relevant schedule per vehicle
            schedules[sched.vehicle_id] = sched

    response_list = []
    
    for row in results:
        bcs: BusCurrentState = row[0]
        veh: Vehicle = row[1]
        svc: Service = row[2]
        rt: Route = row[3]
        current_stop_name = row[4]
        
        sched = schedules.get(veh.id)

        response_list.append({
            "vehicle_id": str(veh.id),
            "vehicle_number": veh.vehicle_number,
            "registration_number": veh.registration_number,
            "vehicle_type": veh.vehicle_type,
            "vehicle_status": veh.status,
            
            "service_id": str(svc.id) if svc else None,
            "service_name": svc.service_name if svc else None,
            "route_id": str(rt.id) if rt else None,
            "route_name": rt.route_name if rt else None,
            "direction": bcs.direction,
            
            "current_stop_id": str(bcs.current_stop_id) if bcs.current_stop_id else None,
            "current_stop_name": current_stop_name,
            "next_stop_id": str(bcs.next_stop_id) if bcs.next_stop_id else None,
            "next_stop_name": next_stops.get(bcs.next_stop_id),
            
            "latitude": bcs.latitude,
            "longitude": bcs.longitude,
            "speed": bcs.speed,
            "heading": bcs.heading,
            "route_progress": bcs.route_progress,
            "dwell_state": bcs.dwell_state,
            
            "eta_seconds": bcs.eta_seconds,
            "eta_status": bcs.eta_status,
            
            "state": bcs.state,
            "state_reason": bcs.state_reason,
            "confidence": bcs.confidence,
            "last_observed_at": bcs.last_observed_at,
            
            "scheduled_status": sched.status if sched else None,
            "planned_departure": sched.planned_departure if sched else None,
        })
        
    return response_list
