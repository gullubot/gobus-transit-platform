"""
Transit Platform — Authentication Routes.

BUILD 2: Operator login endpoint.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import OperatorLoginRequest, OperatorLoginResponse
from app.services.auth_service import authenticate_operator

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/operator/login", response_model=OperatorLoginResponse)
def operator_login(
    request: OperatorLoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> OperatorLoginResponse:
    """
    Authenticate an operator (Driver / Conductor) by employee credentials.
    Returns JWT access token with operator identity and organization context.
    """
    return authenticate_operator(db, request)
