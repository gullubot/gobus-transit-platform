import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.alert import ServiceAlert
from app.models.state import BusCurrentState
from app.models.vehicle import Vehicle
from app.models.service import DepotSchedule
from app.models.crowding import CrowdingReport
from app.models.enums import (
    AlertStatus, AlertSeverity, AlertScope, 
    VehicleStatus, Confidence, CrowdingState
)

logger = logging.getLogger(__name__)

class AlertEngine:
    def __init__(self, session: Session):
        self.session = session

    def _upsert_alert(
        self,
        organization_id: uuid.UUID,
        type_: str,
        fingerprint: str,
        title: str,
        message: str,
        suggested_solution: str,
        severity: AlertSeverity,
        scope: AlertScope,
        service_id: uuid.UUID | None = None,
        route_id: uuid.UUID | None = None,
        trip_id: uuid.UUID | None = None,
    ):
        """Upsert a deterministic alert. Does not create duplicate OPEN/ACKNOWLEDGED alerts."""
        stmt = select(ServiceAlert).where(
            ServiceAlert.incident_fingerprint == fingerprint,
            ServiceAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED])
        )
        existing_alert = self.session.scalar(stmt)

        if existing_alert:
            return existing_alert

        new_alert = ServiceAlert(
            organization_id=organization_id,
            type=type_,
            incident_fingerprint=fingerprint,
            title=title,
            message=message,
            suggested_solution=suggested_solution,
            severity=severity,
            scope=scope,
            service_id=service_id,
            route_id=route_id,
            trip_id=trip_id,
            status=AlertStatus.OPEN,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(new_alert)
        return new_alert

    def _auto_resolve_stale_alerts(
        self, 
        alert_type: str, 
        active_fingerprints: set[str]
    ):
        stmt = select(ServiceAlert).where(
            ServiceAlert.type == alert_type,
            ServiceAlert.status == AlertStatus.OPEN
        )
        open_alerts = self.session.scalars(stmt).all()

        for alert in open_alerts:
            if alert.incident_fingerprint not in active_fingerprints:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now(timezone.utc)
                logger.info(f"Auto-resolving alert {alert.incident_fingerprint}")

    def evaluate_vehicle_tracking_stale(self):
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(minutes=2)
        
        stmt = select(BusCurrentState).where(
            BusCurrentState.last_observed_at < threshold
        )
        stale_states = self.session.scalars(stmt).all()

        active_fingerprints = set()

        for state in stale_states:
            vehicle = self.session.scalar(select(Vehicle).where(Vehicle.id == state.vehicle_id))
            if not vehicle:
                continue

            fingerprint = f"VEHICLE_TRACKING_STALE_{vehicle.organization_id}_{vehicle.id}"
            active_fingerprints.add(fingerprint)

            last_obs_str = state.last_observed_at.isoformat() if state.last_observed_at else "Unknown"
            
            if not state.service_id and not state.route_id and not state.trip_id:
                continue

            self._upsert_alert(
                organization_id=vehicle.organization_id,
                type_="VEHICLE_TRACKING_STALE",
                fingerprint=fingerprint,
                title=f"Vehicle {vehicle.vehicle_number} Tracking Stale",
                message=f"Vehicle {vehicle.vehicle_number} last observed at {last_obs_str}.",
                suggested_solution="Contact the operator to verify hardware power state and network connectivity.",
                severity=AlertSeverity.WARNING,
                scope=AlertScope.SERVICE if state.service_id else (AlertScope.ROUTE if state.route_id else AlertScope.TRIP),
                service_id=state.service_id,
                route_id=state.route_id,
                trip_id=state.trip_id
            )

        self._auto_resolve_stale_alerts("VEHICLE_TRACKING_STALE", active_fingerprints)


    def evaluate_low_tracking_confidence(self):
        stmt = select(BusCurrentState).where(
            BusCurrentState.confidence == Confidence.LOW
        )
        low_conf_states = self.session.scalars(stmt).all()

        active_fingerprints = set()

        for state in low_conf_states:
            vehicle = self.session.scalar(select(Vehicle).where(Vehicle.id == state.vehicle_id))
            if not vehicle:
                continue

            fingerprint = f"LOW_TRACKING_CONFIDENCE_{vehicle.organization_id}_{vehicle.id}"
            active_fingerprints.add(fingerprint)

            if not state.service_id and not state.route_id and not state.trip_id:
                continue

            self._upsert_alert(
                organization_id=vehicle.organization_id,
                type_="LOW_TRACKING_CONFIDENCE",
                fingerprint=fingerprint,
                title=f"Low Tracking Confidence for Vehicle {vehicle.vehicle_number}",
                message=f"Vehicle {vehicle.vehicle_number} currently reporting LOW tracking confidence.",
                suggested_solution="Verify operator device and network conditions and review the vehicle's current tracking state.",
                severity=AlertSeverity.WARNING,
                scope=AlertScope.SERVICE if state.service_id else (AlertScope.ROUTE if state.route_id else AlertScope.TRIP),
                service_id=state.service_id,
                route_id=state.route_id,
                trip_id=state.trip_id
            )

        self._auto_resolve_stale_alerts("LOW_TRACKING_CONFIDENCE", active_fingerprints)


    def evaluate_unexpected_maintenance(self):
        now = datetime.now(timezone.utc)
        today = now.date()

        stmt = (
            select(Vehicle, DepotSchedule)
            .join(DepotSchedule, Vehicle.id == DepotSchedule.vehicle_id)
            .where(
                Vehicle.status == VehicleStatus.MAINTENANCE,
                DepotSchedule.operating_date == today
            )
        )
        rows = self.session.execute(stmt).all()

        for vehicle, schedule in rows:
            fingerprint = f"UNEXPECTED_MAINTENANCE_{vehicle.organization_id}_{vehicle.id}_{today}"
            
            self._upsert_alert(
                organization_id=vehicle.organization_id,
                type_="UNEXPECTED_MAINTENANCE",
                fingerprint=fingerprint,
                title=f"Unexpected Maintenance: Vehicle {vehicle.vehicle_number}",
                message=f"Vehicle {vehicle.vehicle_number} entered maintenance but is scheduled for service today.",
                suggested_solution="Assign an available active vehicle to the affected depot schedule.",
                severity=AlertSeverity.CRITICAL,
                scope=AlertScope.SERVICE,
                service_id=schedule.service_id
            )

    def evaluate_vehicle_offline_scheduled(self):
        now = datetime.now(timezone.utc)
        today = now.date()
        threshold = now - timedelta(minutes=15)

        stmt = select(DepotSchedule, Vehicle).join(Vehicle, DepotSchedule.vehicle_id == Vehicle.id).where(DepotSchedule.operating_date == today)
        scheduled_vehicles = self.session.execute(stmt).all()

        active_fingerprints = set()

        for schedule, vehicle in scheduled_vehicles:
            if vehicle.status == VehicleStatus.MAINTENANCE:
                continue

            current_state = self.session.scalar(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle.id))

            is_offline = False
            if not current_state:
                is_offline = True
            elif not current_state.last_observed_at or current_state.last_observed_at < threshold:
                is_offline = True
            
            if is_offline:
                fingerprint = f"VEHICLE_OFFLINE_SCHEDULED_{vehicle.organization_id}_{vehicle.id}_{today}"
                active_fingerprints.add(fingerprint)

                self._upsert_alert(
                    organization_id=vehicle.organization_id,
                    type_="VEHICLE_OFFLINE_SCHEDULED",
                    fingerprint=fingerprint,
                    title=f"Vehicle {vehicle.vehicle_number} Offline While Scheduled",
                    message=f"Vehicle {vehicle.vehicle_number} is scheduled to operate today but is not actively tracking.",
                    suggested_solution="Verify vehicle availability and consider assigning an available active vehicle to the affected schedule.",
                    severity=AlertSeverity.WARNING,
                    scope=AlertScope.SERVICE,
                    service_id=schedule.service_id
                )

        self._auto_resolve_stale_alerts("VEHICLE_OFFLINE_SCHEDULED", active_fingerprints)

    def evaluate_service_crowding_pattern(self):
        now = datetime.now(timezone.utc)
        threshold_date = now - timedelta(days=7)

        from app.models.trip import Trip
        
        stmt = (
            select(CrowdingReport, Trip.service_id)
            .join(Trip, CrowdingReport.trip_id == Trip.id)
            .where(CrowdingReport.observed_at >= threshold_date)
        )
        rows = self.session.execute(stmt).all()

        buckets = {}

        for report, service_id in rows:
            hour = report.observed_at.hour
            bucket_start = (hour // 2) * 2
            bucket_end = bucket_start + 2
            time_window = f"{bucket_start:02d}:00–{bucket_end:02d}:00"
            
            is_weekend = report.observed_at.weekday() >= 5
            day_pattern = "Weekends" if is_weekend else "Weekdays"

            key = (report.organization_id, service_id, time_window, day_pattern)
            
            if key not in buckets:
                buckets[key] = {"total": 0, "high": 0}
            
            buckets[key]["total"] += 1
            if report.crowding_state in (CrowdingState.HIGH, CrowdingState.FULL):
                buckets[key]["high"] += 1

        for key, stats in buckets.items():
            org_id, svc_id, time_window, day_pattern = key
            
            if stats["total"] < 4:
                continue

            percentage = (stats["high"] / stats["total"]) * 100
            if percentage > 60:
                fingerprint = f"SERVICE_CROWDING_PATTERN_{org_id}_{svc_id}_{time_window}_{day_pattern}"
                
                from app.models.service import Service
                service = self.session.scalar(select(Service).where(Service.id == svc_id))
                svc_name = service.service_code if service else str(svc_id)

                title = f"Recurring High Crowding on {svc_name}"
                message = (
                    f"Service {svc_name} recorded HIGH crowding in {stats['high']} of {stats['total']} "
                    f"relevant observations ({percentage:.1f}%) during the {time_window} {day_pattern.lower()} window "
                    f"over the analyzed 7-day period."
                )

                self._upsert_alert(
                    organization_id=org_id,
                    type_="SERVICE_CROWDING_PATTERN",
                    fingerprint=fingerprint,
                    title=title,
                    message=message,
                    suggested_solution="Consider increasing service frequency or assigning a higher-capacity vehicle during this peak window.",
                    severity=AlertSeverity.INFO,
                    scope=AlertScope.SERVICE,
                    service_id=svc_id
                )

    def run_all(self):
        try:
            logger.info("Starting AlertEngine evaluation cycle...")
            self.evaluate_vehicle_tracking_stale()
            self.evaluate_low_tracking_confidence()
            self.evaluate_unexpected_maintenance()
            self.evaluate_vehicle_offline_scheduled()
            self.evaluate_service_crowding_pattern()
            self.session.commit()
            logger.info("Completed AlertEngine evaluation cycle.")
        except Exception as e:
            self.session.rollback()
            logger.error(f"AlertEngine evaluation failed: {e}", exc_info=True)
