import math
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.crowding import CrowdingReport
from app.models.enums import CrowdingSource, CrowdingState, UserRole
from app.repositories.crowding_repository import get_active_trip_for_vehicle, save_crowding_report
from app.schemas.crowding import CrowdingReportRequest, CrowdingReportResponse


class CrowdingEngine:
    """
    Handles the business logic for processing crowding reports.
    """

    @staticmethod
    def process_report(
        session: Session,
        request: CrowdingReportRequest,
        organization_id: uuid.UUID,
        user_role: UserRole = None,
    ) -> CrowdingReportResponse:
        """
        Processes a crowding report, deriving the source type and resolving trips.
        """
        # Derive source type from authentication context
        # In a real setup, we'd check if the user is a passenger vs operator.
        # Since PASSENGER is not in UserRole (MVP), if user_role is empty or not an operator role,
        # we consider it a PASSENGER. If it's DRIVER/CONDUCTOR, it's OPERATOR.
        # Actually, let's just make it PASSENGER if user_role is None, otherwise OPERATOR.
        if user_role in [UserRole.DRIVER, UserRole.CONDUCTOR]:
            source_type = CrowdingSource.OPERATOR
        else:
            source_type = CrowdingSource.PASSENGER

        # Crowding is VEHICLE-LEVEL.
        # Attempt to bind to the currently active trip at observation time.
        active_trip_id = get_active_trip_for_vehicle(
            session, organization_id, request.vehicle_id, request.observed_at
        )

        received_at = datetime.now(timezone.utc)

        report = CrowdingReport(
            report_id=request.report_id,
            organization_id=organization_id,
            vehicle_id=request.vehicle_id,
            trip_id=active_trip_id,
            crowding_state=request.crowding_state,
            confidence=request.confidence,
            observed_at=request.observed_at,
            received_at=received_at,
            source_type=source_type,
        )

        # Save idempotently
        save_crowding_report(session, report)
        session.commit()

        return CrowdingReportResponse.model_validate(report)

    @staticmethod
    def aggregate_vehicle_crowding(
        session: Session, vehicle_id: uuid.UUID, reference_time: datetime = None
    ):
        """
        Aggregates crowding for a vehicle, implementing staleness, decay, precedence,
        and conflict penalties.
        Returns a dictionary matching PassengerCrowdingResponse.
        """
        from sqlalchemy import desc, select

        from app.schemas.crowding import PassengerCrowdingResponse

        server_now = reference_time if reference_time else datetime.now(timezone.utc)
        one_hour_ago = server_now - __import__("datetime").timedelta(minutes=60)

        # Get all reports in the last 60 minutes
        stmt = (
            select(CrowdingReport)
            .where(
                CrowdingReport.vehicle_id == vehicle_id, CrowdingReport.observed_at >= one_hour_ago
            )
            .order_by(desc(CrowdingReport.observed_at))
        )

        reports = session.execute(stmt).scalars().all()

        if not reports:
            return PassengerCrowdingResponse(
                state=CrowdingState.UNKNOWN,
                confidence=0.0,
                observed_at=server_now,
                evidence_type="NONE",
                stale=True,
            )

        # 11. OPERATOR AUTHORITY WINDOW (10 mins)
        ten_mins_ago = server_now - __import__("datetime").timedelta(minutes=10)
        operator_reports = [
            r
            for r in reports
            if r.source_type == CrowdingSource.OPERATOR and r.observed_at >= ten_mins_ago
        ]

        if operator_reports:
            # Most recent operator report
            active_op = operator_reports[0]
            delta_minutes = (server_now - active_op.observed_at).total_seconds() / 60.0
            decay = math.exp(-(math.log(2) / 10) * delta_minutes)
            final_conf = 0.90 * decay
            return PassengerCrowdingResponse(
                state=active_op.crowding_state,
                confidence=min(max(final_conf, 0.0), 1.0),
                observed_at=active_op.observed_at,
                evidence_type="LIVE_REPORTED",
                stale=False,
            )

        # 12. PASSENGER AGGREGATION
        # Filter to LIVE eligible (0-20 mins) and final_confidence >= 0.20
        twenty_mins_ago = server_now - __import__("datetime").timedelta(minutes=20)
        live_passenger_reports = []

        for r in reports:
            if r.source_type == CrowdingSource.PASSENGER and r.observed_at >= twenty_mins_ago:
                # Also exclude UNRESOLVED_VEHICLE_REPORT (where trip_id is NULL)
                # from live aggregation
                if r.trip_id is None:
                    continue

                delta_minutes = (server_now - r.observed_at).total_seconds() / 60.0
                decay = math.exp(-(math.log(2) / 10) * delta_minutes)
                final_conf = 0.60 * decay
                if final_conf >= 0.20:
                    live_passenger_reports.append((r, final_conf))

        # 13. HISTORICAL FALLBACK
        # If no live reports exist, check for valid historical reports (20-60 mins)
        if not live_passenger_reports:
            sixty_mins_ago = server_now - __import__("datetime").timedelta(minutes=60)
            historical_reports = [
                r
                for r in reports
                if r.observed_at < twenty_mins_ago and r.observed_at >= sixty_mins_ago
            ]
            if historical_reports:
                # Take the most recent historical report
                hist_r = historical_reports[0]
                delta_minutes = (server_now - hist_r.observed_at).total_seconds() / 60.0
                decay = math.exp(-(math.log(2) / 10) * delta_minutes)
                base = 0.90 if hist_r.source_type == CrowdingSource.OPERATOR else 0.60
                final_conf = base * decay
                return PassengerCrowdingResponse(
                    state=hist_r.crowding_state,
                    confidence=min(max(final_conf, 0.0), 1.0),
                    observed_at=hist_r.observed_at,
                    evidence_type="HISTORICAL_REPORTED",
                    stale=True,
                )
            else:
                return PassengerCrowdingResponse(
                    state=CrowdingState.UNKNOWN,
                    confidence=0.0,
                    observed_at=server_now,
                    evidence_type="UNKNOWN",
                    stale=True,
                )

        state_mapping = {
            CrowdingState.LOW: 1,
            CrowdingState.MODERATE: 2,
            CrowdingState.HIGH: 3,
            CrowdingState.FULL: 4,
        }
        reverse_mapping = {
            1: CrowdingState.LOW,
            2: CrowdingState.MODERATE,
            3: CrowdingState.HIGH,
            4: CrowdingState.FULL,
        }

        weighted_sum = 0.0
        weight_total = 0.0
        values = []

        for r, weight in live_passenger_reports:
            val = state_mapping.get(r.crowding_state, 0)
            if val == 0:
                continue
            weighted_sum += val * weight
            weight_total += weight
            values.append(val)

        if weight_total == 0:
            return PassengerCrowdingResponse(
                state=CrowdingState.UNKNOWN,
                confidence=0.0,
                observed_at=server_now,
                evidence_type="UNKNOWN",
                stale=True,
            )

        weighted_state_mean = weighted_sum / weight_total
        # Midpoint rounding: floor(weighted_state_mean + 0.5)
        rounded_val = math.floor(weighted_state_mean + 0.5)
        rounded_val = min(max(rounded_val, 1), 4)

        # weighted_confidence_base = sum(weight_i * weight_i) / sum(weight_i)
        sum_weight_squared = sum(w * w for _, w in live_passenger_reports)
        weighted_confidence_base = sum_weight_squared / weight_total

        # Conflict penalty using population stddev
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        stdev = math.sqrt(variance)

        conflict_penalty = 0.15 * stdev
        agg_conf = weighted_confidence_base - conflict_penalty
        agg_conf = min(max(agg_conf, 0.0), 1.0)

        # Use the most recent observed_at from the aggregated set
        most_recent_observed = max(r.observed_at for r, _ in live_passenger_reports)

        return PassengerCrowdingResponse(
            state=reverse_mapping[rounded_val],
            confidence=agg_conf,
            observed_at=most_recent_observed,
            evidence_type="LIVE_REPORTED",
            stale=False,
        )
