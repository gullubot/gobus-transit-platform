import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import decode_access_token
from app.intelligence.crowding_engine import CrowdingEngine
from app.models.crowding import CrowdingReport
from app.models.enums import AssignmentStatus, TrackingSessionStatus
from app.models.tracking import TrackingSession
from app.models.trip import TripAssignment
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.crowding import (
    CrowdingReportRequest,
    CrowdingReportResponse,
    PassengerCrowdingResponse,
)

router = APIRouter(tags=["crowding"])

oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/operator/login", auto_error=False)


def get_optional_user(
    token: Annotated[Optional[str], Depends(oauth2_scheme_optional)],
    db: Annotated[Session, Depends(get_db)],
) -> Optional[User]:
    """Return User if token is valid, otherwise None."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user = db.execute(
            select(User).where(User.id == uuid.UUID(user_id_str))
        ).scalar_one_or_none()
        return user if user and user.status == "ACTIVE" else None
    except Exception:
        return None


@router.post("/api/crowding/reports", response_model=CrowdingReportResponse)
def submit_crowding_report(
    request: CrowdingReportRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    x_device_id: Optional[str] = Header(default=None, alias="X-Device-Id"),
):
    """
    Submit a crowding report.
    Source type is derived from the auth context (Operator vs Passenger).
    """
    server_now = datetime.now(timezone.utc)

    # 8. FUTURE TIMESTAMP VALIDATION
    allowed_skew = 300  # seconds
    if (request.observed_at - server_now).total_seconds() > allowed_skew:
        raise HTTPException(status_code=400, detail="observed_at is too far in the future")

    # 9. STALENESS
    age_seconds = (server_now - request.observed_at).total_seconds()
    if age_seconds > 3600:
        raise HTTPException(status_code=400, detail="Report is older than 60 minutes")

    organization_id = None
    if user:
        # Operator flow
        organization_id = user.organization_id

        # 5. OPERATOR AUTHORIZATION
        # Operator must have an active assignment and active tracking session for this vehicle/trip.
        active_assignment = (
            db.execute(
                select(TripAssignment)
                .join(TrackingSession, TrackingSession.trip_id == TripAssignment.trip_id)
                .where(
                    TripAssignment.user_id == user.id,
                    TripAssignment.status == AssignmentStatus.ACTIVE,
                    TrackingSession.device_id == TripAssignment.device_id,
                    TrackingSession.status == TrackingSessionStatus.ACTIVE,
                )
            )
            .scalars()
            .first()
        )

        if not active_assignment:
            raise HTTPException(
                status_code=403, detail="Operator has no active assignment and tracking session"
            )

        # Vehicle must match assignment's trip vehicle
        active_trip = active_assignment.trip
        if (
            active_trip.vehicle_id != request.vehicle_id
            or active_trip.organization_id != organization_id
        ):
            raise HTTPException(
                status_code=403, detail="Requested vehicle/trip does not match active assignment"
            )

    else:
        # Passenger flow
        # 6. PASSENGER IDENTITY - purely for abuse/rate-limit
        if x_device_id:
            try:
                uuid.UUID(x_device_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid X-Device-Id format")

        vehicle = db.execute(
            select(Vehicle).where(Vehicle.id == request.vehicle_id)
        ).scalar_one_or_none()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        organization_id = vehicle.organization_id

    # 13. DUPLICATE IDEMPOTENCY
    existing = db.execute(
        select(CrowdingReport).where(CrowdingReport.report_id == request.report_id)
    ).scalar_one_or_none()
    if existing:
        return CrowdingReportResponse.model_validate(existing)

    # 14. RATE LIMITING
    # Only count NEW report_ids (duplicate check already bypassed above)
    from sqlalchemy import func

    five_mins_ago = server_now - timedelta(minutes=5)

    if user:
        # Operator limit: 5 per 5 mins per vehicle
        recent_count = (
            db.execute(
                select(func.count(CrowdingReport.report_id)).where(
                    CrowdingReport.vehicle_id == request.vehicle_id,
                    CrowdingReport.received_at >= five_mins_ago,
                    CrowdingReport.source_type == "OPERATOR",
                )
            ).scalar()
            or 0
        )
        if recent_count >= 5:
            raise HTTPException(status_code=429, detail="Operator rate limit exceeded")
    else:
        # Passenger limit: 2 per 5 mins per vehicle
        recent_count = (
            db.execute(
                select(func.count(CrowdingReport.report_id)).where(
                    CrowdingReport.vehicle_id == request.vehicle_id,
                    CrowdingReport.received_at >= five_mins_ago,
                    CrowdingReport.source_type == "PASSENGER",
                )
            ).scalar()
            or 0
        )
        if recent_count >= 2:
            raise HTTPException(status_code=429, detail="Passenger rate limit exceeded")

    try:
        response = CrowdingEngine.process_report(
            session=db,
            request=request,
            organization_id=organization_id,
            user_role=user.role if user else None,
        )
        return response
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))




@router.get(
    "/api/passenger/vehicles/{vehicle_id}/crowding", response_model=PassengerCrowdingResponse
)
def get_vehicle_crowding(vehicle_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    """
    Passenger-safe GET endpoint to view current vehicle crowding.
    Masks PII, enforces Operator precedence, applies staleness, and aggregates reports.
    """
    vehicle = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return CrowdingEngine.aggregate_vehicle_crowding(session=db, vehicle_id=vehicle_id)
