from datetime import date, datetime, time, timezone
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select, or_, and_, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_db, get_current_admin
from app.models.user import User, OperatorProfile
from app.models.vehicle import Vehicle
from app.models.service import DepotSchedule, Service
from app.models.service_vehicle import ServiceVehicle
from app.models.route import Route, RouteStop, Stop
from app.models.enums import VehicleStatus, Direction, TripStatus, AssignmentStatus, UserRole
from app.models.trip import Trip, TripAssignment
from app.schemas.admin_fleet import (
    VehicleCreate, VehicleUpdate, VehicleResponse,
    VehicleCrewAssignmentRequest, VehicleCrewAssignmentResponse,
    PersonnelSummary, ServiceSummary, VehicleSummary,
    DepotScheduleCreate, DepotScheduleUpdate, DepotScheduleResponse,
    FleetScheduleItemResponse, FleetScheduleCreateRequest, FleetScheduleUpdateRequest,
    MajorDepotResponse, DepotDepartureItemResponse,
    ServiceVehicleAssignRequest, ServiceVehicleResponse, AvailableVehicleOption,
)


router = APIRouter()

# -------------------------------------------------------------------------
# CREW HELPER
# -------------------------------------------------------------------------

def _get_vehicle_active_crew(
    db: Session,
    org_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    service_id: Optional[uuid.UUID] = None,
) -> tuple[Optional[PersonnelSummary], Optional[PersonnelSummary], Optional[ServiceSummary]]:
    """
    Finds the active or latest planned operational Trip for this vehicle
    (filtered by service_id if provided) and returns:
    (driver_summary, conductor_summary, service_summary).
    """
    trip_stmt = select(Trip).where(
        Trip.organization_id == org_id,
        Trip.vehicle_id == vehicle_id,
        Trip.status.in_([TripStatus.PLANNED, TripStatus.ACTIVE]),
    )
    if service_id:
        trip_stmt = trip_stmt.where(Trip.service_id == service_id)
    trip_stmt = trip_stmt.order_by(Trip.operating_date.desc(), Trip.created_at.desc())

    trip = db.execute(trip_stmt).scalars().first()

    driver_summary: Optional[PersonnelSummary] = None
    conductor_summary: Optional[PersonnelSummary] = None
    service_summary: Optional[ServiceSummary] = None

    target_service_id = service_id or (trip.service_id if trip else None)
    if not target_service_id:
        has_sv = inspect(db.bind).has_table("service_vehicles")
        if has_sv:
            sv = db.execute(
                select(ServiceVehicle).where(
                    ServiceVehicle.vehicle_id == vehicle_id,
                    ServiceVehicle.organization_id == org_id,
                    ServiceVehicle.status == "ACTIVE",
                ).order_by(ServiceVehicle.assigned_at.desc())
            ).scalars().first()
            if sv:
                target_service_id = sv.service_id

        if not target_service_id:
            # Fallback to DepotSchedule
            ds = db.execute(
                select(DepotSchedule).where(
                    DepotSchedule.vehicle_id == vehicle_id,
                    DepotSchedule.status != "CANCELLED",
                ).order_by(DepotSchedule.operating_date.desc(), DepotSchedule.created_at.desc())
            ).scalars().first()
            if ds:
                target_service_id = ds.service_id

    if target_service_id:
        svc = db.execute(
            select(Service).where(
                Service.id == target_service_id,
                Service.organization_id == org_id,
            )
        ).scalar_one_or_none()
        if svc:
            service_summary = ServiceSummary(
                id=svc.id,
                service_code=svc.service_code,
                service_name=svc.service_name,
                route_id=svc.route_id,
            )

    if trip:
        assigns = db.execute(
            select(TripAssignment).where(
                TripAssignment.trip_id == trip.id,
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
        ).scalars().all()

        for assign in assigns:
            user = db.get(User, assign.user_id)
            if user and user.organization_id == org_id:
                op = db.execute(
                    select(OperatorProfile).where(OperatorProfile.user_id == user.id)
                ).scalar_one_or_none()
                emp_code = op.employee_code if op else None

                summary = PersonnelSummary(
                    id=user.id,
                    name=user.name,
                    employee_code=emp_code,
                    role=user.role.value if hasattr(user.role, "value") else str(user.role),
                    phone=user.phone,
                    email=user.email,
                )

                if assign.role == "DRIVER" and not driver_summary:
                    driver_summary = summary
                elif assign.role == "CONDUCTOR" and not conductor_summary:
                    conductor_summary = summary

    return driver_summary, conductor_summary, service_summary


# -------------------------------------------------------------------------
# VEHICLES
# -------------------------------------------------------------------------

@router.get("/vehicles", response_model=list[VehicleResponse])
def get_vehicles(
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
    service_id: Optional[uuid.UUID] = None
):
    stmt = select(Vehicle).where(Vehicle.organization_id == current_admin.organization_id)
    if service_id:
        has_sv = inspect(db.bind).has_table("service_vehicles")
        legacy_depot_subq = select(DepotSchedule.vehicle_id).where(
            DepotSchedule.service_id == service_id
        )
        legacy_trip_subq = select(Trip.vehicle_id).where(
            Trip.service_id == service_id,
            Trip.organization_id == current_admin.organization_id,
        )

        if has_sv:
            # Guardrail 2 Precedence:
            # 1. Authoritative: Active ServiceVehicle membership
            active_membership_subq = select(ServiceVehicle.vehicle_id).where(
                ServiceVehicle.service_id == service_id,
                ServiceVehicle.organization_id == current_admin.organization_id,
                ServiceVehicle.status == "ACTIVE",
            )
            # 2. All explicit ServiceVehicle records for this service
            explicit_service_vehicle_subq = select(ServiceVehicle.vehicle_id).where(
                ServiceVehicle.service_id == service_id,
                ServiceVehicle.organization_id == current_admin.organization_id,
            )
            # 3. Fallback: only applies if NO ServiceVehicle row exists for this service (status != INACTIVE),
            # and legacy evidence exists (DepotSchedule even if CANCELLED, or Trip).
            fallback_condition = and_(
                Vehicle.id.not_in(explicit_service_vehicle_subq),
                or_(
                    Vehicle.id.in_(legacy_depot_subq),
                    Vehicle.id.in_(legacy_trip_subq),
                ),
            )
            stmt = stmt.where(or_(Vehicle.id.in_(active_membership_subq), fallback_condition))
        else:
            stmt = stmt.where(or_(Vehicle.id.in_(legacy_depot_subq), Vehicle.id.in_(legacy_trip_subq)))

    vehicles = db.execute(stmt.order_by(Vehicle.created_at.desc())).scalars().all()
    
    responses = []
    for veh in vehicles:
        resp = VehicleResponse.model_validate(veh)
        driver, conductor, service_summary = _get_vehicle_active_crew(
            db, current_admin.organization_id, veh.id, service_id
        )
        resp.driver = driver
        resp.conductor = conductor
        resp.service = service_summary
        responses.append(resp)
    return responses


@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
    service_id: Optional[uuid.UUID] = None,
):
    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    resp = VehicleResponse.model_validate(vehicle)
    driver, conductor, service_summary = _get_vehicle_active_crew(
        db, current_admin.organization_id, vehicle.id, service_id
    )
    resp.driver = driver
    resp.conductor = conductor
    resp.service = service_summary
    return resp


@router.get("/vehicles/{vehicle_id}/crew", response_model=VehicleCrewAssignmentResponse)
def get_vehicle_crew(
    vehicle_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
    service_id: Optional[uuid.UUID] = None,
):
    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    driver, conductor, service_summary = _get_vehicle_active_crew(
        db, current_admin.organization_id, vehicle.id, service_id
    )
    effective_service_id = service_id or (service_summary.id if service_summary else None)
    if not effective_service_id:
        ds = db.execute(
            select(DepotSchedule).where(
                DepotSchedule.vehicle_id == vehicle.id,
                DepotSchedule.status != "CANCELLED",
            ).order_by(DepotSchedule.operating_date.desc(), DepotSchedule.created_at.desc())
        ).scalars().first()
        if ds:
            effective_service_id = ds.service_id
        else:
            raise HTTPException(status_code=400, detail="Vehicle is not associated with any service")

    return VehicleCrewAssignmentResponse(
        vehicle_id=vehicle.id,
        service_id=effective_service_id,
        driver=driver,
        conductor=conductor,
        updated_at=datetime.now(timezone.utc),
    )


@router.post("/vehicles/{vehicle_id}/crew", response_model=VehicleCrewAssignmentResponse)
def assign_vehicle_crew(
    vehicle_id: uuid.UUID,
    payload: VehicleCrewAssignmentRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
):
    """
    Authoritative assignment of Driver and Conductor to a Vehicle for an active Service.
    Reuses an existing active/planned Trip or creates one if required.
    Validates tenant isolation and personnel roles.
    """
    org_id = current_admin.organization_id

    # 1. Authorize & lock Vehicle
    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.organization_id == org_id).with_for_update()
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # 2. Authorize Service
    service = db.execute(
        select(Service).where(Service.id == payload.service_id, Service.organization_id == org_id)
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=400, detail="Service not found or does not belong to your organization")

    # 3. Deterministic row-level locking for personnel (sorted by UUID to prevent lock-order deadlocks)
    personnel_ids = sorted([uid for uid in [payload.driver_id, payload.conductor_id] if uid is not None])
    locked_users: dict[uuid.UUID, User] = {}
    for uid in personnel_ids:
        u = db.execute(
            select(User).where(User.id == uid, User.organization_id == org_id).with_for_update()
        ).scalar_one_or_none()
        if not u:
            role_desc = "Driver" if uid == payload.driver_id else "Conductor"
            raise HTTPException(status_code=400, detail=f"{role_desc} not found or does not belong to your organization")
        locked_users[uid] = u

    # Validate Driver role
    driver_user = locked_users.get(payload.driver_id) if payload.driver_id else None
    if driver_user and driver_user.role != UserRole.DRIVER:
        raise HTTPException(status_code=400, detail=f"User {driver_user.name} does not have the DRIVER role")

    # Validate Conductor role
    conductor_user = locked_users.get(payload.conductor_id) if payload.conductor_id else None
    if conductor_user and conductor_user.role != UserRole.CONDUCTOR:
        raise HTTPException(status_code=400, detail=f"User {conductor_user.name} does not have the CONDUCTOR role")

    now_utc = datetime.now(timezone.utc)

    # 4. Operational Side-Effect Rule:
    # Find existing active or planned Trip for (org_id, service_id, vehicle_id)
    trip = db.execute(
        select(Trip).where(
            Trip.organization_id == org_id,
            Trip.service_id == service.id,
            Trip.vehicle_id == vehicle.id,
            Trip.status.in_([TripStatus.PLANNED, TripStatus.ACTIVE]),
        ).order_by(Trip.operating_date.desc(), Trip.created_at.desc())
    ).scalars().first()

    if not trip:
        trip = Trip(
            organization_id=org_id,
            service_id=service.id,
            vehicle_id=vehicle.id,
            route_id=service.route_id,
            direction=Direction.A_TO_B,
            operating_date=date.today(),
            planned_start_at=now_utc,
            status=TripStatus.PLANNED,
            start_source="ADMIN_FLEET_ASSIGNMENT",
        )
        db.add(trip)
        db.flush()

    # 5. ATOMIC DRIVER REASSIGNMENT (Single active bus invariant)
    if payload.driver_id:
        # 5a. Lock & inspect existing active driver assignments on the TARGET bus
        target_active_driver_assigns = db.execute(
            select(TripAssignment)
            .join(Trip, TripAssignment.trip_id == Trip.id)
            .where(
                Trip.organization_id == org_id,
                Trip.vehicle_id == vehicle.id,
                TripAssignment.role == "DRIVER",
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
            .order_by(TripAssignment.id)
            .with_for_update()
        ).scalars().all()

        already_active_on_target_trip = False
        for assign in target_active_driver_assigns:
            if assign.user_id == payload.driver_id and assign.trip_id == trip.id:
                already_active_on_target_trip = True
            elif assign.user_id != payload.driver_id:
                # Displacement: release existing driver on target bus
                assign.status = AssignmentStatus.CANCELLED
                assign.unassigned_at = now_utc
            elif assign.trip_id != trip.id:
                # Relieve any redundant trip-level driver assignment on the same bus
                assign.status = AssignmentStatus.CANCELLED
                assign.unassigned_at = now_utc

        # 5b. Lock & release selected driver from ANY OTHER bus in the organization
        other_bus_driver_assigns = db.execute(
            select(TripAssignment)
            .join(Trip, TripAssignment.trip_id == Trip.id)
            .where(
                Trip.organization_id == org_id,
                Trip.vehicle_id != vehicle.id,
                TripAssignment.user_id == payload.driver_id,
                TripAssignment.role == "DRIVER",
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
            .order_by(TripAssignment.id)
            .with_for_update()
        ).scalars().all()

        for assign in other_bus_driver_assigns:
            assign.status = AssignmentStatus.CANCELLED
            assign.unassigned_at = now_utc

        # 5c. Create active assignment on target trip if not already active (safe no-op if same bus + same person)
        if not already_active_on_target_trip:
            new_driver_assign = TripAssignment(
                trip_id=trip.id,
                user_id=payload.driver_id,
                role="DRIVER",
                assigned_at=now_utc,
                status=AssignmentStatus.ASSIGNED,
            )
            db.add(new_driver_assign)
    else:
        # Explicit unassign driver: release all active driver assignments on target bus
        target_active_driver_assigns = db.execute(
            select(TripAssignment)
            .join(Trip, TripAssignment.trip_id == Trip.id)
            .where(
                Trip.organization_id == org_id,
                Trip.vehicle_id == vehicle.id,
                TripAssignment.role == "DRIVER",
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
            .order_by(TripAssignment.id)
            .with_for_update()
        ).scalars().all()

        for assign in target_active_driver_assigns:
            assign.status = AssignmentStatus.CANCELLED
            assign.unassigned_at = now_utc

    # 6. ATOMIC CONDUCTOR REASSIGNMENT (Independent from Driver)
    if payload.conductor_id:
        # 6a. Lock & inspect existing active conductor assignments on the TARGET bus
        target_active_cond_assigns = db.execute(
            select(TripAssignment)
            .join(Trip, TripAssignment.trip_id == Trip.id)
            .where(
                Trip.organization_id == org_id,
                Trip.vehicle_id == vehicle.id,
                TripAssignment.role == "CONDUCTOR",
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
            .order_by(TripAssignment.id)
            .with_for_update()
        ).scalars().all()

        already_active_on_target_trip_cond = False
        for assign in target_active_cond_assigns:
            if assign.user_id == payload.conductor_id and assign.trip_id == trip.id:
                already_active_on_target_trip_cond = True
            elif assign.user_id != payload.conductor_id:
                # Displacement: release existing conductor on target bus
                assign.status = AssignmentStatus.CANCELLED
                assign.unassigned_at = now_utc
            elif assign.trip_id != trip.id:
                # Relieve any redundant trip-level conductor assignment on the same bus
                assign.status = AssignmentStatus.CANCELLED
                assign.unassigned_at = now_utc

        # 6b. Lock & release selected conductor from ANY OTHER bus in the organization
        other_bus_cond_assigns = db.execute(
            select(TripAssignment)
            .join(Trip, TripAssignment.trip_id == Trip.id)
            .where(
                Trip.organization_id == org_id,
                Trip.vehicle_id != vehicle.id,
                TripAssignment.user_id == payload.conductor_id,
                TripAssignment.role == "CONDUCTOR",
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
            .order_by(TripAssignment.id)
            .with_for_update()
        ).scalars().all()

        for assign in other_bus_cond_assigns:
            assign.status = AssignmentStatus.CANCELLED
            assign.unassigned_at = now_utc

        # 6c. Create active assignment on target trip if not already active (safe no-op if same bus + same person)
        if not already_active_on_target_trip_cond:
            new_cond_assign = TripAssignment(
                trip_id=trip.id,
                user_id=payload.conductor_id,
                role="CONDUCTOR",
                assigned_at=now_utc,
                status=AssignmentStatus.ASSIGNED,
            )
            db.add(new_cond_assign)
    else:
        # Explicit unassign conductor: release all active conductor assignments on target bus
        target_active_cond_assigns = db.execute(
            select(TripAssignment)
            .join(Trip, TripAssignment.trip_id == Trip.id)
            .where(
                Trip.organization_id == org_id,
                Trip.vehicle_id == vehicle.id,
                TripAssignment.role == "CONDUCTOR",
                TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            )
            .order_by(TripAssignment.id)
            .with_for_update()
        ).scalars().all()

        for assign in target_active_cond_assigns:
            assign.status = AssignmentStatus.CANCELLED
            assign.unassigned_at = now_utc

    # 7. Ensure active DepotSchedule exists for (vehicle, service)
    depot_sched = db.execute(
        select(DepotSchedule).where(
            DepotSchedule.vehicle_id == vehicle.id,
            DepotSchedule.service_id == service.id,
            DepotSchedule.status != "CANCELLED",
        )
    ).scalars().first()
    if not depot_sched:
        new_sched = DepotSchedule(
            vehicle_id=vehicle.id,
            service_id=service.id,
            direction=Direction.A_TO_B,
            operating_date=date.today(),
            planned_departure=now_utc,
            status="PLANNED",
            source="SERVICE_FLEET_ASSIGNMENT",
        )
        db.add(new_sched)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    driver_summary, conductor_summary, _ = _get_vehicle_active_crew(
        db, org_id, vehicle.id, service.id
    )

    return VehicleCrewAssignmentResponse(
        vehicle_id=vehicle.id,
        service_id=service.id,
        driver=driver_summary,
        conductor=conductor_summary,
        updated_at=now_utc,
    )


@router.post("/vehicles", response_model=VehicleResponse)
def create_vehicle(
    vehicle_in: VehicleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    now_utc = datetime.now(timezone.utc)
    vehicle = Vehicle(
        organization_id=current_admin.organization_id,
        vehicle_number=vehicle_in.vehicle_number,
        registration_number=vehicle_in.registration_number,
        vehicle_type=vehicle_in.vehicle_type,
        status=vehicle_in.status
    )
    svc = None
    try:
        db.add(vehicle)
        db.flush()

        # If service_id is provided, validate service and add ServiceVehicle in the same atomic transaction
        if vehicle_in.service_id:
            svc = db.execute(
                select(Service).where(
                    Service.id == vehicle_in.service_id,
                    Service.organization_id == current_admin.organization_id
                )
            ).scalar_one_or_none()
            if not svc:
                raise HTTPException(status_code=404, detail="Service not found or does not belong to your organization")

            has_sv = inspect(db.bind).has_table("service_vehicles")
            if not has_sv:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="ServiceVehicle table is not yet initialized",
                )

            membership = ServiceVehicle(
                organization_id=current_admin.organization_id,
                service_id=svc.id,
                vehicle_id=vehicle.id,
                status="ACTIVE",
                assigned_at=now_utc,
                unassigned_at=None,
            )
            db.add(membership)

        db.commit()
        db.refresh(vehicle)
    except IntegrityError as ie:
        db.rollback()
        if "uq_vehicles_org_number" in str(ie) or "vehicle_number" in str(ie):
            raise HTTPException(status_code=400, detail="Vehicle number already exists for this organization")
        raise HTTPException(status_code=400, detail=f"Database integrity error: {ie.orig}")
    except Exception:
        db.rollback()
        raise

    resp = VehicleResponse.model_validate(vehicle)
    if svc:
        resp.service = ServiceSummary(
            id=svc.id,
            service_code=svc.service_code,
            service_name=svc.service_name,
            route_id=svc.route_id,
        )
    return resp


@router.put("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: uuid.UUID,
    vehicle_in: VehicleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    update_data = vehicle_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vehicle, field, value)

    try:
        db.commit()
        db.refresh(vehicle)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid update, possible duplicate vehicle number")
    return vehicle


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    vehicle_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    """
    Soft-deletes (decommissions) the vehicle rather than hard-delete to preserve history.
    """
    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
        
    vehicle.status = VehicleStatus.DECOMMISSIONED
    db.commit()


# -------------------------------------------------------------------------
# SERVICE ↔ VEHICLE MEMBERSHIP ENDPOINTS
# -------------------------------------------------------------------------

@router.post("/services/{service_id}/vehicles", response_model=ServiceVehicleResponse, status_code=status.HTTP_201_CREATED)
def assign_service_vehicle(
    service_id: uuid.UUID,
    payload: ServiceVehicleAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    """
    Explicitly assigns an existing organization vehicle to a service.
    Reactivates historical INACTIVE membership or creates a new ACTIVE record.
    Prevents duplicate active membership. Does NOT mutate vehicle registration.
    """
    org_id = current_admin.organization_id
    service = db.execute(
        select(Service).where(Service.id == service_id, Service.organization_id == org_id)
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or does not belong to your organization")

    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == payload.vehicle_id, Vehicle.organization_id == org_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or does not belong to your organization")

    now_utc = datetime.now(timezone.utc)
    has_sv = inspect(db.bind).has_table("service_vehicles")
    if not has_sv:
        raise HTTPException(status_code=500, detail="ServiceVehicle table is not yet initialized")

    existing_membership = db.execute(
        select(ServiceVehicle).where(
            ServiceVehicle.service_id == service_id,
            ServiceVehicle.vehicle_id == payload.vehicle_id,
            ServiceVehicle.organization_id == org_id,
        )
    ).scalar_one_or_none()

    if existing_membership:
        if existing_membership.status == "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle {vehicle.vehicle_number} is already assigned to {service.service_name}",
            )
        # Reactivate existing inactive membership record
        existing_membership.status = "ACTIVE"
        existing_membership.assigned_at = now_utc
        existing_membership.unassigned_at = None
        db.commit()
        db.refresh(existing_membership)
        return existing_membership

    # Create new explicit membership
    membership = ServiceVehicle(
        organization_id=org_id,
        service_id=service_id,
        vehicle_id=payload.vehicle_id,
        status="ACTIVE",
        assigned_at=now_utc,
        unassigned_at=None,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.delete("/services/{service_id}/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_service_vehicle(
    service_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    """
    Explicitly unassigns a vehicle from a service by setting status to INACTIVE.
    Preserves historical association record and timestamps.
    """
    org_id = current_admin.organization_id
    service = db.execute(
        select(Service).where(Service.id == service_id, Service.organization_id == org_id)
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or does not belong to your organization")

    vehicle = db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.organization_id == org_id)
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or does not belong to your organization")

    now_utc = datetime.now(timezone.utc)
    has_sv = inspect(db.bind).has_table("service_vehicles")
    if not has_sv:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ServiceVehicle table is not yet initialized",
        )

    membership = db.execute(
        select(ServiceVehicle).where(
            ServiceVehicle.service_id == service_id,
            ServiceVehicle.vehicle_id == vehicle_id,
            ServiceVehicle.organization_id == org_id,
        )
    ).scalar_one_or_none()

    if membership:
        membership.status = "INACTIVE"
        membership.unassigned_at = now_utc
    else:
        # Create an explicit INACTIVE record to override legacy fallback
        membership = ServiceVehicle(
            organization_id=org_id,
            service_id=service_id,
            vehicle_id=vehicle_id,
            status="INACTIVE",
            assigned_at=now_utc,
            unassigned_at=now_utc,
        )
        db.add(membership)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/services/{service_id}/available-vehicles", response_model=list[AvailableVehicleOption])
def get_available_vehicles(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    """
    Returns all organization vehicles with current service assignment status,
    powering the Assign Existing Vehicle selector in Admin Web.
    """
    org_id = current_admin.organization_id
    service = db.execute(
        select(Service).where(Service.id == service_id, Service.organization_id == org_id)
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    vehicles = db.execute(
        select(Vehicle).where(Vehicle.organization_id == org_id).order_by(Vehicle.vehicle_number.asc())
    ).scalars().all()

    has_sv = inspect(db.bind).has_table("service_vehicles")
    active_sv_map: dict[uuid.UUID, list[uuid.UUID]] = {}
    inactive_sv_map: dict[uuid.UUID, set[uuid.UUID]] = {}
    if has_sv:
        all_svs = db.execute(
            select(ServiceVehicle).where(ServiceVehicle.organization_id == org_id)
        ).scalars().all()
        for sv in all_svs:
            if sv.status == "ACTIVE":
                active_sv_map.setdefault(sv.vehicle_id, []).append(sv.service_id)
            elif sv.status == "INACTIVE":
                inactive_sv_map.setdefault(sv.vehicle_id, set()).add(sv.service_id)

    all_services = {
        s.id: ServiceSummary(id=s.id, service_code=s.service_code, service_name=s.service_name, route_id=s.route_id)
        for s in db.execute(select(Service).where(Service.organization_id == org_id)).scalars().all()
    }

    legacy_depot_map: dict[uuid.UUID, set[uuid.UUID]] = {}
    for row in db.execute(
        select(DepotSchedule.vehicle_id, DepotSchedule.service_id)
        .join(Service, DepotSchedule.service_id == Service.id)
        .where(Service.organization_id == org_id)
    ).all():
        legacy_depot_map.setdefault(row[0], set()).add(row[1])

    legacy_trip_map: dict[uuid.UUID, set[uuid.UUID]] = {}
    for row in db.execute(
        select(Trip.vehicle_id, Trip.service_id).where(Trip.organization_id == org_id)
    ).all():
        legacy_trip_map.setdefault(row[0], set()).add(row[1])

    options = []
    for v in vehicles:
        is_assigned = False
        assigned_service_ids = set()

        if has_sv and v.id in active_sv_map:
            assigned_service_ids.update(active_sv_map[v.id])
            if service_id in active_sv_map[v.id]:
                is_assigned = True

        # Check legacy evidence for services where no ServiceVehicle record exists
        legacy_svcs = legacy_depot_map.get(v.id, set()) | legacy_trip_map.get(v.id, set())
        for l_s_id in legacy_svcs:
            if v.id in inactive_sv_map and l_s_id in inactive_sv_map[v.id]:
                continue  # Explicitly unassigned overrides legacy evidence
            assigned_service_ids.add(l_s_id)
            if l_s_id == service_id and not (has_sv and v.id in inactive_sv_map and service_id in inactive_sv_map[v.id]):
                is_assigned = True

        assigned_summaries = [
            all_services[s_id] for s_id in assigned_service_ids if s_id in all_services
        ]

        options.append(
            AvailableVehicleOption(
                id=v.id,
                vehicle_number=v.vehicle_number,
                registration_number=v.registration_number,
                vehicle_type=v.vehicle_type,
                status=v.status.value if hasattr(v.status, "value") else str(v.status),
                is_assigned_to_current_service=is_assigned,
                assigned_services=assigned_summaries,
            )
        )
    return options


# -------------------------------------------------------------------------
# DEPOT SCHEDULES
# -------------------------------------------------------------------------

def _format_time_display(t: time) -> str:
    return t.strftime("%I:%M %p")


@router.get("/depot-schedules", response_model=list[DepotScheduleResponse])
def get_depot_schedules(
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # Enforce org isolation by joining Service or Vehicle
    stmt = (
        select(DepotSchedule)
        .join(Service, DepotSchedule.service_id == Service.id)
        .where(Service.organization_id == current_admin.organization_id)
        .order_by(DepotSchedule.operating_date.desc(), DepotSchedule.planned_departure.desc())
    )
    schedules = db.execute(stmt).scalars().all()
    
    responses = []
    for sched in schedules:
        service = db.get(Service, sched.service_id)
        vehicle = db.get(Vehicle, sched.vehicle_id)
        resp = DepotScheduleResponse.model_validate(sched)
        
        if service:
            route = db.get(Route, service.route_id)
            resp.service = ServiceSummary(
                id=service.id,
                service_code=service.service_code,
                service_name=service.service_name,
                route_id=service.route_id
            )
        if vehicle:
            resp.vehicle = VehicleSummary(
                id=vehicle.id,
                vehicle_number=vehicle.vehicle_number,
                vehicle_type=vehicle.vehicle_type
            )
        responses.append(resp)
        
    return responses


# -------------------------------------------------------------------------
# MAJOR DEPOT & DEPOT-CENTRIC COMBINED DEPARTURES
# -------------------------------------------------------------------------

@router.get("/depot-schedules/major-depots", response_model=list[MajorDepotResponse])
def get_major_depots(
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
):
    """
    Returns list of all unique Major Depots (endpoints of routes) for the current organization.
    A route endpoint is sequence 1 (Depot A) or max sequence (Depot B).
    """
    routes = db.execute(
        select(Route).where(Route.organization_id == current_admin.organization_id)
    ).scalars().all()
    route_ids = [r.id for r in routes]
    if not route_ids:
        return []

    route_stops = db.execute(
        select(RouteStop)
        .where(RouteStop.route_id.in_(route_ids))
        .order_by(RouteStop.route_id, RouteStop.sequence_number.asc())
    ).scalars().all()

    route_stops_by_route: dict[uuid.UUID, list[RouteStop]] = {}
    for rs in route_stops:
        route_stops_by_route.setdefault(rs.route_id, []).append(rs)

    depot_route_counts: dict[uuid.UUID, int] = {}
    for r_id, r_stops in route_stops_by_route.items():
        if not r_stops:
            continue
        start_stop_id = r_stops[0].stop_id
        end_stop_id = r_stops[-1].stop_id

        depot_route_counts[start_stop_id] = depot_route_counts.get(start_stop_id, 0) + 1
        if end_stop_id != start_stop_id:
            depot_route_counts[end_stop_id] = depot_route_counts.get(end_stop_id, 0) + 1

    if not depot_route_counts:
        return []

    stops = db.execute(
        select(Stop).where(Stop.id.in_(list(depot_route_counts.keys())))
    ).scalars().all()

    results = [
        MajorDepotResponse(
            id=stop.id,
            stop_code=stop.stop_code,
            stop_name=stop.name,
            routes_count=depot_route_counts.get(stop.id, 0),
        )
        for stop in stops
    ]

    results.sort(key=lambda d: d.stop_name.lower())
    return results


@router.get("/depot-schedules/departures", response_model=list[DepotDepartureItemResponse])
def get_depot_departures(
    depot_stop_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
):
    """
    Returns a combined, chronological daily timetable of all recurring departures originating
    from the selected Major Depot across all applicable routes and services.
    
    Every single departure row independently derives:
      Selected Major Depot + Service + That Service's Route + Fleet Schedule Direction
      -> Origin Major Depot -> Destination Major Depot
    """
    selected_stop = db.execute(
        select(Stop).where(
            Stop.id == depot_stop_id,
            Stop.organization_id == current_admin.organization_id,
        )
    ).scalar_one_or_none()
    if not selected_stop:
        raise HTTPException(status_code=404, detail="Major Depot not found or unauthorized")

    routes = db.execute(
        select(Route).where(Route.organization_id == current_admin.organization_id)
    ).scalars().all()
    route_ids = [r.id for r in routes]
    if not route_ids:
        return []

    route_stops = db.execute(
        select(RouteStop)
        .where(RouteStop.route_id.in_(route_ids))
        .order_by(RouteStop.route_id, RouteStop.sequence_number.asc())
    ).scalars().all()

    route_stops_by_route: dict[uuid.UUID, list[RouteStop]] = {}
    for rs in route_stops:
        route_stops_by_route.setdefault(rs.route_id, []).append(rs)

    applicable_route_directions: dict[tuple[uuid.UUID, Direction], tuple[uuid.UUID, uuid.UUID]] = {}
    dest_stop_ids: set[uuid.UUID] = set()
    routes_by_id = {r.id: r for r in routes}

    for r_id, r_stops in route_stops_by_route.items():
        if not r_stops:
            continue
        start_stop_id = r_stops[0].stop_id
        end_stop_id = r_stops[-1].stop_id

        if start_stop_id == depot_stop_id:
            applicable_route_directions[(r_id, Direction.A_TO_B)] = (start_stop_id, end_stop_id)
            dest_stop_ids.add(end_stop_id)

        if end_stop_id == depot_stop_id:
            applicable_route_directions[(r_id, Direction.B_TO_A)] = (end_stop_id, start_stop_id)
            dest_stop_ids.add(start_stop_id)

    if not applicable_route_directions:
        return []

    dest_stops = db.execute(
        select(Stop).where(Stop.id.in_(list(dest_stop_ids)))
    ).scalars().all() if dest_stop_ids else []
    dest_stops_by_id = {s.id: s for s in dest_stops}
    dest_stops_by_id[selected_stop.id] = selected_stop

    applicable_route_ids = list({r_id for (r_id, _) in applicable_route_directions.keys()})
    services = db.execute(
        select(Service).where(
            Service.route_id.in_(applicable_route_ids),
            Service.organization_id == current_admin.organization_id,
        )
    ).scalars().all()
    services_by_id = {s.id: s for s in services}
    service_ids = list(services_by_id.keys())

    if not service_ids:
        return []

    schedules = db.execute(
        select(DepotSchedule).where(
            DepotSchedule.service_id.in_(service_ids),
            DepotSchedule.status != "CANCELLED",
        )
    ).scalars().all()

    veh_ids = list({s.vehicle_id for s in schedules})
    vehicles = db.execute(select(Vehicle).where(Vehicle.id.in_(veh_ids))).scalars().all() if veh_ids else []
    vehicles_by_id = {v.id: v for v in vehicles}

    items: list[DepotDepartureItemResponse] = []
    for sched in schedules:
        svc = services_by_id.get(sched.service_id)
        if not svc:
            continue
        route = routes_by_id.get(svc.route_id)
        if not route:
            continue

        key = (svc.route_id, sched.direction)
        if key not in applicable_route_directions:
            continue

        origin_id, dest_id = applicable_route_directions[key]
        dest_stop = dest_stops_by_id.get(dest_id)
        dest_name = dest_stop.name if dest_stop else "Unknown"
        dest_code = dest_stop.stop_code if dest_stop else None

        vehicle = vehicles_by_id.get(sched.vehicle_id)
        veh_number = vehicle.vehicle_number if vehicle else "Unknown"
        reg_number = vehicle.registration_number if vehicle else None
        veh_type = vehicle.vehicle_type if vehicle else None
        veh_status = vehicle.status.value if (vehicle and hasattr(vehicle.status, "value")) else (str(vehicle.status) if vehicle else "UNKNOWN")

        dep_time = sched.planned_departure.time()
        time_str = dep_time.strftime("%H:%M")
        formatted_time = _format_time_display(dep_time)

        items.append(
            DepotDepartureItemResponse(
                id=sched.id,
                departure_time=time_str,
                formatted_departure_time=formatted_time,
                vehicle_id=sched.vehicle_id,
                vehicle_number=veh_number,
                registration_number=reg_number,
                vehicle_type=veh_type,
                vehicle_status=veh_status,
                service_id=svc.id,
                service_name=svc.service_name,
                service_code=svc.service_code,
                route_id=route.id,
                route_code=route.route_code,
                route_name=route.route_name,
                origin_stop_id=selected_stop.id,
                origin_stop_name=selected_stop.name,
                origin_stop_code=selected_stop.stop_code,
                destination_stop_id=dest_id,
                destination_stop_name=dest_name,
                destination_stop_code=dest_code,
                direction=sched.direction,
                status=sched.status,
                every_day=True,
                source=sched.source,
                operating_date=sched.operating_date,
            )
        )

    items.sort(key=lambda x: x.departure_time)
    return items


@router.get("/depot-schedules/{schedule_id}", response_model=DepotScheduleResponse)
def get_depot_schedule(
    schedule_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    stmt = (
        select(DepotSchedule)
        .join(Service, DepotSchedule.service_id == Service.id)
        .where(
            DepotSchedule.id == schedule_id,
            Service.organization_id == current_admin.organization_id
        )
    )
    sched = db.execute(stmt).scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Depot Schedule not found")
        
    service = db.get(Service, sched.service_id)
    vehicle = db.get(Vehicle, sched.vehicle_id)
    resp = DepotScheduleResponse.model_validate(sched)
    
    if service:
        route = db.get(Route, service.route_id)
        resp.service = ServiceSummary(
            id=service.id,
            service_code=service.service_code,
            service_name=service.service_name,
            route_id=service.route_id
        )
    if vehicle:
        resp.vehicle = VehicleSummary(
            id=vehicle.id,
            vehicle_number=vehicle.vehicle_number,
            vehicle_type=vehicle.vehicle_type
        )
    return resp


@router.post("/depot-schedules", response_model=DepotScheduleResponse)
def create_depot_schedule(
    schedule_in: DepotScheduleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # Validate vehicle ownership
    vehicle = db.execute(
        select(Vehicle).where(
            Vehicle.id == schedule_in.vehicle_id, 
            Vehicle.organization_id == current_admin.organization_id
        )
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=400, detail="Vehicle not found or does not belong to your organization")

    # Validate service ownership
    service = db.execute(
        select(Service).where(
            Service.id == schedule_in.service_id, 
            Service.organization_id == current_admin.organization_id
        )
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=400, detail="Service not found or does not belong to your organization")

    schedule = DepotSchedule(
        vehicle_id=schedule_in.vehicle_id,
        service_id=schedule_in.service_id,
        direction=schedule_in.direction,
        operating_date=schedule_in.operating_date,
        planned_departure=schedule_in.planned_departure,
        planned_arrival=schedule_in.planned_arrival,
        status=schedule_in.status,
        source=schedule_in.source
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    resp = DepotScheduleResponse.model_validate(schedule)
    resp.service = ServiceSummary(
        id=service.id,
        service_code=service.service_code,
        service_name=service.service_name,
        route_id=service.route_id
    )
    resp.vehicle = VehicleSummary(
        id=vehicle.id,
        vehicle_number=vehicle.vehicle_number,
        vehicle_type=vehicle.vehicle_type
    )
    return resp


@router.put("/depot-schedules/{schedule_id}", response_model=DepotScheduleResponse)
def update_depot_schedule(
    schedule_id: uuid.UUID,
    schedule_in: DepotScheduleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    stmt = (
        select(DepotSchedule)
        .join(Service, DepotSchedule.service_id == Service.id)
        .where(
            DepotSchedule.id == schedule_id,
            Service.organization_id == current_admin.organization_id
        )
    )
    schedule = db.execute(stmt).scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Depot Schedule not found")

    if schedule_in.vehicle_id:
        vehicle = db.execute(
            select(Vehicle).where(
                Vehicle.id == schedule_in.vehicle_id, 
                Vehicle.organization_id == current_admin.organization_id
            )
        ).scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=400, detail="Vehicle not found or does not belong to your organization")

    if schedule_in.service_id:
        service = db.execute(
            select(Service).where(
                Service.id == schedule_in.service_id, 
                Service.organization_id == current_admin.organization_id
            )
        ).scalar_one_or_none()
        if not service:
            raise HTTPException(status_code=400, detail="Service not found or does not belong to your organization")

    update_data = schedule_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)
    
    return get_depot_schedule(schedule_id, db, current_admin)


@router.delete("/depot-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_depot_schedule(
    schedule_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    """
    Instead of hard-deleting, sets the status to CANCELLED.
    """
    stmt = (
        select(DepotSchedule)
        .join(Service, DepotSchedule.service_id == Service.id)
        .where(
            DepotSchedule.id == schedule_id,
            Service.organization_id == current_admin.organization_id
        )
    )
    schedule = db.execute(stmt).scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Depot Schedule not found")
        
    schedule.status = "CANCELLED"
    db.commit()


# -------------------------------------------------------------------------
# FLEET SCHEDULES (SERVICE-SCOPED RECURRING TIMETABLES)
# -------------------------------------------------------------------------

def _parse_time_str(time_str: str) -> time:
    parts = time_str.strip().split(":")
    if len(parts) < 2 or len(parts) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid departure_time format. Expected HH:MM or HH:MM:SS."
        )
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            raise ValueError()
        return time(hour, minute, second)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid departure_time values. Hours must be 0-23, minutes 0-59."
        )


def _to_fleet_schedule_response(db: Session, sched: DepotSchedule, org_id: uuid.UUID) -> FleetScheduleItemResponse:
    dep_time = sched.planned_departure.time()
    time_str = dep_time.strftime("%H:%M")
    formatted_time = _format_time_display(dep_time)
    
    vehicle = db.get(Vehicle, sched.vehicle_id)
    veh_number = vehicle.vehicle_number if vehicle else "Unknown"
    veh_type = vehicle.vehicle_type if vehicle else None
    reg_number = vehicle.registration_number if vehicle else None
    veh_status = vehicle.status.value if (vehicle and hasattr(vehicle.status, "value")) else (str(vehicle.status) if vehicle else None)

    driver_summary, conductor_summary, _ = _get_vehicle_active_crew(
        db,
        org_id=org_id,
        vehicle_id=sched.vehicle_id,
        service_id=sched.service_id,
    )

    return FleetScheduleItemResponse(
        id=sched.id,
        service_id=sched.service_id,
        vehicle_id=sched.vehicle_id,
        vehicle_number=veh_number,
        vehicle_type=veh_type,
        registration_number=reg_number,
        vehicle_status=veh_status,
        departure_time=time_str,
        formatted_departure_time=formatted_time,
        direction=sched.direction,
        driver=driver_summary,
        conductor=conductor_summary,
        every_day=True,
        status=sched.status,
        source=sched.source,
        created_at=sched.created_at,
        updated_at=sched.updated_at,
    )


@router.get("/fleet-schedules", response_model=list[FleetScheduleItemResponse])
def get_fleet_schedules(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
    direction: Optional[Direction] = None,
):
    """
    List recurring departure timetable for a specific service and optionally scoped by direction,
    ordered chronologically by departure time.
    """
    service = db.execute(
        select(Service).where(
            Service.id == service_id,
            Service.organization_id == current_admin.organization_id,
        )
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or unauthorized")

    stmt = (
        select(DepotSchedule)
        .where(
            DepotSchedule.service_id == service_id,
            DepotSchedule.status != "CANCELLED",
        )
    )
    if direction is not None:
        stmt = stmt.where(DepotSchedule.direction == direction)

    schedules = db.execute(stmt).scalars().all()

    items = [_to_fleet_schedule_response(db, s, current_admin.organization_id) for s in schedules]
    items.sort(key=lambda x: x.departure_time)
    return items


def _is_vehicle_associated_with_service(
    db: Session,
    org_id: uuid.UUID,
    service_id: uuid.UUID,
    vehicle_id: uuid.UUID,
) -> bool:
    """
    Authoritative service-vehicle membership validation matching get_vehicles:
    1. If ServiceVehicle table exists:
       - If an explicit ServiceVehicle row exists for (service_id, vehicle_id, org_id):
         - Return True if status == "ACTIVE"
         - Return False if status == "INACTIVE" (explicitly unassigned)
       - If NO explicit ServiceVehicle row exists for this service:
         - Fallback: Return True if legacy evidence exists (DepotSchedule or Trip for this service).
    2. If ServiceVehicle table does not exist:
       - Fallback: Return True if legacy evidence exists (DepotSchedule or Trip for this service).
    """
    has_sv = inspect(db.bind).has_table("service_vehicles")
    if has_sv:
        sv = db.execute(
            select(ServiceVehicle).where(
                ServiceVehicle.service_id == service_id,
                ServiceVehicle.vehicle_id == vehicle_id,
                ServiceVehicle.organization_id == org_id,
            )
        ).scalar_one_or_none()
        if sv is not None:
            return sv.status == "ACTIVE"

    # Legacy fallback: evidence in DepotSchedule (any status) or Trip
    legacy_depot = db.execute(
        select(DepotSchedule.id).where(
            DepotSchedule.service_id == service_id,
            DepotSchedule.vehicle_id == vehicle_id,
        )
    ).scalars().first()
    if legacy_depot:
        return True

    legacy_trip = db.execute(
        select(Trip.id).where(
            Trip.service_id == service_id,
            Trip.vehicle_id == vehicle_id,
            Trip.organization_id == org_id,
        )
    ).scalars().first()
    return legacy_trip is not None


@router.post("/fleet-schedules", response_model=FleetScheduleItemResponse, status_code=status.HTTP_201_CREATED)
def create_fleet_schedule(
    schedule_in: FleetScheduleCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
):
    """
    Add a recurring departure to the service timetable for a specific direction.
    """
    service = db.execute(
        select(Service).where(
            Service.id == schedule_in.service_id,
            Service.organization_id == current_admin.organization_id,
        )
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=400, detail="Service not found or unauthorized")

    vehicle = db.execute(
        select(Vehicle).where(
            Vehicle.id == schedule_in.vehicle_id,
            Vehicle.organization_id == current_admin.organization_id,
        )
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=400, detail="Vehicle not found or unauthorized")

    if not _is_vehicle_associated_with_service(db, current_admin.organization_id, service.id, vehicle.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle is not associated with this service. Please add the vehicle to the service in Fleet Management first.",
        )

    t_val = _parse_time_str(schedule_in.departure_time)

    # Direction-scoped duplicate check: same service, direction, vehicle, departure time
    existing_schedules = db.execute(
        select(DepotSchedule).where(
            DepotSchedule.service_id == service.id,
            DepotSchedule.direction == schedule_in.direction,
            DepotSchedule.vehicle_id == vehicle.id,
            DepotSchedule.status != "CANCELLED",
        )
    ).scalars().all()
    for ex in existing_schedules:
        ex_time = ex.planned_departure.time()
        if ex_time.hour == t_val.hour and ex_time.minute == t_val.minute:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A departure for vehicle {vehicle.vehicle_number} at {t_val.strftime('%H:%M')} already exists for this service and direction.",
            )

    planned_dt = datetime.combine(date.today(), t_val)
    new_sched = DepotSchedule(
        vehicle_id=vehicle.id,
        service_id=service.id,
        direction=schedule_in.direction,
        operating_date=date.today(),
        planned_departure=planned_dt,
        status="PLANNED",
        source="RECURRING_DAILY",
    )
    db.add(new_sched)
    db.commit()
    db.refresh(new_sched)

    return _to_fleet_schedule_response(db, new_sched, current_admin.organization_id)


@router.put("/fleet-schedules/{schedule_id}", response_model=FleetScheduleItemResponse)
def update_fleet_schedule(
    schedule_id: uuid.UUID,
    schedule_in: FleetScheduleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
):
    """
    Update departure time, vehicle, or direction for a recurring timetable entry.
    """
    sched = db.execute(
        select(DepotSchedule)
        .join(Service, DepotSchedule.service_id == Service.id)
        .where(
            DepotSchedule.id == schedule_id,
            Service.organization_id == current_admin.organization_id,
        )
    ).scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found or unauthorized")

    target_veh_id = sched.vehicle_id
    if schedule_in.vehicle_id and schedule_in.vehicle_id != sched.vehicle_id:
        vehicle = db.execute(
            select(Vehicle).where(
                Vehicle.id == schedule_in.vehicle_id,
                Vehicle.organization_id == current_admin.organization_id,
            )
        ).scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=400, detail="Vehicle not found or unauthorized")

        if not _is_vehicle_associated_with_service(db, current_admin.organization_id, sched.service_id, vehicle.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vehicle is not associated with this service. Please add the vehicle to the service in Fleet Management first.",
            )
        target_veh_id = schedule_in.vehicle_id

    target_direction = schedule_in.direction if schedule_in.direction is not None else sched.direction
    target_time = sched.planned_departure.time()
    if schedule_in.departure_time:
        target_time = _parse_time_str(schedule_in.departure_time)

    # Direction-scoped duplicate check:
    existing = db.execute(
        select(DepotSchedule).where(
            DepotSchedule.service_id == sched.service_id,
            DepotSchedule.direction == target_direction,
            DepotSchedule.vehicle_id == target_veh_id,
            DepotSchedule.id != sched.id,
            DepotSchedule.status != "CANCELLED",
        )
    ).scalars().all()
    for ex in existing:
        ex_time = ex.planned_departure.time()
        if ex_time.hour == target_time.hour and ex_time.minute == target_time.minute:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A departure at {target_time.strftime('%H:%M')} already exists for this vehicle, service, and direction.",
            )

    sched.vehicle_id = target_veh_id
    sched.direction = target_direction
    sched.planned_departure = datetime.combine(sched.operating_date, target_time)
    sched.source = "RECURRING_DAILY"
    db.commit()
    db.refresh(sched)
    return _to_fleet_schedule_response(db, sched, current_admin.organization_id)


@router.delete("/fleet-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fleet_schedule(
    schedule_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin),
):
    """
    Cancel a recurring departure from the timetable.
    """
    stmt = (
        select(DepotSchedule)
        .join(Service, DepotSchedule.service_id == Service.id)
        .where(
            DepotSchedule.id == schedule_id,
            Service.organization_id == current_admin.organization_id,
        )
    )
    sched = db.execute(stmt).scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found or unauthorized")

    sched.status = "CANCELLED"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

