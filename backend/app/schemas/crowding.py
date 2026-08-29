import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import CrowdingSource, CrowdingState


class CrowdingReportRequest(BaseModel):
    """
    Client payload for a crowding report.
    Source type MUST NOT be supplied by the client; it is server-derived.
    """

    report_id: uuid.UUID = Field(..., description="Unique ID for the report (idempotency key).")
    vehicle_id: uuid.UUID = Field(..., description="The vehicle being reported on.")
    crowding_state: CrowdingState = Field(..., description="The reported crowding state.")
    confidence: float = Field(..., description="Confidence of the report (0.0 to 1.0).")
    observed_at: datetime = Field(..., description="When the observation was made.")
    # Notice: No source_type.


class CrowdingReportResponse(BaseModel):
    """
    Response returned to the client upon successful submission.
    """

    report_id: uuid.UUID
    vehicle_id: uuid.UUID
    trip_id: Optional[uuid.UUID]
    crowding_state: CrowdingState
    confidence: float
    observed_at: datetime
    received_at: datetime
    source_type: CrowdingSource

    model_config = {"from_attributes": True}


class PassengerCrowdingResponse(BaseModel):
    """
    Passenger-safe output format. Masks all PII and internal identifiers.
    """

    state: CrowdingState
    confidence: float = Field(..., ge=0.0, le=1.0)
    observed_at: datetime
    evidence_type: str = Field(..., description="E.g., OPERATOR, PASSENGER, HISTORICAL_BASELINE")
    stale: bool
