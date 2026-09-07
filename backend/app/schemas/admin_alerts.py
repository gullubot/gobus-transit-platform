import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import AlertStatus, AlertSeverity, AlertScope


class AlertEntityContext(BaseModel):
    vehicle_id: Optional[uuid.UUID] = None
    vehicle_number: Optional[str] = None
    service_id: Optional[uuid.UUID] = None
    service_code: Optional[str] = None
    service_name: Optional[str] = None
    route_id: Optional[uuid.UUID] = None
    route_code: Optional[str] = None
    route_name: Optional[str] = None
    stop_id: Optional[uuid.UUID] = None
    stop_code: Optional[str] = None
    stop_name: Optional[str] = None


class SuggestedAction(BaseModel):
    label: str
    destination: str
    action_type: str = "NAVIGATE"
    reason: str


class SuggestedResolution(BaseModel):
    recommended_action: str
    reason: str
    observed: str
    actions: List[SuggestedAction] = Field(default_factory=list)


class ServiceAlertResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    service_id: Optional[uuid.UUID] = None
    route_id: Optional[uuid.UUID] = None
    stop_id: Optional[uuid.UUID] = None
    trip_id: Optional[uuid.UUID] = None
    scope: AlertScope
    status: AlertStatus
    type: str
    incident_fingerprint: str
    title: str
    message: str
    suggested_solution: Optional[str] = None
    severity: AlertSeverity
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    acknowledged_by: Optional[uuid.UUID] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Deterministic triage & enrichment fields
    urgency_score: int = 50
    urgency_rank: Optional[str] = None
    entity_context: Optional[AlertEntityContext] = None
    suggested_resolution: Optional[SuggestedResolution] = None

    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledgeRequest(BaseModel):
    pass


class AlertResolveRequest(BaseModel):
    pass


class AlertMetrics(BaseModel):
    active: int = 0
    critical: int = 0
    warning: int = 0
    resolved: int = 0
    open: int = 0
    acknowledged: int = 0


class AlertListResponse(BaseModel):
    data: List[ServiceAlertResponse]
    total: int
    metrics: AlertMetrics
