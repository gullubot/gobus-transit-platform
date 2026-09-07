"""
Transit Platform — Trip Tracking Lifecycle Client.

Manages explicit session start and end via POST /api/trips/{trip_id}/start and /end.
"""

from typing import Any, Dict, Optional
from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import AuthenticationError, TripSessionError
from simulator.core.session import OperatorSession
from simulator.utils.logging import get_logger

logger = get_logger("trip")


def start_trip_tracking(
    client: GoBusHttpClient,
    session: OperatorSession,
    trip_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Activates an explicit tracking session for an assigned trip.
    Updates the session with the resulting tracking_session_id and device_id.
    """
    if not session.access_token:
        raise AuthenticationError("Cannot start trip: operator is not authenticated")

    target_trip_id = trip_id or (session.assignment.trip_id if session.assignment else None)
    if not target_trip_id:
        raise TripSessionError("Cannot start trip: no trip_id provided or assigned")

    logger.info(f"Starting tracking session for trip {target_trip_id}...")
    try:
        data = client.post(
            f"/api/trips/{target_trip_id}/start",
            json_data={},
            token=session.access_token,
        )
    except Exception as e:
        logger.error(f"Failed to start trip tracking: {e}")
        raise

    tracking_session_id = str(data["tracking_session_id"])
    device_id = str(data.get("device_id", ""))
    status = str(data.get("status", "ACTIVE"))

    session.set_tracking_started(tracking_session_id, device_id)
    logger.info(
        f"Trip tracking session started [SessionId={tracking_session_id[:8]}..., "
        f"Status={status}, DeviceId={device_id[:8]}...]"
    )
    return data


def end_trip_tracking(
    client: GoBusHttpClient,
    session: OperatorSession,
    trip_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ends an active tracking session for an assigned trip.
    Marks session mode as STOPPED.
    """
    if not session.access_token:
        raise AuthenticationError("Cannot end trip: operator is not authenticated")

    target_trip_id = trip_id or (session.assignment.trip_id if session.assignment else None)
    if not target_trip_id:
        raise TripSessionError("Cannot end trip: no trip_id provided or assigned")

    logger.info(f"Ending tracking session for trip {target_trip_id}...")
    try:
        data = client.post(
            f"/api/trips/{target_trip_id}/end",
            json_data={},
            token=session.access_token,
        )
    except Exception as e:
        logger.error(f"Failed to end trip tracking: {e}")
        raise

    session.set_tracking_ended()
    logger.info(f"Trip tracking session ended for trip {target_trip_id[:8]}...")
    return data
