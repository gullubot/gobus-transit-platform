import re
import uuid
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import ServiceAlert
from app.models.vehicle import Vehicle
from app.models.service import Service
from app.models.route import Route, Stop
from app.models.trip import Trip
from app.models.enums import AlertStatus, AlertSeverity
from app.schemas.admin_alerts import (
    AlertEntityContext,
    SuggestedResolution,
    SuggestedAction,
)

UUID_PATTERN = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def calculate_urgency_score(status: AlertStatus, severity: AlertSeverity) -> int:
    """Deterministic urgency score (0-100)."""
    if status == AlertStatus.RESOLVED:
        return 10
    
    tier_map = {
        (AlertStatus.OPEN, AlertSeverity.CRITICAL): 95,
        (AlertStatus.ACKNOWLEDGED, AlertSeverity.CRITICAL): 85,
        (AlertStatus.OPEN, AlertSeverity.WARNING): 75,
        (AlertStatus.ACKNOWLEDGED, AlertSeverity.WARNING): 65,
        (AlertStatus.OPEN, AlertSeverity.INFO): 55,
        (AlertStatus.ACKNOWLEDGED, AlertSeverity.INFO): 45,
    }
    return tier_map.get((status, severity), 30)


def extract_entity_context(alert: ServiceAlert, session: Session) -> AlertEntityContext:
    """
    Deterministically resolves affected entity context from alert fields,
    fingerprint metadata, and database relations.
    """
    ctx = AlertEntityContext(
        service_id=alert.service_id,
        route_id=alert.route_id,
        stop_id=alert.stop_id,
    )

    # 1. Resolve vehicle_id
    vehicle_id: Optional[uuid.UUID] = None
    if alert.trip_id:
        trip = session.scalar(select(Trip).where(Trip.id == alert.trip_id))
        if trip and trip.vehicle_id:
            vehicle_id = trip.vehicle_id
            if not ctx.service_id:
                ctx.service_id = trip.service_id
            if not ctx.route_id:
                ctx.route_id = trip.route_id

    if not vehicle_id and alert.incident_fingerprint:
        # Check for UUIDs in fingerprint
        matches = UUID_PATTERN.findall(alert.incident_fingerprint)
        # Fingerprint pattern: TYPE_orgId_vehicleId_date...
        for candidate_str in matches:
            try:
                candidate_uuid = uuid.UUID(candidate_str)
                if candidate_uuid == alert.organization_id:
                    continue
                # Test if candidate is a vehicle
                veh = session.scalar(
                    select(Vehicle).where(
                        Vehicle.id == candidate_uuid,
                        Vehicle.organization_id == alert.organization_id,
                    )
                )
                if veh:
                    vehicle_id = candidate_uuid
                    break
            except (ValueError, TypeError):
                continue

    if vehicle_id:
        ctx.vehicle_id = vehicle_id
        vehicle = session.scalar(
            select(Vehicle).where(
                Vehicle.id == vehicle_id,
                Vehicle.organization_id == alert.organization_id,
            )
        )
        if vehicle:
            ctx.vehicle_number = vehicle.vehicle_number

    # 2. Resolve Service details
    if ctx.service_id:
        service = session.scalar(
            select(Service).where(
                Service.id == ctx.service_id,
                Service.organization_id == alert.organization_id,
            )
        )
        if service:
            ctx.service_code = service.service_code
            ctx.service_name = service.service_name
            if not ctx.route_id:
                ctx.route_id = service.route_id

    # 3. Resolve Route details
    if ctx.route_id:
        route = session.scalar(
            select(Route).where(
                Route.id == ctx.route_id,
                Route.organization_id == alert.organization_id,
            )
        )
        if route:
            ctx.route_code = route.route_code
            ctx.route_name = route.route_name

    # 4. Resolve Stop details
    if ctx.stop_id:
        stop = session.scalar(
            select(Stop).where(
                Stop.id == ctx.stop_id,
                Stop.organization_id == alert.organization_id,
            )
        )
        if stop:
            ctx.stop_code = stop.stop_code
            ctx.stop_name = stop.name

    return ctx


def resolve_suggested_resolution(
    alert: ServiceAlert,
    ctx: AlertEntityContext,
) -> SuggestedResolution:
    """
    Authoritative deterministic resolution engine.
    Matches supported domain alert types with factual observations and actionable navigation links.
    """
    v_label = ctx.vehicle_number or (f"Vehicle {str(ctx.vehicle_id)[:8]}" if ctx.vehicle_id else "Assigned vehicle")
    s_label = ctx.service_code or (f"Service {str(ctx.service_id)[:8]}" if ctx.service_id else "Service")

    alert_type = alert.type.upper() if alert.type else ""

    if alert_type == "VEHICLE_OFFLINE_SCHEDULED":
        observed = (
            f"{v_label} is scheduled to operate today on {s_label} but is not actively tracking."
            if ctx.service_id
            else f"{v_label} is scheduled to operate today but is not actively tracking."
        )
        recommended = "Verify vehicle availability in Fleet and review the affected schedule."
        reason = "The vehicle has an active schedule assignment for today but has stopped emitting tracking telemetry."
        actions = []
        if ctx.service_id:
            actions.append(
                SuggestedAction(
                    label="Open Fleet Schedule",
                    destination=f"/fleet-schedules?serviceId={ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Review departure times and assign an active replacement vehicle.",
                )
            )
            actions.append(
                SuggestedAction(
                    label="Open Fleet",
                    destination=f"/vehicles?serviceId={ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Inspect vehicle status and verify operator assignment.",
                )
            )
        elif ctx.vehicle_id:
            actions.append(
                SuggestedAction(
                    label="Open Fleet",
                    destination="/vehicles",
                    action_type="NAVIGATE",
                    reason="Inspect vehicle status and telemetry.",
                )
            )

        return SuggestedResolution(
            recommended_action=recommended,
            reason=reason,
            observed=observed,
            actions=actions,
        )

    elif alert_type == "UNEXPECTED_MAINTENANCE":
        observed = f"{v_label} entered MAINTENANCE status while scheduled for service today."
        recommended = "Assign an available active vehicle to the affected depot schedule."
        reason = "The vehicle was pulled into maintenance, creating an unserved schedule gap on the assigned service."
        actions = []
        if ctx.service_id:
            actions.append(
                SuggestedAction(
                    label="Open Fleet Schedule",
                    destination=f"/fleet-schedules?serviceId={ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Reassign today's scheduled departures to an active standby vehicle.",
                )
            )
            actions.append(
                SuggestedAction(
                    label="Open Fleet",
                    destination=f"/vehicles?serviceId={ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Check depot fleet availability for alternative vehicles.",
                )
            )
        else:
            actions.append(
                SuggestedAction(
                    label="Open Fleet",
                    destination="/vehicles",
                    action_type="NAVIGATE",
                    reason="Check fleet availability for maintenance replacement.",
                )
            )

        return SuggestedResolution(
            recommended_action=recommended,
            reason=reason,
            observed=observed,
            actions=actions,
        )

    elif alert_type == "VEHICLE_TRACKING_STALE":
        observed = f"{v_label} telemetry has not updated within expected intervals."
        recommended = "Contact vehicle operator and verify tracking device power and network connectivity."
        reason = "Last observed location telemetry has aged beyond the real-time staleness threshold."
        actions = []
        if ctx.service_id:
            actions.append(
                SuggestedAction(
                    label="Open Fleet",
                    destination=f"/vehicles?serviceId={ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Verify vehicle and driver telemetry status.",
                )
            )
            actions.append(
                SuggestedAction(
                    label="Open Service",
                    destination=f"/services/{ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Check overall service route and active trip progress.",
                )
            )
        else:
            actions.append(
                SuggestedAction(
                    label="Open Fleet",
                    destination="/vehicles",
                    action_type="NAVIGATE",
                    reason="Verify vehicle telemetry status.",
                )
            )

        return SuggestedResolution(
            recommended_action=recommended,
            reason=reason,
            observed=observed,
            actions=actions,
        )

    elif alert_type == "LOW_TRACKING_CONFIDENCE":
        observed = f"{v_label} is reporting degraded tracking confidence."
        recommended = "Verify operator device GPS accuracy and check for route alignment anomalies."
        reason = "GPS signal jitter or off-route positioning is degrading tracking precision."
        actions = []
        if ctx.service_id:
            actions.append(
                SuggestedAction(
                    label="Open Fleet",
                    destination=f"/vehicles?serviceId={ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Inspect vehicle telemetry health and recent tracking events.",
                )
            )
        if ctx.route_id:
            actions.append(
                SuggestedAction(
                    label="Open Route",
                    destination=f"/routes/{ctx.route_id}",
                    action_type="NAVIGATE",
                    reason="Review designated route topology and stop sequence.",
                )
            )

        return SuggestedResolution(
            recommended_action=recommended,
            reason=reason,
            observed=observed,
            actions=actions,
        )

    elif alert_type == "SERVICE_CROWDING_PATTERN":
        observed = alert.message or f"Recurring high crowding detected on {s_label}."
        recommended = "Review service capacity and adjust dispatch frequencies or vehicle sizes for this window."
        reason = "Passenger crowding observations consistently exceeded capacity thresholds during peak operating windows."
        actions = []
        if ctx.service_id:
            actions.append(
                SuggestedAction(
                    label="Open Service",
                    destination=f"/services/{ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Review service configuration, frequency, and operating parameters.",
                )
            )
            actions.append(
                SuggestedAction(
                    label="Open Fleet Schedule",
                    destination=f"/fleet-schedules?serviceId={ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Adjust scheduled departure frequencies and vehicle capacity assignments.",
                )
            )

        return SuggestedResolution(
            recommended_action=recommended,
            reason=reason,
            observed=observed,
            actions=actions,
        )

    else:
        # Unsupported or custom alert type fallback
        observed = alert.message or "Incident reported."
        recommended = "No predefined resolution guidance is available for this alert type."
        reason = "This alert type does not match a predefined operational triage pattern. Review incident details and take manual action as needed."
        actions = []
        if ctx.service_id:
            actions.append(
                SuggestedAction(
                    label="Open Service",
                    destination=f"/services/{ctx.service_id}",
                    action_type="NAVIGATE",
                    reason="Investigate service details.",
                )
            )
        elif ctx.route_id:
            actions.append(
                SuggestedAction(
                    label="Open Route",
                    destination=f"/routes/{ctx.route_id}",
                    action_type="NAVIGATE",
                    reason="Investigate route details.",
                )
            )
        elif ctx.stop_id:
            actions.append(
                SuggestedAction(
                    label="Open Stop",
                    destination=f"/stops?stopId={ctx.stop_id}",
                    action_type="NAVIGATE",
                    reason="Investigate stop details.",
                )
            )

        return SuggestedResolution(
            recommended_action=recommended,
            reason=reason,
            observed=observed,
            actions=actions,
        )
