"""
Transit Platform — Tracking Ingestion & Trip Lifecycle Routes.

BUILD 2: Explicit trip tracking start/end, batch telemetry ingestion, and device heartbeat.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_operator
from app.db.session import get_db
from app.models.user import OperatorProfile, User
from app.schemas.operator import TripEndResponse, TripStartResponse
from app.schemas.tracking import (
    HeartbeatRequest,
    HeartbeatResponse,
    TrackingBatchRequest,
    TrackingBatchResponse,
)
from app.services.operator_service import end_trip_tracking, start_trip_tracking
from app.services.tracking_service import ingest_telemetry_batch, record_heartbeat

router = APIRouter(tags=["tracking"])


@router.post("/api/trips/{trip_id}/start", response_model=TripStartResponse)
def start_tracking_session(
    trip_id: uuid.UUID,
    operator_ctx: Annotated[tuple[User, OperatorProfile], Depends(get_current_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> TripStartResponse:
    """
    Start an explicit tracking session for an assigned trip.
    Validates operator duty assignment and assigned active device.
    """
    user, _ = operator_ctx
    return start_trip_tracking(db, user, trip_id)


@router.post("/api/trips/{trip_id}/end", response_model=TripEndResponse)
def end_tracking_session(
    trip_id: uuid.UUID,
    operator_ctx: Annotated[tuple[User, OperatorProfile], Depends(get_current_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> TripEndResponse:
    """
    End an active tracking session for an assigned trip.
    Stops telemetry ingestion for the session and records end timestamp.
    """
    user, _ = operator_ctx
    return end_trip_tracking(db, user, trip_id)


@router.post("/api/tracking/batch", response_model=TrackingBatchResponse)
def upload_telemetry_batch(
    request: TrackingBatchRequest,
    operator_ctx: Annotated[tuple[User, OperatorProfile], Depends(get_current_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> TrackingBatchResponse:
    """
    Ingest a batch of telemetry observation packets from an authenticated operator.
    Performs sequence-based deduplication and returns packet-level ACK.
    """
    user, _ = operator_ctx
    return ingest_telemetry_batch(db, user, request)


@router.post("/api/tracking/heartbeat", response_model=HeartbeatResponse)
def send_heartbeat(
    request: HeartbeatRequest,
    operator_ctx: Annotated[tuple[User, OperatorProfile], Depends(get_current_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> HeartbeatResponse:
    """
    Submit device and session health status (battery, network, GPS availability).
    """
    user, _ = operator_ctx
    return record_heartbeat(db, user, request)
