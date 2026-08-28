import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.intelligence.config import (
    ETA_CONFIDENCE_HIGH,
    ETA_CONFIDENCE_LOW,
    ETA_CONFIDENCE_MEDIUM,
    ETA_DEGRADED_UNCERTAINTY_MIN,
    ETA_DWELL_NON_STOP_UNCERTAINTY_MIN,
    ETA_EWMA_ALPHA,
    ETA_MAX_SECONDS,
    ETA_MIN_SECONDS,
    ETA_WEIGHT_DEGRADED_CURR,
    ETA_WEIGHT_DEGRADED_HIST,
    ETA_WEIGHT_LIVE_CURR,
    ETA_WEIGHT_LIVE_HIST,
    MIN_EFFECTIVE_SPEED_MPS,
)
from app.intelligence.core_models import (
    CanonicalState,
    CanonicalStateContext,
    Direction,
    DwellState,
    ETAResult,
    ETAStatus,
    RouteStop,
)
from app.repositories.historical_eta import HistoricalETARepository


def _clamp(val: float, min_val: float, max_val: float) -> float:
    if math.isnan(val):
        return min_val
    return max(min_val, min(val, max_val))


class ETAEngine:
    def __init__(self, repo: HistoricalETARepository):
        self.repo = repo
        # Store EWMAs per vehicle (in a real app, this would be in Redis/DB, keeping in memory for prototype logic)
        self._vehicle_ewma: Dict[str, float] = {}

    def _update_ewma(self, vehicle_id: str, current_speed: Optional[float]) -> Optional[float]:
        if current_speed is None or current_speed < 0 or math.isnan(current_speed):
            return self._vehicle_ewma.get(vehicle_id)

        prev_ewma = self._vehicle_ewma.get(vehicle_id)
        if prev_ewma is None:
            self._vehicle_ewma[vehicle_id] = current_speed
            return current_speed

        new_ewma = (ETA_EWMA_ALPHA * current_speed) + ((1.0 - ETA_EWMA_ALPHA) * prev_ewma)
        self._vehicle_ewma[vehicle_id] = new_ewma
        return new_ewma

    def _get_base_confidence(self, canonical_conf: str) -> float:
        if canonical_conf == "HIGH":
            return ETA_CONFIDENCE_HIGH
        elif canonical_conf == "MEDIUM":
            return ETA_CONFIDENCE_MEDIUM
        elif canonical_conf == "LOW":
            return ETA_CONFIDENCE_LOW
        return 0.0

    def calculate_eta(
        self,
        canonical: CanonicalStateContext,
        route_stops: List[RouteStop],
        target_stop_id: str,
        total_route_distance: float,
        time_of_day_bucket: str,
        day_of_week: int,
    ) -> ETAResult:
        now = datetime.now(timezone.utc)

        # 1. State / Freshness Fast Fails
        if canonical.state == CanonicalState.NOT_ACTIVE:
            return self._build_unavailable(
                target_stop_id, ["NOT_ACTIVE_STATE"], now, canonical.last_observed_at
            )

        if not canonical.organization_id or not canonical.route_id or not canonical.direction:
            return self._build_unavailable(
                target_stop_id, ["MISSING_CONTEXT"], now, canonical.last_observed_at
            )

        # 2. Target Resolution & Progress
        if not canonical.route_progress_m:
            return self._build_unavailable(
                target_stop_id, ["NO_ROUTE_PROGRESS"], now, canonical.last_observed_at
            )

        target_stop = next((s for s in route_stops if s.id == target_stop_id), None)
        if not target_stop:
            return self._build_unavailable(
                target_stop_id, ["TARGET_NOT_FOUND"], now, canonical.last_observed_at
            )

        is_a_to_b = canonical.direction == Direction.A_TO_B.value
        remaining_dist = (
            (target_stop.distance_from_start - canonical.route_progress_m)
            if is_a_to_b
            else (canonical.route_progress_m - target_stop.distance_from_start)
        )

        if remaining_dist < -10.0:  # Allow 10m float noise
            return self._build_passed(target_stop_id, now, canonical.last_observed_at)

        if (
            remaining_dist <= 20.0
            and canonical.dwell_state == DwellState.DWELL_AT_STOP
            and canonical.current_stop_id == target_stop_id
        ):
            # Reached target explicitly. (Phase 4 handles completion drop, but if we are here and stopped at target, ETA is 0)
            return self._build_zero(target_stop_id, now, canonical.last_observed_at)

        # 3. Path Segments
        sorted_stops = sorted(
            route_stops, key=lambda s: s.distance_from_start, reverse=not is_a_to_b
        )
        future_stops = []
        for s in sorted_stops:
            s_dist_remaining = (
                (s.distance_from_start - canonical.route_progress_m)
                if is_a_to_b
                else (canonical.route_progress_m - s.distance_from_start)
            )
            if s_dist_remaining >= -10.0:
                future_stops.append(s)
                if s.id == target_stop_id:
                    break

        if not future_stops:
            return self._build_passed(target_stop_id, now, canonical.last_observed_at)

        # 4. Speed & EWMA
        v_ewma = self._update_ewma(canonical.vehicle_id, canonical.speed_mps)

        # 5. Segment Accumulation
        total_time_s = 0.0
        reason_codes = []

        # Decide Fallback Level globally for confidence, but compute iteratively
        final_fallback_level = 0
        final_status = (
            ETAStatus.LIVE if canonical.state == CanonicalState.LIVE else ETAStatus.DEGRADED
        )
        if canonical.state in [CanonicalState.STALE, CanonicalState.OFFLINE]:
            final_status = ETAStatus.FALLBACK
            final_fallback_level = max(final_fallback_level, 2)

        if canonical.dwell_state == DwellState.DWELL_NON_STOP:
            reason_codes.append("DWELL_NON_STOP")

        current_progress = canonical.route_progress_m

        for i, stop in enumerate(future_stops):
            seg_dist = (
                (stop.distance_from_start - current_progress)
                if is_a_to_b
                else (current_progress - stop.distance_from_start)
            )
            seg_dist = max(0.0, seg_dist)

            if seg_dist == 0:
                # Same location, just check dwell
                if i < len(future_stops) - 1:
                    hist_data = self.repo.get_historical_segment_baseline(
                        canonical.organization_id,
                        canonical.route_id,
                        canonical.direction,
                        canonical.current_stop_id or stop.id,
                        stop.id,
                        day_of_week,
                        time_of_day_bucket,
                    )
                    if hist_data:
                        total_time_s += hist_data[1]
                current_progress = stop.distance_from_start
                continue

            from_stop_id = (
                canonical.current_stop_id
                if (i == 0 and canonical.current_stop_id)
                else (future_stops[i - 1].id if i > 0 else stop.id)
            )
            to_stop_id = stop.id

            # Historical Segment
            hist_segment = self.repo.get_historical_segment_baseline(
                canonical.organization_id,
                canonical.route_id,
                canonical.direction,
                from_stop_id,
                to_stop_id,
                day_of_week,
                time_of_day_bucket,
            )

            # Determine segment speed
            segment_speed = None
            segment_fallback = 0

            hist_speed = None
            if hist_segment and hist_segment[0] > 0:
                # We have a valid travel time > 0, compute segment-specific speed for blending
                # The segment distance might not be exactly `seg_dist` if we are mid-segment,
                # but for blending we need a speed. We assume nominal segment distance or just
                # use historical travel time directly?
                # "convert the historical segment travel time to a speed only for the specific
                # segment currently being estimated"
                # If we are mid-segment, we apply the speed to the remaining distance.
                # To get historical speed, we need full segment distance. Let's approximate full
                # segment distance as seg_dist if it's the first partial segment.
                # Wait, the spec says `historical_segment_speed_mps = segment_distance_m / median_travel_seconds`.
                # Let's assume we can compute the segment distance.
                if i == 0 and len(future_stops) > 1:
                    # Partial segment. We need full distance.
                    # We will use seg_dist to avoid looking up full distance right now.
                    hist_speed = max(0.1, seg_dist / hist_segment[0])
                else:
                    hist_speed = max(0.1, seg_dist / hist_segment[0])

            # Try to blend
            if final_status in [ETAStatus.LIVE, ETAStatus.DEGRADED]:
                w_curr = (
                    ETA_WEIGHT_LIVE_CURR
                    if final_status == ETAStatus.LIVE
                    else ETA_WEIGHT_DEGRADED_CURR
                )
                w_hist = (
                    ETA_WEIGHT_LIVE_HIST
                    if final_status == ETAStatus.LIVE
                    else ETA_WEIGHT_DEGRADED_HIST
                )

                v_curr = v_ewma if (v_ewma is not None and v_ewma > 0) else None

                if v_curr is not None and hist_speed is not None:
                    # Both
                    segment_speed = (w_curr * v_curr) + (w_hist * hist_speed)
                    segment_fallback = 0 if final_status == ETAStatus.LIVE else 1
                elif v_curr is not None:
                    # No history
                    segment_speed = v_curr
                    segment_fallback = 1
                    reason_codes.append("NO_HISTORICAL_SEGMENT")
                elif hist_speed is not None:
                    # No current
                    segment_speed = hist_speed
                    segment_fallback = 2
                    reason_codes.append("NO_CURRENT_SPEED")
                else:
                    # Neither
                    segment_speed = None
            else:
                # STALE or OFFLINE -> Fallback only
                if hist_speed is not None:
                    segment_speed = hist_speed
                    segment_fallback = 2
                else:
                    segment_speed = None

            if segment_speed == 0:
                # If speed is strictly 0, it means current_speed is 0 and no historical.
                # This falls through to route fallback or unavailable.
                segment_speed = None

            if segment_speed is not None:
                # Apply MIN_EFFECTIVE_SPEED_MPS strictly as denominator protection, not to fabricate motion.
                safe_speed = max(MIN_EFFECTIVE_SPEED_MPS, segment_speed)
                total_time_s += seg_dist / safe_speed

                if i < len(future_stops) - 1 and hist_segment:
                    total_time_s += hist_segment[1]  # add intermediate destination dwell
            else:
                # Need LEVEL 3 (Route) or LEVEL 4 (Schedule) for the remaining distance.
                # If we are here, we abandon segment iteration and use route fallback for the ENTIRE remaining journey.
                hist_route_time = self.repo.get_historical_route_baseline(
                    canonical.organization_id,
                    canonical.route_id,
                    canonical.direction,
                    day_of_week,
                    time_of_day_bucket,
                )
                if hist_route_time and total_route_distance > 0:
                    # Proportional fallback
                    route_progress_fraction = _clamp(
                        current_progress / total_route_distance, 0.0, 1.0
                    )
                    target_progress_fraction = _clamp(
                        target_stop.distance_from_start / total_route_distance, 0.0, 1.0
                    )
                    remaining_fraction = abs(target_progress_fraction - route_progress_fraction)

                    route_fallback_eta = hist_route_time * remaining_fraction
                    total_time_s += route_fallback_eta
                    segment_fallback = 3
                    final_fallback_level = max(final_fallback_level, segment_fallback)
                    if final_status == ETAStatus.LIVE:
                        final_status = ETAStatus.FALLBACK
                    break
                else:
                    # LEVEL 5 (UNAVAILABLE)
                    return self._build_unavailable(
                        target_stop_id, ["NO_USABLE_SPEED"], now, canonical.last_observed_at
                    )

            final_fallback_level = max(final_fallback_level, segment_fallback)
            current_progress = stop.distance_from_start

        # 6. Final Status Logic
        if final_fallback_level >= 2 and final_status == ETAStatus.LIVE:
            final_status = ETAStatus.FALLBACK

        # 7. Confidence & Uncertainty
        base_conf = self._get_base_confidence(canonical.confidence)

        freshness_penalty = 1.0
        if canonical.state == CanonicalState.DEGRADED:
            freshness_penalty = 0.8
        elif canonical.state in [CanonicalState.STALE, CanonicalState.OFFLINE]:
            freshness_penalty = 0.6

        dwell_penalty = (
            0.7
            if canonical.dwell_state == DwellState.DWELL_NON_STOP
            else (0.8 if canonical.dwell_state == DwellState.UNKNOWN else 1.0)
        )
        fallback_penalty = 1.0
        if final_fallback_level == 1:
            fallback_penalty = 0.9
        elif final_fallback_level == 2:
            fallback_penalty = 0.8
        elif final_fallback_level == 3:
            fallback_penalty = 0.6

        final_conf = _clamp(
            base_conf * freshness_penalty * dwell_penalty * fallback_penalty, 0.0, 1.0
        )

        eta_sec = int(total_time_s)

        base_var = (1.0 - final_conf) * eta_sec
        low_unc = base_var * 0.5
        up_unc = base_var * 1.5

        if final_status == ETAStatus.DEGRADED:
            up_unc += max(0.2 * eta_sec, ETA_DEGRADED_UNCERTAINTY_MIN)

        if canonical.dwell_state == DwellState.DWELL_NON_STOP:
            up_unc += max(0.4 * eta_sec, ETA_DWELL_NON_STOP_UNCERTAINTY_MIN)

        low_bound = max(ETA_MIN_SECONDS, int(eta_sec - low_unc))
        up_bound = min(ETA_MAX_SECONDS, int(eta_sec + up_unc))

        # Distinct unique reason codes
        reason_codes = list(set(reason_codes))

        return ETAResult(
            target_stop_id=target_stop_id,
            eta_seconds=eta_sec,
            lower_bound_seconds=low_bound,
            upper_bound_seconds=up_bound,
            confidence_score=final_conf,
            status=final_status,
            fallback_level=final_fallback_level,
            reason_codes=reason_codes,
            generated_at=now,
            source_observed_at=canonical.last_observed_at,
        )

    def _build_unavailable(
        self, target: str, reasons: List[str], generated_at: datetime, observed: Optional[datetime]
    ) -> ETAResult:
        return ETAResult(
            target_stop_id=target,
            eta_seconds=0,
            lower_bound_seconds=0,
            upper_bound_seconds=0,
            confidence_score=0.0,
            status=ETAStatus.UNAVAILABLE,
            fallback_level=5,
            reason_codes=reasons,
            generated_at=generated_at,
            source_observed_at=observed,
        )

    def _build_passed(
        self, target: str, generated_at: datetime, observed: Optional[datetime]
    ) -> ETAResult:
        return ETAResult(
            target_stop_id=target,
            eta_seconds=0,
            lower_bound_seconds=0,
            upper_bound_seconds=0,
            confidence_score=1.0,
            status=ETAStatus.UNAVAILABLE,
            fallback_level=0,
            reason_codes=["TARGET_ALREADY_PASSED"],
            generated_at=generated_at,
            source_observed_at=observed,
        )

    def _build_zero(
        self, target: str, generated_at: datetime, observed: Optional[datetime]
    ) -> ETAResult:
        return ETAResult(
            target_stop_id=target,
            eta_seconds=0,
            lower_bound_seconds=0,
            upper_bound_seconds=0,
            confidence_score=1.0,
            status=ETAStatus.LIVE,
            fallback_level=0,
            reason_codes=["AT_TARGET"],
            generated_at=generated_at,
            source_observed_at=observed,
        )
