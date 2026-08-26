"""
Transit Platform — Operator Service.

BUILD 2: Duty assignment retrieval, assignment-based device authorization,
and manual tracking session lifecycle.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.device import Device
from app.models.enums import AssignmentStatus, DeviceStatus, TrackingSessionStatus, TripStatus
from app.models.service import Service
from app.models.tracking import TrackingSession
from app.models.trip import Trip, TripAssignment
from app.models.user import User
from app.schemas.operator import AssignmentResponse, TripEndResponse, TripStartResponse


def get_operator_assignment(db: Session, user: User) -> AssignmentResponse:
    """
    Retrieve the current/upcoming trip assignment for the authenticated operator.
    Uses BUILD 1 relationships: TripAssignment -> Trip -> Service -> Route / Vehicle / Device.
    """
    stmt = (
        select(TripAssignment)
        .options(
            selectinload(TripAssignment.trip)
            .selectinload(Trip.service)
            .selectinload(Service.route),
            selectinload(TripAssignment.trip).selectinload(Trip.vehicle),
            selectinload(TripAssignment.device),
        )
        .where(
            TripAssignment.user_id == user.id,
            TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
        )
        .order_by(TripAssignment.assigned_at.desc())
    )
    assignment = db.execute(stmt).scalars().first()

    if assignment is None or assignment.trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active or upcoming trip assignment found for this operator",
        )

    trip = assignment.trip
    service = trip.service
    route = service.route if service else None
    vehicle = trip.vehicle
    device = assignment.device

    # Check for existing active tracking session
    session_stmt = (
        select(TrackingSession)
        .where(
            TrackingSession.trip_id == trip.id,
            TrackingSession.operator_id == user.id,
            TrackingSession.status.in_(
                [
                    TrackingSessionStatus.ACTIVE,
                    TrackingSessionStatus.STARTING,
                    TrackingSessionStatus.OFFLINE,
                    TrackingSessionStatus.SYNCING,
                ]
            ),
        )
        .order_by(TrackingSession.created_at.desc())
    )
    active_session = db.execute(session_stmt).scalars().first()

    return AssignmentResponse(
        assignment_id=assignment.id,
        trip_id=trip.id,
        service_id=service.id if service else trip.service_id,
        service_code=service.service_code if service else "UNKNOWN",
        service_name=service.service_name if service else "Unknown Service",
        route_id=route.id if route else trip.route_id,
        route_code=route.route_code if route else "UNKNOWN",
        route_name=route.route_name if route else "Unknown Route",
        direction=trip.direction.value,
        vehicle_id=vehicle.id if vehicle else trip.vehicle_id,
        vehicle_number=vehicle.vehicle_number if vehicle else "UNKNOWN",
        planned_start_at=trip.planned_start_at,
        trip_status=trip.status.value,
        operator_role=assignment.role,
        assignment_status=assignment.status.value,
        assigned_device_id=device.id if device else assignment.device_id,
        assigned_device_status=device.status.value if device else None,
        active_tracking_session_id=active_session.id if active_session else None,
        tracking_session_status=active_session.status.value if active_session else None,
    )


def start_trip_tracking(db: Session, user: User, trip_id: uuid.UUID) -> TripStartResponse:
    """
    Start an explicit tracking session for an assigned trip.

    Enforces Assignment-Based Device Validation:
    1. Authenticated operator
    2. Trip assignment exists and belongs to operator
    3. Assignment has an associated Device
    4. Device exists, belongs to same organization, and is ACTIVE
    5. Trip belongs to same organization and is eligible (PLANNED or ACTIVE)
    6. Prevents duplicate active sessions for same trip/device
    """
    stmt = (
        select(TripAssignment)
        .options(
            selectinload(TripAssignment.trip),
            selectinload(TripAssignment.device),
        )
        .where(
            TripAssignment.user_id == user.id,
            TripAssignment.trip_id == trip_id,
            TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
        )
    )
    assignment = db.execute(stmt).scalars().first()

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator is not assigned to this trip",
        )

    trip = assignment.trip
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned trip not found",
        )

    # Validate organization consistency
    if user.organization_id and trip.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trip belongs to a different organization",
        )

    # Validate trip status
    if trip.status not in (TripStatus.PLANNED, TripStatus.ACTIVE, TripStatus.SUSPECTED_START):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start tracking for trip with status '{trip.status.value}'",
        )

    # Validate assigned device
    if assignment.device_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No device assigned for this operator duty",
        )

    device = db.get(Device, assignment.device_id)
    if device is None or device.status != DeviceStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assigned tracking device is not active or not found",
        )

    if user.organization_id and device.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assigned device belongs to a different organization",
        )

    now = datetime.now(timezone.utc)

    # Check for existing active tracking session to avoid overlapping duplicates
    existing_session_stmt = select(TrackingSession).where(
        TrackingSession.trip_id == trip.id,
        TrackingSession.device_id == device.id,
        TrackingSession.status.in_(
            [
                TrackingSessionStatus.ACTIVE,
                TrackingSessionStatus.STARTING,
                TrackingSessionStatus.OFFLINE,
                TrackingSessionStatus.SYNCING,
            ]
        ),
    )
    existing_session = db.execute(existing_session_stmt).scalars().first()

    if existing_session is not None:
        return TripStartResponse(
            tracking_session_id=existing_session.id,
            trip_id=trip.id,
            device_id=device.id,
            status=existing_session.status.value,
            started_at=existing_session.started_at or existing_session.created_at,
        )

    # Create new tracking session
    session = TrackingSession(
        id=uuid.uuid4(),
        device_id=device.id,
        operator_id=user.id,
        trip_id=trip.id,
        started_at=now,
        status=TrackingSessionStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    db.add(session)

    # Update assignment status to ACTIVE
    assignment.status = AssignmentStatus.ACTIVE

    db.commit()
    db.refresh(session)

    return TripStartResponse(
        tracking_session_id=session.id,
        trip_id=trip.id,
        device_id=device.id,
        status=session.status.value,
        started_at=session.started_at or now,
    )


def end_trip_tracking(db: Session, user: User, trip_id: uuid.UUID) -> TripEndResponse:
    """
    End an active tracking session for an assigned trip.
    Marks tracking session as ENDED and records ended_at timestamp.
    """
    stmt = (
        select(TrackingSession)
        .where(
            TrackingSession.trip_id == trip_id,
            TrackingSession.operator_id == user.id,
            TrackingSession.status != TrackingSessionStatus.ENDED,
        )
        .order_by(TrackingSession.created_at.desc())
    )
    session = db.execute(stmt).scalars().first()

    if session is None:
        # Check if already ended
        ended_stmt = (
            select(TrackingSession)
            .where(
                TrackingSession.trip_id == trip_id,
                TrackingSession.operator_id == user.id,
                TrackingSession.status == TrackingSessionStatus.ENDED,
            )
            .order_by(TrackingSession.updated_at.desc())
        )
        ended_session = db.execute(ended_stmt).scalars().first()
        if ended_session:
            return TripEndResponse(
                tracking_session_id=ended_session.id,
                trip_id=trip_id,
                status=ended_session.status.value,
                ended_at=ended_session.ended_at or ended_session.updated_at,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active tracking session found for this trip and operator",
        )

    now = datetime.now(timezone.utc)
    session.status = TrackingSessionStatus.ENDED
    session.ended_at = now
    session.updated_at = now

    db.commit()

    return TripEndResponse(
        tracking_session_id=session.id,
        trip_id=trip_id,
        status=session.status.value,
        ended_at=now,
    )
