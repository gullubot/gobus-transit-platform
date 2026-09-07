import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import func, case, select, and_, or_
from sqlalchemy.orm import Session

from app.models.crowding import CrowdingReport
from app.models.enums import CrowdingState, TripStatus
from app.models.route import Route
from app.models.service import Service, ServiceSchedule
from app.models.trip import Trip
from app.models.vehicle import Vehicle
from app.schemas.admin_insights import (
    InsightEvidence,
    InsightResponse,
    InsightSuggestion,
)

# Logical capacity tiers derived from vehicle_type
CAPACITY_TIERS = {
    "MINI_BUS": "LOWER_CAPACITY",
    "BUS": "HIGHER_CAPACITY",
    "DOUBLE_DECKER": "HIGHER_CAPACITY",
}

class InsightsService:
    def __init__(self, session: Session, organization_id: uuid.UUID):
        self.session = session
        self.organization_id = organization_id

    def generate_all_insights(self, lookback_days: int = 30) -> List[InsightResponse]:
        insights = []
        insights.extend(self.analyze_recurring_crowding(lookback_days))
        insights.extend(self.analyze_service_performance(lookback_days))
        insights.extend(self.analyze_missed_trips(lookback_days))
        insights.extend(self.analyze_fleet_capacity(lookback_days))
        return insights

    def _get_active_schedules(self, service_id: uuid.UUID) -> List[ServiceSchedule]:
        return self.session.scalars(
            select(ServiceSchedule)
            .where(
                ServiceSchedule.service_id == service_id,
                ServiceSchedule.status == "ACTIVE"
            )
        ).all()

    def analyze_recurring_crowding(self, lookback_days: int = 30) -> List[InsightResponse]:
        """
        Detect recurring HIGH/FULL crowding patterns.
        Threshold: minimum 5 reports, > 60% HIGH/FULL ratio.
        """
        insights = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # 1. Base query matching relevant crowding reports.
        # Ensure we only include reports linked to a trip/service.
        # We group by service_id and the hour of observed_at.
        
        # PostgreSQL specific extraction
        hour_expr = func.extract('hour', CrowdingReport.observed_at)
        dow_expr = func.extract('isodow', CrowdingReport.observed_at) # 1=Mon, 7=Sun

        high_full_cond = CrowdingReport.crowding_state.in_([CrowdingState.HIGH, CrowdingState.FULL])
        
        stmt = (
            select(
                Trip.service_id,
                Service.service_code,
                Service.service_name,
                Service.route_id,
                Route.route_name,
                hour_expr.label("hour"),
                func.count(CrowdingReport.report_id).label("total_reports"),
                func.sum(case((high_full_cond, 1), else_=0)).label("high_full_count")
            )
            .select_from(CrowdingReport)
            .join(Trip, CrowdingReport.trip_id == Trip.id)
            .join(Service, Trip.service_id == Service.id)
            .join(Route, Service.route_id == Route.id)
            .where(
                CrowdingReport.organization_id == self.organization_id,
                CrowdingReport.observed_at >= cutoff_date
            )
            .group_by(
                Trip.service_id,
                Service.service_code,
                Service.service_name,
                Service.route_id,
                Route.route_name,
                hour_expr
            )
        )
        
        results = self.session.execute(stmt).all()
        
        for row in results:
            total = row.total_reports
            high_full = row.high_full_count or 0
            
            if total >= 5:
                ratio = high_full / total
                if ratio > 0.60:
                    start_hour = int(row.hour)
                    end_hour = (start_hour + 2) % 24 # 2-hour window representation for MVP
                    window_str = f"{start_hour:02d}:00–{end_hour:02d}:00"
                    
                    # Look up active schedule to suggest interval decrease
                    schedules = self._get_active_schedules(row.service_id)
                    current_interval = None
                    if schedules:
                        current_interval = schedules[0].typical_interval_minutes
                    
                    suggestion_text = "Consider increasing service frequency during this peak window."
                    if current_interval:
                        proposed_interval = max(5, current_interval - 5)
                        suggestion_text = f"Consider decreasing the typical interval from {current_interval} minutes to {proposed_interval} minutes during this window."
                    
                    evidence_stmt = f"{high_full} of {total} relevant reports were HIGH/FULL."
                    
                    # Let's fetch route explicitly to get route_name
                    # Actually, route_name can be fetched via service
                    service_ent = self.session.get(Service, row.service_id)
                    
                    insight = InsightResponse(
                        insight_type="CROWDING",
                        title="Recurring High Crowding",
                        service_id=row.service_id,
                        service_name=row.service_code,
                        route_id=row.route_id,
                        route_name=service_ent.route.route_name if service_ent.route else "Unknown",
                        time_window=window_str,
                        day_pattern="Weekdays", # Simplified for MVP unless proven otherwise by dow_expr
                        lookback_days=lookback_days,
                        severity="WARNING",
                        evidence=InsightEvidence(
                            statement=evidence_stmt,
                            total_observations=total,
                            matched_observations=high_full,
                            ratio=ratio,
                            window_start=f"{start_hour:02d}:00",
                            window_end=f"{end_hour:02d}:00"
                        ),
                        suggestion=InsightSuggestion(
                            action=suggestion_text,
                            related_entity_type="SERVICE_SCHEDULE",
                            related_entity_id=schedules[0].id if schedules else None
                        ),
                        generated_at=datetime.now(timezone.utc)
                    )
                    insights.append(insight)

        return insights

    def analyze_service_performance(self, lookback_days: int = 30) -> List[InsightResponse]:
        """
        Detect recurring departure delays.
        """
        insights = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        
        # We need trips with actual_start_at > planned_start_at + 10 mins
        stmt = (
            select(
                Trip.service_id,
                func.count(Trip.id).label("total_trips"),
                func.sum(
                    case(
                        (
                            Trip.actual_start_at > Trip.planned_start_at + timedelta(minutes=10),
                            1
                        ),
                        else_=0
                    )
                ).label("delayed_trips")
            )
            .select_from(Trip)
            .where(
                Trip.organization_id == self.organization_id,
                Trip.operating_date >= cutoff_date.date(),
                Trip.status == TripStatus.COMPLETED,
                Trip.actual_start_at.is_not(None)
            )
            .group_by(Trip.service_id)
        )
        
        results = self.session.execute(stmt).all()
        
        for row in results:
            total = row.total_trips
            delayed = row.delayed_trips or 0
            if total >= 5:
                ratio = delayed / total
                if ratio > 0.40:  # > 40% of trips are delayed by > 10m
                    service_ent = self.session.get(Service, row.service_id)
                    evidence_stmt = f"{delayed} of {total} completed trips experienced departure delays over 10 minutes."
                    
                    insight = InsightResponse(
                        insight_type="PERFORMANCE",
                        title="Recurring Departure Delays",
                        service_id=row.service_id,
                        service_name=service_ent.service_code,
                        route_id=service_ent.route_id,
                        route_name=service_ent.route.route_name if service_ent.route else "Unknown",
                        time_window="All Day",
                        day_pattern="All Days",
                        lookback_days=lookback_days,
                        severity="WARNING",
                        evidence=InsightEvidence(
                            statement=evidence_stmt,
                            total_observations=total,
                            matched_observations=delayed,
                            ratio=ratio
                        ),
                        suggestion=InsightSuggestion(
                            action="Review depot dispatch schedule or adjust planned times.",
                            related_entity_type="SERVICE",
                            related_entity_id=service_ent.id
                        ),
                        generated_at=datetime.now(timezone.utc)
                    )
                    insights.append(insight)
        
        return insights

    def analyze_missed_trips(self, lookback_days: int = 30) -> List[InsightResponse]:
        """
        Detect repeated CANCELLED or ABANDONED trips.
        """
        insights = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        
        stmt = (
            select(
                Trip.service_id,
                func.count(Trip.id).label("total_trips"),
                func.sum(
                    case(
                        (Trip.status.in_([TripStatus.CANCELLED, TripStatus.ABANDONED]), 1),
                        else_=0
                    )
                ).label("missed_trips")
            )
            .select_from(Trip)
            .where(
                Trip.organization_id == self.organization_id,
                Trip.operating_date >= cutoff_date.date(),
                Trip.status.in_([TripStatus.COMPLETED, TripStatus.CANCELLED, TripStatus.ABANDONED])
            )
            .group_by(Trip.service_id)
        )
        
        results = self.session.execute(stmt).all()
        for row in results:
            total = row.total_trips
            missed = row.missed_trips or 0
            if total >= 10:
                ratio = missed / total
                if ratio > 0.20: # > 20% missed
                    service_ent = self.session.get(Service, row.service_id)
                    evidence_stmt = f"{missed} of {total} trips were cancelled or abandoned."
                    
                    insight = InsightResponse(
                        insight_type="PERFORMANCE",
                        title="Recurring Missed Trips",
                        service_id=row.service_id,
                        service_name=service_ent.service_code,
                        route_id=service_ent.route_id,
                        route_name=service_ent.route.route_name if service_ent.route else "Unknown",
                        time_window="All Day",
                        day_pattern="All Days",
                        lookback_days=lookback_days,
                        severity="CRITICAL",
                        evidence=InsightEvidence(
                            statement=evidence_stmt,
                            total_observations=total,
                            matched_observations=missed,
                            ratio=ratio
                        ),
                        suggestion=InsightSuggestion(
                            action="Review fleet availability and depot scheduling for the affected service.",
                            related_entity_type="SERVICE",
                            related_entity_id=service_ent.id
                        ),
                        generated_at=datetime.now(timezone.utc)
                    )
                    insights.append(insight)
        
        return insights

    def analyze_fleet_capacity(self, lookback_days: int = 30) -> List[InsightResponse]:
        """
        Detect vehicle capacity mismatch (high crowding on lower capacity vehicle).
        """
        insights = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        
        # Find cases where HIGH/FULL is frequent, and mostly served by lower capacity vehicles
        # Actually, let's group by service and see if LOW capacity vehicles receive HIGH/FULL
        
        stmt = (
            select(
                Trip.service_id,
                Vehicle.vehicle_type,
                func.count(CrowdingReport.report_id).label("total_reports"),
                func.sum(case((CrowdingReport.crowding_state.in_([CrowdingState.HIGH, CrowdingState.FULL]), 1), else_=0)).label("high_full_count")
            )
            .select_from(CrowdingReport)
            .join(Trip, CrowdingReport.trip_id == Trip.id)
            .join(Vehicle, CrowdingReport.vehicle_id == Vehicle.id)
            .where(
                CrowdingReport.organization_id == self.organization_id,
                CrowdingReport.observed_at >= cutoff_date
            )
            .group_by(Trip.service_id, Vehicle.vehicle_type)
        )
        
        results = self.session.execute(stmt).all()
        for row in results:
            total = row.total_reports
            high_full = row.high_full_count or 0
            tier = CAPACITY_TIERS.get(row.vehicle_type, "UNKNOWN")
            
            if total >= 5 and tier == "LOWER_CAPACITY":
                ratio = high_full / total
                if ratio > 0.60:
                    service_ent = self.session.get(Service, row.service_id)
                    evidence_stmt = f"{high_full} of {total} reports on lower-capacity vehicles ({row.vehicle_type}) were HIGH/FULL."
                    
                    insight = InsightResponse(
                        insight_type="FLEET",
                        title="Under-Capacity Vehicle Assignment",
                        service_id=row.service_id,
                        service_name=service_ent.service_code,
                        route_id=service_ent.route_id,
                        route_name=service_ent.route.route_name if service_ent.route else "Unknown",
                        time_window="All Day",
                        day_pattern="All Days",
                        lookback_days=lookback_days,
                        severity="WARNING",
                        evidence=InsightEvidence(
                            statement=evidence_stmt,
                            total_observations=total,
                            matched_observations=high_full,
                            ratio=ratio
                        ),
                        suggestion=InsightSuggestion(
                            action="Consider assigning a higher-capacity vehicle to this service.",
                            related_entity_type="SERVICE",
                            related_entity_id=service_ent.id
                        ),
                        generated_at=datetime.now(timezone.utc)
                    )
                    insights.append(insight)
                    
        return insights
