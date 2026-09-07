from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_admin
from app.models.user import User
from app.schemas.auth import AdminLoginRequest, AdminLoginResponse
from app.services.auth_service import authenticate_admin

router = APIRouter()

@router.post("/login", response_model=AdminLoginResponse)
def login_admin(
    request: AdminLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate an administrator and return a JWT token.
    """
    return authenticate_admin(db, request)

@router.get("/me", response_model=AdminLoginResponse)
def get_admin_me(
    current_admin: User = Depends(get_current_admin),
):
    """
    Get current admin profile using token.
    """
    org_id = current_admin.organization_id
    org_name = current_admin.organization.name if current_admin.organization else None
    
    return AdminLoginResponse(
        access_token="", # Usually omit token on /me but schema requires it
        token_type="bearer",
        user_id=current_admin.id,
        name=current_admin.name,
        email=current_admin.email or "",
        role=current_admin.role.value,
        organization_id=org_id,
        organization_name=org_name,
    )
