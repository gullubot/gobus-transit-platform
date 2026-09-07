"""
Transit Platform — Device Heartbeat Client.

Submits periodic device health status to POST /api/tracking/heartbeat.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import AuthenticationError
from simulator.core.session import OperatorSession
from simulator.utils.logging import get_logger

logger = get_logger("heartbeat")


def send_device_heartbeat(
    client: GoBusHttpClient,
    session: OperatorSession,
    battery_level: Optional[float] = 95.0,
    network_type: Optional[str] = "CELLULAR",
    gps_status: Optional[str] = "AVAILABLE",
    app_version: Optional[str] = "1.0.0",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submits a device status heartbeat to the GoBus backend.
    """
    if not session.access_token:
        raise AuthenticationError("Cannot send heartbeat: operator is not authenticated")

    active_session_id = session_id or session.active_tracking_session_id
    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    payload: Dict[str, Any] = {
        "timestamp": timestamp_str,
    }
    if active_session_id:
        payload["session_id"] = active_session_id
    if battery_level is not None:
        payload["battery_level"] = round(float(battery_level), 1)
    if network_type is not None:
        payload["network_type"] = str(network_type)[:20]
    if gps_status is not None:
        payload["gps_status"] = str(gps_status)[:20]
    if app_version is not None:
        payload["app_version"] = str(app_version)[:50]

    logger.debug(f"Sending heartbeat for session {active_session_id or 'unknown'}...")
    try:
        data = client.post(
            "/api/tracking/heartbeat",
            json_data=payload,
            token=session.access_token,
        )
        logger.info(
            f"Heartbeat acknowledged [Status={data.get('status')}, "
            f"DeviceStatus={data.get('device_status')}, "
            f"SessionStatus={data.get('session_status')}]"
        )
        return data
    except Exception as e:
        logger.warning(f"Heartbeat submission failed: {e}")
        raise
