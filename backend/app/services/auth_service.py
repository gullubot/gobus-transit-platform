"""
Transit Platform — Authentication Service.

BUILD 2: Operator authentication, role determination, and JWT issuance.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import create_access_token, verify_password
from app.models.enums import UserRole
from app.models.user import OperatorProfile, User
from app.schemas.auth import OperatorLoginRequest, OperatorLoginResponse


def authenticate_operator(db: Session, request: OperatorLoginRequest) -> OperatorLoginResponse:
    """
    Authenticate an operator by employee code and password.

    Server determines:
    authenticated user -> operator profile -> organization context.
    Rejects non-operator roles (FLEET_ADMIN, DEPOT_ADMIN).
    """
    stmt = (
        select(OperatorProfile)
        .options(
            selectinload(OperatorProfile.user).selectinload(User.organization),
        )
        .where(OperatorProfile.employee_code == request.employee_code)
    )
    profile = db.execute(stmt).scalar_one_or_none()

    if profile is None or profile.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee code or password",
        )

    user = profile.user

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator account is inactive",
        )

    if user.role not in (UserRole.DRIVER, UserRole.CONDUCTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role.value}' is not authorized for operator tracking",
        )

    if not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee code or password",
        )

    org = user.organization
    org_name = org.name if org else "Default Organization"
    org_id = user.organization_id or user.id

    access_token = create_access_token(
        subject=str(user.id),
        claims={
            "role": user.role.value,
            "org_id": str(org_id),
            "emp_code": profile.employee_code,
        },
    )

    return OperatorLoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        name=user.name,
        role=user.role.value,
        employee_code=profile.employee_code,
        organization_id=org_id,
        organization_name=org_name,
    )
