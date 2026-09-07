"""
Transit Platform — Operator Service.

BUILD 2: Duty assignment retrieval, assignment-based device authorization,
and manual tracking session lifecycle.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.alert import ServiceAlert
from app.models.device import Device
from app.models.enums import (
    AlertScope,
    AlertSeverity,
    AlertStatus,
    AssignmentStatus,
    DeviceStatus,
    TrackingSessionStatus,
    TripStatus,
)
from app.models.route import RouteStop
from app.models.service import Service
from app.models.tracking import TrackingSession
from app.models.trip import Trip, TripAssignment
from app.models.user import User
from app.schemas.operator import (
    AssignmentResponse,
    OperatorIssueReportRequest,
    OperatorIssueReportResponse,
    OperatorTripResponse,
    TripEndResponse,
    TripStartResponse,
)


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

    # Derive operational details for operator mobile UI
    route_id = route.id if route else trip.route_id
    origin_stop_name, destination_stop_name = _resolve_terminal_stops(db, route_id, trip.direction)
    route_distance_km = route.distance_km if route else None

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
        vehicle_registration=vehicle.registration_number if vehicle else None,
        vehicle_type=vehicle.vehicle_type if vehicle else None,
        origin_stop_name=origin_stop_name,
        destination_stop_name=destination_stop_name,
        route_distance_km=route_distance_km,
    )


def _resolve_terminal_stops(
    db: Session,
    route_id: uuid.UUID | None,
    direction: str | object | None,
) -> tuple[str | None, str | None]:
    """
    Resolve origin and destination terminal stops according to route direction.
    A_TO_B: first stop is origin, last stop is destination.
    B_TO_A: last stop is origin, first stop is destination.
    """
    if not route_id:
        return None, None

    rs_stmt = (
        select(RouteStop)
        .options(selectinload(RouteStop.stop))
        .where(RouteStop.route_id == route_id)
        .order_by(RouteStop.sequence_number.asc())
    )
    route_stops = db.execute(rs_stmt).scalars().all()
    if not route_stops:
        return None, None

    first_stop = route_stops[0].stop.name.strip() if route_stops[0].stop and route_stops[0].stop.name else None
    last_stop = route_stops[-1].stop.name.strip() if route_stops[-1].stop and route_stops[-1].stop.name else None

    dir_val = direction.value if hasattr(direction, "value") else str(direction or "")
    if dir_val == "B_TO_A":
        return last_stop, first_stop
    return first_stop, last_stop


def get_operator_trips(db: Session, user: User) -> list[OperatorTripResponse]:
    """
    Retrieve all assigned trips for the authenticated operator for TODAY.
    Restricted to Trip.operating_date == date.today().
    Ordered chronologically by Trip.planned_start_at.asc().

    Deterministic is_next logic:
    1. If an eligible Trip is currently ACTIVE, that trip is next.
    2. Otherwise choose the earliest eligible upcoming trip for today whose planned_start_at has not passed.
    3. COMPLETED, CANCELLED, ABANDONED trips cannot be next.
    4. At most one trip has is_next=true.
    5. If there is no active/upcoming eligible trip, every item has is_next=false.
    """
    today = date.today()
    stmt = (
        select(TripAssignment)
        .join(Trip, TripAssignment.trip_id == Trip.id)
        .options(
            selectinload(TripAssignment.trip)
            .selectinload(Trip.service)
            .selectinload(Service.route),
            selectinload(TripAssignment.trip).selectinload(Trip.vehicle),
        )
        .where(
            TripAssignment.user_id == user.id,
            Trip.operating_date == today,
        )
        .order_by(Trip.planned_start_at.asc())
    )
    assignments = db.execute(stmt).scalars().all()
    if not assignments:
        return []

    trip_items: list[OperatorTripResponse] = []
    terminals_cache: dict[tuple[uuid.UUID, str], tuple[str | None, str | None]] = {}

    for assignment in assignments:
        trip = assignment.trip
        if not trip:
            continue
        service = trip.service
        route = service.route if service else None
        vehicle = trip.vehicle

        route_id = route.id if route else trip.route_id
        dir_val = trip.direction.value if hasattr(trip.direction, "value") else str(trip.direction or "A_TO_B")

        cache_key = (route_id, dir_val)
        if cache_key not in terminals_cache:
            terminals_cache[cache_key] = _resolve_terminal_stops(db, route_id, dir_val)
        origin_name, dest_name = terminals_cache[cache_key]

        trip_status_str = trip.status.value if hasattr(trip.status, "value") else str(trip.status)
        assignment_status_str = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)

        trip_items.append(
            OperatorTripResponse(
                trip_id=trip.id,
                assignment_id=assignment.id,
                service_code=service.service_code if service else "UNKNOWN",
                service_name=service.service_name if service else "Unknown Service",
                route_code=route.route_code if route else "UNKNOWN",
                route_name=route.route_name if route else "Unknown Route",
                direction=dir_val,
                vehicle_number=vehicle.vehicle_number if vehicle else "UNKNOWN",
                vehicle_registration=vehicle.registration_number if vehicle else None,
                vehicle_type=vehicle.vehicle_type if vehicle else None,
                planned_start_at=trip.planned_start_at,
                actual_start_at=trip.actual_start_at,
                actual_end_at=trip.actual_end_at,
                trip_status=trip_status_str,
                assignment_status=assignment_status_str,
                operator_role=assignment.role,
                origin_stop_name=origin_name,
                destination_stop_name=dest_name,
                route_distance_km=route.distance_km if route else None,
                is_next=False,
            )
        )

    # Calculate is_next deterministically
    now_utc = datetime.now(timezone.utc)

    def _to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # Ineligible statuses: COMPLETED, CANCELLED, ABANDONED (or assignment CANCELLED)
    ineligible_trip_statuses = {
        TripStatus.COMPLETED.value,
        TripStatus.CANCELLED.value,
        TripStatus.ABANDONED.value,
    }
    eligible_trips = [
        t for t in trip_items
        if t.trip_status not in ineligible_trip_statuses
        and t.assignment_status != AssignmentStatus.CANCELLED.value
    ]

    active_trips = [
        t for t in eligible_trips
        if t.trip_status in {TripStatus.ACTIVE.value, TripStatus.SUSPECTED_START.value}
    ]

    next_trip_id = None
    if active_trips:
        # Rule 1: If an eligible Trip is currently ACTIVE, that trip is next.
        next_trip_id = active_trips[0].trip_id
    elif eligible_trips:
        # Rule 2: Otherwise choose the earliest eligible upcoming trip for today whose planned_start_at has not passed
        future_trips = [t for t in eligible_trips if _to_utc(t.planned_start_at) >= now_utc]
        if future_trips:
            future_trips.sort(key=lambda x: _to_utc(x.planned_start_at))
            next_trip_id = future_trips[0].trip_id
        else:
            # If planned_start_at has slightly elapsed but trip is still unstarted for today
            eligible_trips.sort(key=lambda x: _to_utc(x.planned_start_at))
            next_trip_id = eligible_trips[0].trip_id

    if next_trip_id:
        for item in trip_items:
            if item.trip_id == next_trip_id:
                item.is_next = True
                break

    return trip_items


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


def report_operator_trip_issue(
    db: Session,
    user: User,
    trip_id: uuid.UUID,
    request: OperatorIssueReportRequest,
) -> OperatorIssueReportResponse:
    """
    Report an operational issue/incident on an assigned trip.

    Authorization checks:
    1. Trip exists (404 if not found).
    2. Tenant isolation: trip belongs to operator's organization (403 if mismatch).
    3. Operator assignment: operator must be assigned to this trip (403 if not).

    Creates an OPEN ServiceAlert with scope=TRIP and type=OPERATOR_REPORTED_ISSUE for Admin triage.
    CRITICAL: Does NOT modify trip status, ETA, route matching, or tracking session.
    """
    stmt = (
        select(Trip)
        .options(selectinload(Trip.service))
        .where(Trip.id == trip_id)
    )
    trip = db.execute(stmt).scalar_one_or_none()
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        )

    if trip.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trip does not belong to operator's organization",
        )

    assignment_stmt = select(TripAssignment).where(
        TripAssignment.user_id == user.id,
        TripAssignment.trip_id == trip_id,
        TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
    )
    assignment = db.execute(assignment_stmt).scalar_one_or_none()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator is not assigned to this trip",
        )

    title = f"Operator Report: {request.issue_type.strip().replace('_', ' ').title()}"
    fingerprint = f"OPERATOR_ISSUE:{trip.id}:{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    alert = ServiceAlert(
        organization_id=trip.organization_id,
        service_id=trip.service_id,
        route_id=trip.route_id,
        trip_id=trip.id,
        scope=AlertScope.TRIP,
        status=AlertStatus.OPEN,
        type="OPERATOR_REPORTED_ISSUE",
        incident_fingerprint=fingerprint,
        title=title,
        message=request.message.strip(),
        severity=request.severity,
        effective_from=now,
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    return OperatorIssueReportResponse(
        alert_id=alert.id,
        trip_id=alert.trip_id,
        service_id=alert.service_id,
        route_id=alert.route_id,
        scope=alert.scope,
        status=alert.status,
        type=alert.type,
        severity=alert.severity,
        title=alert.title,
        message=alert.message,
        created_at=alert.created_at,
        created_by=alert.created_by,
    )

