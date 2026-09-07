import uuid
from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class FareSlabBase(BaseModel):
    min_distance_km: Decimal = Field(..., ge=0)
    max_distance_km: Optional[Decimal] = Field(None, gt=0)
    fare_amount: Decimal = Field(..., ge=0)


class FareSlabCreate(FareSlabBase):
    pass


class FareSlabResponse(FareSlabBase):
    id: uuid.UUID
    fare_configuration_id: uuid.UUID

    model_config = {"from_attributes": True}


class FareConfigurationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    currency: str = Field("INR", min_length=3, max_length=3)
    effective_from: date
    effective_until: Optional[date] = None


class FareConfigurationCreate(FareConfigurationBase):
    slabs: List[FareSlabCreate]


class FareConfigurationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None
    slabs: Optional[List[FareSlabCreate]] = None


class FareConfigurationResponse(FareConfigurationBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    slabs: List[FareSlabResponse]
    service_id: Optional[uuid.UUID] = None
    service_code: Optional[str] = None
    service_name: Optional[str] = None

    model_config = {"from_attributes": True}


class FarePreviewRequest(BaseModel):
    service_id: uuid.UUID
    origin_stop_id: uuid.UUID
    destination_stop_id: uuid.UUID


class MatchedSlabResponse(BaseModel):
    id: uuid.UUID
    min_distance_km: float
    max_distance_km: Optional[float]
    fare_amount: float


class FareCalculationResponse(BaseModel):
    distance_km: float
    fare_amount: float
    currency: str
    matched_slab: MatchedSlabResponse
    fare_configuration_id: uuid.UUID
    fare_configuration_name: str
