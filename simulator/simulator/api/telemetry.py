"""
Transit Platform — Batch Telemetry Ingestion Client.

Formats telemetry packets with UUIDs, UTC timestamps, and strictly monotonic
sequence numbers matching the verified POST /api/tracking/batch contract.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import AuthenticationError, TelemetryBatchError
from simulator.core.session import OperatorSession
from simulator.utils.logging import get_logger

logger = get_logger("telemetry")


@dataclass
class RejectedPacket:
    """Details for a rejected packet."""
    packet_id: str
    reason: str


@dataclass
class BatchAckResult:
    """Acknowledged telemetry batch upload result."""
    accepted: List[str] = field(default_factory=list)
    duplicates: List[str] = field(default_factory=list)
    retryable: List[str] = field(default_factory=list)
    rejected: List[RejectedPacket] = field(default_factory=list)

    @property
    def is_fully_accepted(self) -> bool:
        return len(self.rejected) == 0 and len(self.retryable) == 0


def create_telemetry_packet(
    latitude: float,
    longitude: float,
    device_sequence: int,
    speed_mps: Optional[float] = None,
    heading: Optional[float] = None,
    accuracy_m: Optional[float] = 5.0,
    observed_at: Optional[datetime] = None,
    battery_level: Optional[float] = 95.0,
    network_type: Optional[str] = "CELLULAR",
    gps_status: Optional[str] = "AVAILABLE",
    packet_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Constructs a validated single telemetry observation packet.
    CRITICAL: Never includes vehicle_id or route_id.
    """
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(f"Invalid latitude: {latitude}. Must be between -90 and 90.")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(f"Invalid longitude: {longitude}. Must be between -180 and 180.")

    if observed_at is None:
        observed_at = datetime.now(timezone.utc)
    elif observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    # Format timestamp as ISO-8601 with milliseconds and 'Z'
    timestamp_str = observed_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    packet = {
        "packet_id": packet_id or str(uuid.uuid4()),
        "latitude": round(float(latitude), 6),
        "longitude": round(float(longitude), 6),
        "device_sequence": int(device_sequence),
        "observed_at": timestamp_str,
    }

    if accuracy_m is not None:
        packet["accuracy_m"] = round(float(accuracy_m), 1)
    if speed_mps is not None:
        packet["speed_mps"] = round(float(speed_mps), 2)
    if heading is not None:
        packet["heading"] = round(float(heading), 1)
    if battery_level is not None:
        packet["battery_level"] = round(float(battery_level), 1)
    if network_type is not None:
        packet["network_type"] = str(network_type)[:20]
    if gps_status is not None:
        packet["gps_status"] = str(gps_status)[:20]

    return packet


def send_telemetry_batch(
    client: GoBusHttpClient,
    session: OperatorSession,
    packets: List[Dict[str, Any]],
    session_id: Optional[str] = None,
) -> BatchAckResult:
    """
    Uploads a batch of telemetry observation packets to POST /api/tracking/batch.
    Returns parsed BatchAckResult.
    """
    if not session.access_token:
        raise AuthenticationError("Cannot send telemetry: operator is not authenticated")
    if not packets:
        raise ValueError("Cannot send telemetry: packets list is empty")
    if len(packets) > 500:
        raise ValueError(f"Batch size exceeds maximum limit of 500: got {len(packets)}")

    active_session_id = session_id or session.active_tracking_session_id
    payload: Dict[str, Any] = {"packets": packets}
    if active_session_id:
        payload["session_id"] = active_session_id

    logger.debug(f"Uploading telemetry batch of {len(packets)} packet(s)...")
    try:
        response_data = client.post(
            "/api/tracking/batch",
            json_data=payload,
            token=session.access_token,
        )
    except Exception as e:
        logger.error(f"Telemetry batch upload failed: {e}")
        raise

    accepted = [str(pid) for pid in response_data.get("accepted", [])]
    duplicates = [str(pid) for pid in response_data.get("duplicates", [])]
    retryable = [str(pid) for pid in response_data.get("retryable", [])]
    rejected = [
        RejectedPacket(
            packet_id=str(r.get("packet_id")),
            reason=str(r.get("reason", "Unknown")),
        )
        for r in response_data.get("rejected", [])
    ]

    result = BatchAckResult(
        accepted=accepted,
        duplicates=duplicates,
        retryable=retryable,
        rejected=rejected,
    )

    logger.info(
        f"Telemetry ACK: accepted={len(accepted)}, duplicates={len(duplicates)}, "
        f"retryable={len(retryable)}, rejected={len(rejected)}"
    )

    if rejected:
        for rej in rejected:
            logger.warning(f"Packet {rej.packet_id} rejected by server: {rej.reason}")

    return result
