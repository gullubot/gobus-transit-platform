from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.enums import UserRole, VerificationStatus

class OperatorProfileCreate(BaseModel):
    employee_code: str = Field(..., max_length=50)
    operator_type: str = Field(..., max_length=20)
    verification_status: VerificationStatus = VerificationStatus.PENDING

class OperatorProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    employee_code: str
    operator_type: str
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AdminUserCreate(BaseModel):
    name: str = Field(..., max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = None
    password: str = Field(..., min_length=4, max_length=255)
    role: UserRole
    operator_profile: Optional[OperatorProfileCreate] = None

class AdminUserUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = None
    role: Optional[UserRole] = None
    employee_code: Optional[str] = Field(None, max_length=50)
    operator_type: Optional[str] = Field(None, max_length=20)

class AdminUserPasswordUpdate(BaseModel):
    password: str = Field(..., min_length=4, max_length=255)

class AdminUserStatusUpdate(BaseModel):
    status: str = Field(..., max_length=20)  # ACTIVE, INACTIVE, SUSPENDED

class ActiveVehicleSummary(BaseModel):
    id: UUID
    vehicle_number: str
    registration_number: Optional[str] = None
    service_code: Optional[str] = None

    class Config:
        from_attributes = True


class AdminUserResponse(BaseModel):
    id: UUID
    organization_id: Optional[UUID]
    name: str
    phone: Optional[str]
    email: Optional[str]
    role: UserRole
    status: str
    created_at: datetime
    updated_at: datetime
    operator_profile: Optional[OperatorProfileResponse] = None
    active_vehicle: Optional[ActiveVehicleSummary] = None

    class Config:
        from_attributes = True
