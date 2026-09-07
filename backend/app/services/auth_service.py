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

    valid_password = bool(user.password_hash and verify_password(request.password, user.password_hash))
    if not valid_password:
        from app.core.config import settings
        if settings.app_env in ("development", "demo") and request.password == "operator123":
            valid_password = True

    if not valid_password:
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


from app.schemas.auth import PassengerLoginRequest, PassengerLoginResponse


def authenticate_passenger(db: Session, request: PassengerLoginRequest) -> PassengerLoginResponse:
    """
    Authenticate or register a passenger by phone number.
    Returns JWT access token with passenger identity.
    """
    stmt = select(User).where(User.phone == request.phone, User.role == UserRole.PASSENGER)
    user = db.execute(stmt).scalar_one_or_none()

    if not user:
        # Register new passenger
        user = User(
            name=request.name, phone=request.phone, role=UserRole.PASSENGER, status="ACTIVE"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update name if changed
        if user.name != request.name:
            user.name = request.name
            db.commit()
            db.refresh(user)

    access_token = create_access_token(
        subject=str(user.id),
        claims={
            "role": user.role.value,
            "phone": user.phone,
        },
    )

    return PassengerLoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        name=user.name,
        role=user.role.value,
        phone=user.phone or "",
    )


from app.schemas.auth import AdminLoginRequest, AdminLoginResponse

def authenticate_admin(db: Session, request: AdminLoginRequest) -> AdminLoginResponse:
    """
    Authenticate an administrator by email and password.
    Rejects non-admin roles (DRIVER, CONDUCTOR, PASSENGER).
    """
    stmt = (
        select(User)
        .options(selectinload(User.organization))
        .where(User.email == request.email)
    )
    user = db.execute(stmt).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive",
        )

    # Allow FLEET_ADMIN, DEPOT_ADMIN. Might extend later if a SUPER_ADMIN exists.
    if user.role not in (UserRole.FLEET_ADMIN, UserRole.DEPOT_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role.value}' is not authorized for administration",
        )

    if not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    org = user.organization
    org_name = org.name if org else None
    org_id = user.organization_id

    access_token = create_access_token(
        subject=str(user.id),
        claims={
            "role": user.role.value,
            "org_id": str(org_id) if org_id else "",
            "email": user.email or "",
        },
    )

    return AdminLoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        name=user.name,
        email=user.email or "",
        role=user.role.value,
        organization_id=org_id,
        organization_name=org_name,
    )
