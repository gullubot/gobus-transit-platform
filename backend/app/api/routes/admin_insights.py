from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.models.user import User
from app.schemas.admin_insights import InsightsSummaryResponse
from app.services.insights_service import InsightsService

router = APIRouter()


@router.get("/crowding", response_model=InsightsSummaryResponse)
def get_crowding_insights(
    lookback_days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    Retrieve recurring crowding insights and suggestions for the admin's organization.
    """
    service = InsightsService(session=db, organization_id=current_admin.organization_id)
    insights = service.analyze_recurring_crowding(lookback_days=lookback_days)
    return InsightsSummaryResponse(insights=insights)


@router.get("/performance", response_model=InsightsSummaryResponse)
def get_performance_insights(
    lookback_days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    Retrieve service performance (delays, missed trips) insights.
    """
    service = InsightsService(session=db, organization_id=current_admin.organization_id)
    insights = service.analyze_service_performance(lookback_days=lookback_days)
    insights.extend(service.analyze_missed_trips(lookback_days=lookback_days))
    return InsightsSummaryResponse(insights=insights)


@router.get("/fleet", response_model=InsightsSummaryResponse)
def get_fleet_insights(
    lookback_days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    Retrieve fleet capacity insights (e.g. under-capacity vehicle assignments).
    """
    service = InsightsService(session=db, organization_id=current_admin.organization_id)
    insights = service.analyze_fleet_capacity(lookback_days=lookback_days)
    return InsightsSummaryResponse(insights=insights)


@router.get("/summary", response_model=InsightsSummaryResponse)
def get_all_insights_summary(
    lookback_days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    Retrieve all insights combined for the dashboard summary.
    """
    service = InsightsService(session=db, organization_id=current_admin.organization_id)
    insights = service.generate_all_insights(lookback_days=lookback_days)
    return InsightsSummaryResponse(insights=insights)
