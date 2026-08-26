"""
Transit Platform — Operator Routes.

BUILD 2: Duty assignment visibility for authenticated operators.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_operator
from app.db.session import get_db
from app.models.user import OperatorProfile, User
from app.schemas.operator import AssignmentResponse
from app.services.operator_service import get_operator_assignment

router = APIRouter(prefix="/api/operator", tags=["operator"])


@router.get("/me/assignment", response_model=AssignmentResponse)
def get_my_assignment(
    operator_ctx: Annotated[tuple[User, OperatorProfile], Depends(get_current_operator)],
    db: Annotated[Session, Depends(get_db)],
) -> AssignmentResponse:
    """Retrieve current/upcoming trip duty assignment for the authenticated operator."""
    user, _ = operator_ctx
    return get_operator_assignment(db, user)
