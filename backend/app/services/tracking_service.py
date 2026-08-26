"""
Transit Platform — Telemetry Ingestion Service.

BUILD 2: High-integrity batch telemetry ingestion, sequence-based deduplication,
packet-level ACK response, and device heartbeat.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.enums import DeviceStatus, TrackingSessionStatus, ValidationStatus
from app.models.tracking import TrackingEvent, TrackingSession
from app.models.user import User
from app.schemas.tracking import (
    HeartbeatRequest,
    HeartbeatResponse,
    RejectedPacketDetail,
    TrackingBatchRequest,
    TrackingBatchResponse,
)


def get_active_session_for_operator(
    db: Session, user: User, session_id: uuid.UUID | None = None
) -> TrackingSession:
    """Retrieve and validate the active tracking session for an operator."""
    if session_id:
        session = db.get(TrackingSession, session_id)
        if session is None or session.operator_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tracking session not found or does not belong to this operator",
            )
    else:
        stmt = (
            select(TrackingSession)
            .where(
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
        session = db.execute(stmt).scalars().first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active tracking session found for this operator. Start a trip first.",
        )

    if session.status == TrackingSessionStatus.ENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tracking session has already ended",
        )

    # Verify device status
    device = db.get(Device, session.device_id)
    if device is None or device.status != DeviceStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tracking device is not active or unauthorized",
        )

    return session


def ingest_telemetry_batch(
    db: Session, user: User, request: TrackingBatchRequest
) -> TrackingBatchResponse:
    """
    Ingest a batch of telemetry observation packets.

    Validation Rules:
    1. Authenticated operator with an active TrackingSession
    2. Coordinates valid (-90 <= lat <= 90, -180 <= lon <= 180)
    3. Global packet_id deduplication (idempotency)
    4. Monotonic device_sequence deduplication within session
    5. Stores immutable TrackingEvent with server-generated received_at
    6. Returns packet-level ACK (accepted, duplicates, retryable, rejected)
    """
    session = get_active_session_for_operator(db, user, request.session_id)
    now = datetime.now(timezone.utc)

    # If session was OFFLINE or SYNCING, restore to ACTIVE on receipt of data
    if session.status in (TrackingSessionStatus.OFFLINE, TrackingSessionStatus.SYNCING):
        session.status = TrackingSessionStatus.ACTIVE
        session.updated_at = now

    accepted: list[uuid.UUID] = []
    duplicates: list[uuid.UUID] = []
    retryable: list[uuid.UUID] = []
    rejected: list[RejectedPacketDetail] = []

    # Pre-fetch existing packet_ids in this batch for efficient dedup
    incoming_packet_ids = [p.packet_id for p in request.packets]
    existing_packets_stmt = select(TrackingEvent.packet_id).where(
        TrackingEvent.packet_id.in_(incoming_packet_ids)
    )
    existing_packet_ids = set(db.execute(existing_packets_stmt).scalars().all())

    # Pre-fetch existing sequences for this device + session
    incoming_sequences = [p.device_sequence for p in request.packets]
    existing_seqs_stmt = select(TrackingEvent.device_sequence).where(
        TrackingEvent.device_id == session.device_id,
        TrackingEvent.tracking_session_id == session.id,
        TrackingEvent.device_sequence.in_(incoming_sequences),
    )
    existing_sequences = set(db.execute(existing_seqs_stmt).scalars().all())

    events_to_add: list[TrackingEvent] = []

    for packet in request.packets:
        # 1. Validate coordinate bounds
        if not (-90.0 <= packet.latitude <= 90.0) or not (-180.0 <= packet.longitude <= 180.0):
            rejected.append(
                RejectedPacketDetail(
                    packet_id=packet.packet_id,
                    reason=(
                        f"Coordinates out of range: lat={packet.latitude}, lon={packet.longitude}"
                    ),
                )
            )
            continue

        # 2. Global packet_id deduplication
        if packet.packet_id in existing_packet_ids:
            duplicates.append(packet.packet_id)
            continue

        # 3. Device sequence deduplication within session
        if packet.device_sequence in existing_sequences:
            duplicates.append(packet.packet_id)
            continue

        # 4. Valid and new observation — create immutable TrackingEvent
        event = TrackingEvent(
            id=uuid.uuid4(),
            packet_id=packet.packet_id,
            tracking_session_id=session.id,
            trip_id=session.trip_id,
            device_id=session.device_id,
            operator_id=user.id,
            latitude=packet.latitude,
            longitude=packet.longitude,
            accuracy_m=packet.accuracy_m,
            speed_mps=packet.speed_mps,
            heading=packet.heading,
            observed_at=packet.observed_at,
            received_at=now,  # Authoritative server receipt timestamp
            device_sequence=packet.device_sequence,
            battery_level=packet.battery_level,
            network_type=packet.network_type,
            gps_status=packet.gps_status,
            validation_status=ValidationStatus.VALID,
            created_at=now,
        )
        events_to_add.append(event)
        existing_packet_ids.add(packet.packet_id)
        existing_sequences.add(packet.device_sequence)
        accepted.append(packet.packet_id)

    if events_to_add:
        db.add_all(events_to_add)

    # Update device last_seen_at and battery
    device = db.get(Device, session.device_id)
    if device:
        device.last_seen_at = now
        if request.packets:
            last_pkt = request.packets[-1]
            if last_pkt.battery_level is not None:
                device.battery_level = last_pkt.battery_level
            if last_pkt.network_type is not None:
                device.network_status = last_pkt.network_type
            if last_pkt.gps_status is not None:
                device.gps_permission_status = last_pkt.gps_status

    db.commit()

    return TrackingBatchResponse(
        accepted=accepted,
        duplicates=duplicates,
        retryable=retryable,
        rejected=rejected,
    )


def record_heartbeat(db: Session, user: User, request: HeartbeatRequest) -> HeartbeatResponse:
    """Record a lightweight device and session health heartbeat."""
    session = None
    if request.session_id:
        session = db.get(TrackingSession, request.session_id)

    if session is None:
        stmt = (
            select(TrackingSession)
            .where(
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
        session = db.execute(stmt).scalars().first()

    now = datetime.now(timezone.utc)

    if session and session.device_id:
        device = db.get(Device, session.device_id)
        if device:
            device.last_seen_at = now
            if request.battery_level is not None:
                device.battery_level = request.battery_level
            if request.network_type is not None:
                device.network_status = request.network_type
            if request.gps_status is not None:
                device.gps_permission_status = request.gps_status
            if request.app_version is not None:
                device.app_version = request.app_version
            db.commit()

    device_status = "ACTIVE"
    session_status_str = session.status.value if session else None

    return HeartbeatResponse(
        status="ok",
        received_at=now,
        device_status=device_status,
        session_status=session_status_str,
    )
