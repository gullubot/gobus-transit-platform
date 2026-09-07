import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_admin, get_db
from app.core.security import get_password_hash
from app.models.enums import AssignmentStatus, TripStatus, UserRole
from app.models.service import Service
from app.models.trip import Trip, TripAssignment
from app.models.user import OperatorProfile, User
from app.models.vehicle import Vehicle
from app.schemas.admin_users import (
    ActiveVehicleSummary,
    AdminUserCreate,
    AdminUserPasswordUpdate,
    AdminUserResponse,
    AdminUserStatusUpdate,
    AdminUserUpdate,
)

router = APIRouter()


def _ensure_role_hierarchy(current_admin: User, target_role: UserRole):
    """Enforce role restrictions for the current admin."""
    if target_role.value == "PASSENGER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot manage passenger accounts from this endpoint.",
        )
    if current_admin.role == UserRole.DEPOT_ADMIN and target_role == UserRole.FLEET_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Depot Admin cannot manage Fleet Admin roles.",
        )


def _enrich_active_vehicles(
    db: Session, org_id: uuid.UUID, users: list[User]
) -> dict[uuid.UUID, ActiveVehicleSummary]:
    """
    Authoritatively resolve current active vehicle assignment for drivers and conductors.
    Only active assignments on planned/active trips in the same organization are returned.
    """
    if not users:
        return {}
    user_ids = [u.id for u in users if u.role in (UserRole.DRIVER, UserRole.CONDUCTOR)]
    if not user_ids:
        return {}

    assign_rows = db.execute(
        select(
            TripAssignment.user_id,
            Vehicle.id.label("vehicle_id"),
            Vehicle.vehicle_number,
            Vehicle.registration_number,
            Service.service_code,
        )
        .join(Trip, TripAssignment.trip_id == Trip.id)
        .join(Vehicle, Trip.vehicle_id == Vehicle.id)
        .outerjoin(Service, Trip.service_id == Service.id)
        .where(
            Trip.organization_id == org_id,
            TripAssignment.user_id.in_(user_ids),
            TripAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE]),
            Trip.status.in_([TripStatus.PLANNED, TripStatus.ACTIVE]),
        )
        .order_by(TripAssignment.assigned_at.desc())
    ).all()

    active_map: dict[uuid.UUID, ActiveVehicleSummary] = {}
    for r in assign_rows:
        if r.user_id not in active_map:
            active_map[r.user_id] = ActiveVehicleSummary(
                id=r.vehicle_id,
                vehicle_number=r.vehicle_number,
                registration_number=r.registration_number,
                service_code=r.service_code,
            )
    return active_map


@router.get("/", response_model=List[AdminUserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
    role: UserRole | None = None,
    user_status: str | None = None,
):
    """List users in the organization with authoritative active vehicle assignments."""
    stmt = (
        select(User)
        .options(selectinload(User.operator_profile))
        .where(User.organization_id == current_admin.organization_id)
        .where(User.role != "PASSENGER")
    )

    if role:
        stmt = stmt.where(User.role == role)
    if user_status:
        stmt = stmt.where(User.status == user_status)

    users = list(db.execute(stmt.order_by(User.created_at.desc())).scalars().all())
    active_map = _enrich_active_vehicles(db, current_admin.organization_id, users)

    result = []
    for u in users:
        resp = AdminUserResponse.model_validate(u)
        resp.active_vehicle = active_map.get(u.id)
        result.append(resp)
    return result


@router.get("/{user_id}", response_model=AdminUserResponse)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Get a specific user in the organization."""
    user = db.execute(
        select(User)
        .options(selectinload(User.operator_profile))
        .where(User.id == user_id, User.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role.value == "PASSENGER":
        raise HTTPException(status_code=404, detail="User not found")

    active_map = _enrich_active_vehicles(db, current_admin.organization_id, [user])
    resp = AdminUserResponse.model_validate(user)
    resp.active_vehicle = active_map.get(user.id)
    return resp


@router.post("/", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: AdminUserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Create a new user (and operator profile if applicable)."""
    _ensure_role_hierarchy(current_admin, user_in.role)

    # Validate email uniqueness if provided
    if user_in.email:
        existing = db.execute(select(User).where(User.email == user_in.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

    db_user = User(
        organization_id=current_admin.organization_id,
        name=user_in.name,
        phone=user_in.phone,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        status="ACTIVE",
    )
    db.add(db_user)
    db.flush()

    if user_in.role in (UserRole.DRIVER, UserRole.CONDUCTOR):
        if not user_in.operator_profile:
            raise HTTPException(
                status_code=400,
                detail="Operator profile is required for DRIVER and CONDUCTOR roles",
            )
            
        # Validate employee_code uniqueness
        existing_emp = db.execute(
            select(OperatorProfile)
            .join(User)
            .where(
                OperatorProfile.employee_code == user_in.operator_profile.employee_code,
                User.organization_id == current_admin.organization_id
            )
        ).scalar_one_or_none()
        if existing_emp:
            raise HTTPException(status_code=400, detail="Employee code already in use in this organization")

        db_profile = OperatorProfile(
            user_id=db_user.id,
            employee_code=user_in.operator_profile.employee_code,
            operator_type=user_in.operator_profile.operator_type,
            verification_status=user_in.operator_profile.verification_status,
        )
        db.add(db_profile)

    db.commit()
    db.refresh(db_user)
    return db_user


@router.put("/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: uuid.UUID,
    user_in: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Update user metadata and optionally operator profile."""
    user = db.execute(
        select(User)
        .options(selectinload(User.operator_profile))
        .where(User.id == user_id, User.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()

    if not user or user.role.value == "PASSENGER":
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.role:
        _ensure_role_hierarchy(current_admin, user_in.role)
        if user_id == current_admin.id and current_admin.role != user_in.role:
            raise HTTPException(status_code=403, detail="Cannot change your own role")
            
        # If changing from admin to operator, ensure operator_profile exists/is created
        if user_in.role in (UserRole.DRIVER, UserRole.CONDUCTOR) and not user.operator_profile:
            if not user_in.employee_code or not user_in.operator_type:
                raise HTTPException(status_code=400, detail="Employee code and operator type required when assigning operator role")
            
            db_profile = OperatorProfile(
                user_id=user.id,
                employee_code=user_in.employee_code,
                operator_type=user_in.operator_type,
            )
            db.add(db_profile)
        user.role = user_in.role

    if user_in.name is not None:
        user.name = user_in.name
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.email is not None:
        user.email = user_in.email

    if user.operator_profile:
        if user_in.employee_code is not None:
             # Validate employee_code uniqueness
            existing_emp = db.execute(
                select(OperatorProfile)
                .join(User)
                .where(
                    OperatorProfile.employee_code == user_in.employee_code,
                    User.organization_id == current_admin.organization_id,
                    OperatorProfile.user_id != user.id
                )
            ).scalar_one_or_none()
            if existing_emp:
                raise HTTPException(status_code=400, detail="Employee code already in use")
            user.operator_profile.employee_code = user_in.employee_code
        if user_in.operator_type is not None:
            user.operator_profile.operator_type = user_in.operator_type

    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/password", response_model=AdminUserResponse)
def update_user_password(
    user_id: uuid.UUID,
    pwd_in: AdminUserPasswordUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Update user password securely."""
    user = db.execute(
        select(User)
        .options(selectinload(User.operator_profile))
        .where(User.id == user_id, User.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()

    if not user or user.role.value == "PASSENGER":
        raise HTTPException(status_code=404, detail="User not found")

    _ensure_role_hierarchy(current_admin, user.role)

    user.password_hash = get_password_hash(pwd_in.password)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/status", response_model=AdminUserResponse)
def update_user_status(
    user_id: uuid.UUID,
    status_in: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Activate, Deactivate, or Suspend a user."""
    user = db.execute(
        select(User)
        .options(selectinload(User.operator_profile))
        .where(User.id == user_id, User.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()

    if not user or user.role.value == "PASSENGER":
        raise HTTPException(status_code=404, detail="User not found")

    _ensure_role_hierarchy(current_admin, user.role)
    
    if user_id == current_admin.id and status_in.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Cannot deactivate your own account")
        
    if status_in.status not in ("ACTIVE", "INACTIVE", "SUSPENDED"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    user.status = status_in.status
    db.commit()
    db.refresh(user)
    return user
