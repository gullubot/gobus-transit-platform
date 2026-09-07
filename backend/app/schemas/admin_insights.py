import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class InsightEvidence(BaseModel):
    statement: str = Field(..., description="Fact-based evidence statement.")
    total_observations: Optional[int] = None
    matched_observations: Optional[int] = None
    ratio: Optional[float] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None


class InsightSuggestion(BaseModel):
    action: str = Field(..., description="Actionable suggestion for the admin.")
    related_entity_type: Optional[str] = Field(None, description="e.g. 'SERVICE_SCHEDULE', 'VEHICLE'")
    related_entity_id: Optional[uuid.UUID] = None


class InsightResponse(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    insight_type: str = Field(..., description="e.g. CROWDING, PERFORMANCE, FLEET")
    title: str
    service_id: uuid.UUID
    service_name: str
    route_id: uuid.UUID
    route_name: str
    time_window: str = Field(..., description="e.g. 08:00-10:00")
    day_pattern: str = Field(..., description="e.g. Weekdays")
    lookback_days: int
    severity: str = Field(..., description="INFO, WARNING, CRITICAL")
    evidence: InsightEvidence
    suggestion: InsightSuggestion
    generated_at: datetime


class InsightsSummaryResponse(BaseModel):
    insights: List[InsightResponse]
