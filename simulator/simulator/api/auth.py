"""
Transit Platform — Operator Authentication Client.

Sends JSON credentials to POST /api/auth/operator/login and updates
the in-memory OperatorSession without persisting secrets to disk or logs.
"""

from typing import Any, Dict
from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import AuthenticationError
from simulator.core.session import OperatorSession
from simulator.utils.logging import get_logger

logger = get_logger("auth")


def operator_login(
    client: GoBusHttpClient,
    session: OperatorSession,
    password: str,
) -> Dict[str, Any]:
    """
    Authenticates operator with GoBus backend using JSON credentials.
    Updates the session with JWT access token and user profile.
    """
    if not session.employee_code:
        raise AuthenticationError("Cannot login: operator employee_code is missing")
    if not password:
        raise AuthenticationError("Cannot login: password is empty")

    payload = {
        "employee_code": session.employee_code,
        "password": password,
    }

    logger.info(f"Authenticating operator '{session.employee_code}'...")
    response_data = client.post("/api/auth/operator/login", json_data=payload)

    access_token = response_data.get("access_token")
    if not access_token or not isinstance(access_token, str):
        raise AuthenticationError("Server response did not contain a valid 'access_token'")

    user_id = str(response_data.get("user_id", ""))
    name = str(response_data.get("name", ""))
    role = str(response_data.get("role", ""))
    org_id = str(response_data.get("organization_id", ""))
    org_name = str(response_data.get("organization_name", ""))

    session.set_authenticated(
        token=access_token,
        user_id=user_id,
        name=name,
        role=role,
        organization_id=org_id,
        organization_name=org_name,
    )

    logger.info(
        f"Operator '{session.employee_code}' successfully authenticated "
        f"[Role={role}, Org='{org_name}', UserId={user_id[:8]}...]"
    )
    return response_data


def operator_logout(session: OperatorSession) -> None:
    """Clears in-memory authentication and tracking state."""
    logger.info(f"Logging out operator '{session.employee_code}'")
    session.clear()
