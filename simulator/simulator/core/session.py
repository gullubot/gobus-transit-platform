"""
Transit Platform — Simulator Operator Session Model & State Machine.

Tracks runtime state, duty assignment, and monotonic sequence counters.
Never exposes plaintext tokens or passwords in representations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class SimulationMode(str, Enum):
    """Runtime simulation states."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    ASSIGNED = "ASSIGNED"
    TRACKING = "TRACKING"
    STOPPED = "STOPPED"


@dataclass
class AssignmentContext:
    """Parsed operational context from /api/operator/me/assignment."""
    assignment_id: str
    trip_id: str
    service_id: str
    service_code: str
    service_name: str
    route_id: str
    route_code: str
    route_name: str
    direction: str
    vehicle_id: str
    vehicle_number: str
    planned_start_at: str
    trip_status: str
    operator_role: str
    assignment_status: str
    assigned_device_id: Optional[str] = None
    assigned_device_status: Optional[str] = None
    active_tracking_session_id: Optional[str] = None
    tracking_session_status: Optional[str] = None


@dataclass
class OperatorSession:
    """
    Runtime simulator session for an individual simulated operator.
    Maintains in-memory credentials, assignment, and sequence tracking.
    """
    employee_code: str
    user_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None

    # In-memory JWT token (never persisted or printed)
    _access_token: Optional[str] = field(default=None, repr=False)

    mode: SimulationMode = SimulationMode.DISCONNECTED
    assignment: Optional[AssignmentContext] = None

    active_tracking_session_id: Optional[str] = None
    device_id: Optional[str] = None
    device_sequence: int = 0

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    def set_authenticated(
        self,
        token: str,
        user_id: str,
        name: str,
        role: str,
        organization_id: str,
        organization_name: str,
    ) -> None:
        """Sets authentication context and transitions mode."""
        self._access_token = token
        self.user_id = user_id
        self.name = name
        self.role = role
        self.organization_id = organization_id
        self.organization_name = organization_name
        self.mode = SimulationMode.AUTHENTICATED

    def set_assigned(self, assignment: AssignmentContext) -> None:
        """Stores assignment context and transitions mode."""
        self.assignment = assignment
        if assignment.active_tracking_session_id:
            self.active_tracking_session_id = assignment.active_tracking_session_id
        if assignment.assigned_device_id:
            self.device_id = assignment.assigned_device_id
        self.mode = SimulationMode.ASSIGNED

    def set_tracking_started(self, tracking_session_id: str, device_id: str) -> None:
        """Sets tracking session and initializes sequence counter."""
        self.active_tracking_session_id = tracking_session_id
        self.device_id = device_id
        self.device_sequence = 0
        self.mode = SimulationMode.TRACKING

    def set_tracking_ended(self) -> None:
        """Ends active tracking and updates mode."""
        self.active_tracking_session_id = None
        self.mode = SimulationMode.STOPPED

    def clear(self) -> None:
        """Resets session to disconnected state."""
        self._access_token = None
        self.assignment = None
        self.active_tracking_session_id = None
        self.device_sequence = 0
        self.mode = SimulationMode.DISCONNECTED

    def next_sequence(self) -> int:
        """Increments and returns the next monotonic device sequence number."""
        self.device_sequence += 1
        return self.device_sequence

    def safe_summary(self) -> Dict[str, Any]:
        """Provides a safe dictionary for dashboard/logging without secrets."""
        return {
            "employee_code": self.employee_code,
            "mode": self.mode.value,
            "user_id": self.user_id,
            "role": self.role,
            "org_name": self.organization_name,
            "trip_id": self.assignment.trip_id if self.assignment else None,
            "service_code": self.assignment.service_code if self.assignment else None,
            "vehicle_number": self.assignment.vehicle_number if self.assignment else None,
            "tracking_session_id": self.active_tracking_session_id,
            "last_sequence": self.device_sequence,
        }

    def __repr__(self) -> str:
        return (
            f"OperatorSession(employee_code={self.employee_code!r}, "
            f"mode={self.mode.value!r}, "
            f"user_id={self.user_id!r}, "
            f"assigned={self.assignment is not None}, "
            f"tracking_session_id={self.active_tracking_session_id!r}, "
            f"device_sequence={self.device_sequence})"
        )
