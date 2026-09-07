"""
Transit Platform — Crowding Ingestion Client.

Submits operator crowding assessments matching the verified schema
POST /api/crowding/reports (using crowding_state and confidence, NOT 'level').
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
import uuid

from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import AuthenticationError, RateLimitExceededError
from simulator.core.session import OperatorSession
from simulator.utils.logging import get_logger

logger = get_logger("crowding")

VALID_CROWDING_STATES: Set[str] = {"UNKNOWN", "LOW", "MODERATE", "HIGH", "FULL"}


def submit_crowding_report(
    client: GoBusHttpClient,
    session: OperatorSession,
    vehicle_id: Optional[str] = None,
    crowding_state: str = "MODERATE",
    confidence: float = 0.9,
    observed_at: Optional[datetime] = None,
    report_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submits a crowding report to POST /api/crowding/reports.
    CRITICAL: Uses verified fields 'crowding_state' and 'confidence'.
    Never sends 'level' or 'source_type'.
    """
    if not session.access_token:
        raise AuthenticationError("Cannot submit crowding report: operator is not authenticated")

    target_vehicle_id = vehicle_id or (session.assignment.vehicle_id if session.assignment else None)
    if not target_vehicle_id:
        raise ValueError("Cannot submit crowding report: vehicle_id is missing or unassigned")

    normalized_state = crowding_state.upper()
    if normalized_state not in VALID_CROWDING_STATES:
        raise ValueError(
            f"Invalid crowding_state: {crowding_state}. Must be one of {sorted(VALID_CROWDING_STATES)}"
        )

    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

    if observed_at is None:
        observed_at = datetime.now(timezone.utc)
    elif observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    timestamp_str = observed_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    target_report_id = report_id or str(uuid.uuid4())

    payload = {
        "report_id": target_report_id,
        "vehicle_id": target_vehicle_id,
        "crowding_state": normalized_state,
        "confidence": round(float(confidence), 2),
        "observed_at": timestamp_str,
    }

    logger.info(
        f"Submitting crowding report [Vehicle={target_vehicle_id[:8]}..., "
        f"State={normalized_state}, Confidence={confidence}]..."
    )
    try:
        data = client.post(
            "/api/crowding/reports",
            json_data=payload,
            token=session.access_token,
        )
        logger.info(f"Crowding report accepted: ReportId={target_report_id[:8]}...")
        return data
    except RateLimitExceededError as e:
        logger.warning(f"Crowding report rate limit exceeded: {e}")
        raise
    except Exception as e:
        logger.error(f"Crowding report submission failed: {e}")
        raise
