import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, func, and_, or_, case
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.database import engine
from app.models.alert import ServiceAlert
from app.models.enums import AlertStatus, AlertSeverity
from app.models.user import User
from app.schemas.admin_alerts import (
    ServiceAlertResponse,
    AlertAcknowledgeRequest,
    AlertResolveRequest,
    AlertListResponse,
    AlertMetrics,
)
from app.services.alert_resolution import (
    calculate_urgency_score,
    extract_entity_context,
    resolve_suggested_resolution,
)

router = APIRouter()


def get_db():
    with Session(engine) as session:
        yield session


def _enrich_alert_response(
    alert: ServiceAlert,
    session: Session,
    urgency_rank: Optional[str] = None,
) -> ServiceAlertResponse:
    entity_ctx = extract_entity_context(alert, session)
    resolution = resolve_suggested_resolution(alert, entity_ctx)
    score = calculate_urgency_score(alert.status, alert.severity)

    # Base dictionary from ORM model
    resp = ServiceAlertResponse.model_validate(alert)
    resp.urgency_score = score
    resp.urgency_rank = urgency_rank
    resp.entity_context = entity_ctx
    resp.suggested_resolution = resolution
    return resp


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    status_: Optional[AlertStatus] = Query(None, alias="status"),
    severity: Optional[AlertSeverity] = Query(None),
    type: Optional[str] = Query(None),
    service_id: Optional[uuid.UUID] = Query(None),
    route_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    List operational alerts strictly scoped to the admin's organization.
    Applies deterministic urgency ranking prior to pagination:
      1. Unresolved incidents outrank resolved incidents.
      2. Higher severity outranks lower severity (CRITICAL > WARNING > INFO).
      3. OPEN outranks ACKNOWLEDGED within the same severity.
      4. For unresolved alerts: older incidents outrank newer incidents (FIFO triage).
      5. For resolved alerts: newer resolutions appear first.
    """
    # 1. Organization-wide summary metrics
    metrics_stmt = select(
        func.count().filter(ServiceAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED])).label("active"),
        func.count().filter(ServiceAlert.status == AlertStatus.OPEN).label("open"),
        func.count().filter(ServiceAlert.status == AlertStatus.ACKNOWLEDGED).label("acknowledged"),
        func.count().filter(ServiceAlert.status == AlertStatus.RESOLVED).label("resolved"),
        func.count().filter(and_(ServiceAlert.status != AlertStatus.RESOLVED, ServiceAlert.severity == AlertSeverity.CRITICAL)).label("critical"),
        func.count().filter(and_(ServiceAlert.status != AlertStatus.RESOLVED, ServiceAlert.severity == AlertSeverity.WARNING)).label("warning"),
    ).where(ServiceAlert.organization_id == current_admin.organization_id)
    
    m_row = db.execute(metrics_stmt).one()
    metrics = AlertMetrics(
        active=m_row.active or 0,
        open=m_row.open or 0,
        acknowledged=m_row.acknowledged or 0,
        resolved=m_row.resolved or 0,
        critical=m_row.critical or 0,
        warning=m_row.warning or 0,
    )

    # 2. Base query with organization isolation
    stmt = select(ServiceAlert).where(
        ServiceAlert.organization_id == current_admin.organization_id
    )

    # 3. Filters
    if status_:
        stmt = stmt.where(ServiceAlert.status == status_)
    if severity:
        stmt = stmt.where(ServiceAlert.severity == severity)
    if type:
        stmt = stmt.where(ServiceAlert.type == type)
    if service_id:
        stmt = stmt.where(ServiceAlert.service_id == service_id)
    if route_id:
        stmt = stmt.where(ServiceAlert.route_id == route_id)
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ServiceAlert.title.ilike(search_term),
                ServiceAlert.message.ilike(search_term),
                ServiceAlert.type.ilike(search_term),
                ServiceAlert.incident_fingerprint.ilike(search_term),
            )
        )

    # 4. Total count matching filters
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # 5. Deterministic urgency ordering expression
    urgency_tier = case(
        (and_(ServiceAlert.status == AlertStatus.OPEN, ServiceAlert.severity == AlertSeverity.CRITICAL), 1),
        (and_(ServiceAlert.status == AlertStatus.ACKNOWLEDGED, ServiceAlert.severity == AlertSeverity.CRITICAL), 2),
        (and_(ServiceAlert.status == AlertStatus.OPEN, ServiceAlert.severity == AlertSeverity.WARNING), 3),
        (and_(ServiceAlert.status == AlertStatus.ACKNOWLEDGED, ServiceAlert.severity == AlertSeverity.WARNING), 4),
        (and_(ServiceAlert.status == AlertStatus.OPEN, ServiceAlert.severity == AlertSeverity.INFO), 5),
        (and_(ServiceAlert.status == AlertStatus.ACKNOWLEDGED, ServiceAlert.severity == AlertSeverity.INFO), 6),
        else_=7,
    )

    unresolved_time = case(
        (ServiceAlert.status != AlertStatus.RESOLVED, ServiceAlert.created_at),
        else_=None,
    )
    resolved_time = case(
        (ServiceAlert.status == AlertStatus.RESOLVED, ServiceAlert.created_at),
        else_=None,
    )

    stmt = stmt.order_by(
        urgency_tier.asc(),
        unresolved_time.asc().nulls_last(),
        resolved_time.desc().nulls_last(),
        ServiceAlert.id.asc(),
    ).limit(limit).offset(offset)

    alerts = db.scalars(stmt).all()

    # 6. Enrich with deterministic resolution and entity context
    enriched_data = [
        _enrich_alert_response(
            alert=alert,
            session=db,
            urgency_rank=f"#{offset + idx + 1}",
        )
        for idx, alert in enumerate(alerts)
    ]

    return AlertListResponse(data=enriched_data, total=total, metrics=metrics)


@router.get("/alerts/{alert_id}", response_model=ServiceAlertResponse)
def get_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Get a specific alert, strictly scoped to the admin's organization."""
    stmt = select(ServiceAlert).where(
        ServiceAlert.id == alert_id,
        ServiceAlert.organization_id == current_admin.organization_id,
    )
    alert = db.scalar(stmt)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return _enrich_alert_response(alert=alert, session=db)


@router.put("/alerts/{alert_id}/acknowledge", response_model=ServiceAlertResponse)
def acknowledge_alert(
    alert_id: uuid.UUID,
    request: AlertAcknowledgeRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Acknowledge an open alert (explicit Admin action only)."""
    stmt = select(ServiceAlert).where(
        ServiceAlert.id == alert_id,
        ServiceAlert.organization_id == current_admin.organization_id,
    )
    alert = db.scalar(stmt)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status != AlertStatus.OPEN:
        raise HTTPException(
            status_code=400, detail=f"Cannot acknowledge alert in {alert.status.value} status"
        )

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = current_admin.id
    alert.acknowledged_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return _enrich_alert_response(alert=alert, session=db)


@router.put("/alerts/{alert_id}/resolve", response_model=ServiceAlertResponse)
def resolve_alert(
    alert_id: uuid.UUID,
    request: AlertResolveRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Resolve an open or acknowledged alert (explicit Admin action only)."""
    stmt = select(ServiceAlert).where(
        ServiceAlert.id == alert_id,
        ServiceAlert.organization_id == current_admin.organization_id,
    )
    alert = db.scalar(stmt)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(
            status_code=400, detail="Alert is already resolved."
        )

    alert.status = AlertStatus.RESOLVED
    alert.resolved_by = current_admin.id
    alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return _enrich_alert_response(alert=alert, session=db)
