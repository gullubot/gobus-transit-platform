"""
Transit Platform — FastAPI Dependencies.

BUILD 2: Authentication, authorization, and database session injection.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import OperatorProfile, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/operator/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Validate JWT token and return authenticated User with operator_profile loaded."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (PyJWTError, ValueError):
        raise credentials_exception

    stmt = (
        select(User)
        .options(selectinload(User.operator_profile), selectinload(User.organization))
        .where(User.id == user_id)
    )
    user = db.execute(stmt).scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def get_current_operator(
    current_user: Annotated[User, Depends(get_current_user)],
) -> tuple[User, OperatorProfile]:
    """
    Ensure the authenticated user is an active DRIVER or CONDUCTOR with a valid operator profile.
    Fleet/Depot admins are rejected from operator tracking endpoints.
    """
    if current_user.role not in (UserRole.DRIVER, UserRole.CONDUCTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role.value}' is not authorized for operator tracking",
        )

    if not current_user.operator_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator profile is missing for this account",
        )

    return current_user, current_user.operator_profile

def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Ensure the authenticated user is an active FLEET_ADMIN or DEPOT_ADMIN.
    """
    if current_user.role not in (UserRole.FLEET_ADMIN, UserRole.DEPOT_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role.value}' is not authorized for administration",
        )
    return current_user

def get_fleet_admin(
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> User:
    """
    Ensure the authenticated admin is specifically a FLEET_ADMIN.
    """
    if current_admin.role != UserRole.FLEET_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Fleet Admins can perform this action",
        )
    return current_admin
