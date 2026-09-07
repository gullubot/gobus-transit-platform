"""
Transit Platform — Duty Assignment Discovery Client.

Fetches and parses duty assignment details from GET /api/operator/me/assignment.
"""

from typing import Any, Dict
from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import AssignmentNotFoundError, AuthenticationError
from simulator.core.session import AssignmentContext, OperatorSession
from simulator.utils.logging import get_logger

logger = get_logger("assignment")


def fetch_operator_assignment(
    client: GoBusHttpClient,
    session: OperatorSession,
) -> AssignmentContext:
    """
    Fetches the current duty assignment for the authenticated operator.
    Updates the session's assignment context.
    """
    if not session.access_token:
        raise AuthenticationError("Cannot fetch assignment: operator is not authenticated")

    logger.info(f"Fetching duty assignment for operator '{session.employee_code}'...")
    try:
        data = client.get("/api/operator/me/assignment", token=session.access_token)
    except AssignmentNotFoundError:
        logger.warning(f"No active or upcoming trip duty assignment found for operator '{session.employee_code}'")
        raise AssignmentNotFoundError(
            f"No active or upcoming trip assignment found for operator '{session.employee_code}'. "
            "Please dispatch a trip to this operator in GoBus Admin Web first."
        )

    assignment = AssignmentContext(
        assignment_id=str(data["assignment_id"]),
        trip_id=str(data["trip_id"]),
        service_id=str(data["service_id"]),
        service_code=str(data.get("service_code", "UNKNOWN")),
        service_name=str(data.get("service_name", "Unknown Service")),
        route_id=str(data["route_id"]),
        route_code=str(data.get("route_code", "UNKNOWN")),
        route_name=str(data.get("route_name", "Unknown Route")),
        direction=str(data.get("direction", "A_TO_B")),
        vehicle_id=str(data["vehicle_id"]),
        vehicle_number=str(data.get("vehicle_number", "UNKNOWN")),
        planned_start_at=str(data.get("planned_start_at", "")),
        trip_status=str(data.get("trip_status", "PLANNED")),
        operator_role=str(data.get("operator_role", "DRIVER")),
        assignment_status=str(data.get("assignment_status", "ASSIGNED")),
        assigned_device_id=data.get("assigned_device_id"),
        assigned_device_status=data.get("assigned_device_status"),
        active_tracking_session_id=data.get("active_tracking_session_id"),
        tracking_session_status=data.get("tracking_session_status"),
    )

    session.set_assigned(assignment)
    logger.info(
        f"Assignment retrieved: Service={assignment.service_code} ({assignment.service_name}), "
        f"Route={assignment.route_code}, Vehicle={assignment.vehicle_number}, "
        f"Direction={assignment.direction}, TripId={assignment.trip_id[:8]}..."
    )
    return assignment
