"""
Transit Platform — Authentication Schemas.

BUILD 2: Operator login request, response, and token payload models.
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class OperatorLoginRequest(BaseModel):
    """Operator authentication credentials."""

    employee_code: str = Field(
        ..., min_length=1, max_length=50, description="Operator employee code"
    )
    password: str = Field(..., min_length=1, description="Operator password")


class OperatorLoginResponse(BaseModel):
    """Successful operator authentication response."""

    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    name: str
    role: str
    employee_code: str
    organization_id: uuid.UUID
    organization_name: str

    model_config = ConfigDict(from_attributes=True)


class TokenPayload(BaseModel):
    """JWT payload structure."""

    sub: str  # user_id as str
    role: str
    org_id: str
    emp_code: str
    exp: int
    iat: int


class PassengerLoginRequest(BaseModel):
    """Passenger authentication credentials."""

    phone: str = Field(..., min_length=5, max_length=20, description="Passenger phone number")
    name: str = Field(..., min_length=1, max_length=255, description="Passenger name")


class PassengerLoginResponse(BaseModel):
    """Successful passenger authentication response."""

    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    name: str
    role: str
    phone: str

    model_config = ConfigDict(from_attributes=True)


class AdminLoginRequest(BaseModel):
    """Admin authentication credentials."""

    email: str = Field(..., min_length=5, max_length=255, description="Admin email address")
    password: str = Field(..., min_length=1, description="Admin password")


class AdminLoginResponse(BaseModel):
    """Successful admin authentication response."""

    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    name: str
    email: str
    role: str
    organization_id: uuid.UUID | None
    organization_name: str | None

    model_config = ConfigDict(from_attributes=True)
