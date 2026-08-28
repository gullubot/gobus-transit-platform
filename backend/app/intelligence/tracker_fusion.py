import math
from datetime import datetime
from typing import List, Tuple

from app.intelligence import config
from app.intelligence.core_models import (
    CanonicalState,
    CanonicalStateContext,
    TrackerFusionDiagnostic,
    TrackerInput,
    TrackerState,
    ValidationStatus,
)


class TrackerFusionEngine:
    @staticmethod
    def calculate_base_reliability(tracker_input: TrackerInput) -> float:
        weights = {
            "gps": config.FUSION_WEIGHT_GPS,
            "rm": config.FUSION_WEIGHT_RM,
            "acc": config.FUSION_WEIGHT_ACC,
            "spd": config.FUSION_WEIGHT_SPD,
            "ct": config.FUSION_WEIGHT_CT,
            "sess": config.FUSION_WEIGHT_SESS,
        }

        comps = {}

        comps["gps"] = (
            tracker_input.gps_validation.confidence_score
            if tracker_input.gps_validation.confidence_score is not None
            else 0.0
        )

        if tracker_input.route_match.match_confidence is not None:
            comps["rm"] = tracker_input.route_match.match_confidence
        else:
            del weights["rm"]

        if tracker_input.accuracy_m is not None:
            acc = tracker_input.accuracy_m
            if acc <= 10.0:
                comps["acc"] = 1.0
            elif acc >= 100.0:
                comps["acc"] = 0.0
            else:
                comps["acc"] = 1.0 - ((acc - 10.0) / 90.0)
        else:
            del weights["acc"]

        if tracker_input.speed_mps is not None:
            spd = tracker_input.speed_mps
            if spd <= config.SUSPICIOUS_SPEED_THRESHOLD_MPS:
                comps["spd"] = 1.0
            elif spd >= config.MAX_IMPOSSIBLE_SPEED_MPS:
                comps["spd"] = 0.0
            else:
                comps["spd"] = 1.0 - (
                    (spd - config.SUSPICIOUS_SPEED_THRESHOLD_MPS)
                    / (config.MAX_IMPOSSIBLE_SPEED_MPS - config.SUSPICIOUS_SPEED_THRESHOLD_MPS)
                )
        else:
            del weights["spd"]

        comps["ct"] = tracker_input.stop_progression.progression_confidence
        comps["sess"] = tracker_input.session_health

        total_weight = sum(weights.values())
        if total_weight == 0.0:
            return 0.0

        base_reliability = sum(v * (weights[k] / total_weight) for k, v in comps.items())
        return min(1.0, max(0.0, base_reliability))

    @staticmethod
    def get_freshness_factor(age_seconds: float) -> float:
        if age_seconds <= config.FUSION_LIVE_MAX_AGE_SECONDS:
            return 1.0
        elif age_seconds > config.FUSION_DEGRADED_MAX_AGE_SECONDS:
            return 0.0

        diff = config.FUSION_DEGRADED_MAX_AGE_SECONDS - config.FUSION_LIVE_MAX_AGE_SECONDS
        return 1.0 - ((age_seconds - config.FUSION_LIVE_MAX_AGE_SECONDS) / diff)

    @staticmethod
    def process_tracker_input(
        context: CanonicalStateContext, tracker_input: TrackerInput, reference_time: datetime
    ) -> Tuple[CanonicalStateContext, List[TrackerFusionDiagnostic]]:
        diagnostics = []
        source_id = tracker_input.source_id

        if source_id not in context.trackers:
            context.trackers[source_id] = TrackerState(source_id=source_id)

        tracker_state = context.trackers[source_id]

        # Duplicate check
        if tracker_state.last_packet_id == tracker_input.packet_id:
            diagnostics.append(TrackerFusionDiagnostic.DUPLICATE_PACKET)
            return context, diagnostics

        tracker_state.last_packet_id = tracker_input.packet_id

        # High-water check
        if (
            tracker_state.last_observed_at
            and tracker_input.observed_at < tracker_state.last_observed_at
        ):
            diagnostics.append(TrackerFusionDiagnostic.HISTORICAL_PACKET)
            return context, diagnostics

        age_seconds = (reference_time - tracker_input.observed_at).total_seconds()

        # Calculate reliability
        base_reliability = TrackerFusionEngine.calculate_base_reliability(tracker_input)
        freshness_factor = TrackerFusionEngine.get_freshness_factor(age_seconds)
        final_reliability = base_reliability * freshness_factor

        # Check basic trust rules
        is_valid = (
            tracker_input.gps_validation.status == ValidationStatus.VALID
            and age_seconds <= config.FUSION_STALE_MAX_AGE_SECONDS
            and tracker_input.session_health > 0.0
            and tracker_input.trip_inference.status != "COMPLETED"
        )

        tracker_state.last_observed_at = tracker_input.observed_at
        tracker_state.last_reliability = final_reliability
        tracker_state.is_trusted = is_valid

        if is_valid:
            tracker_state.consecutive_valid_observations += 1
        else:
            tracker_state.consecutive_valid_observations = 0

        # Store latest input per source for canonical evaluation
        if not hasattr(context, "_latest_inputs"):
            context._latest_inputs = {}
        context._latest_inputs[source_id] = tracker_input

        # Now evaluate canonical state
        TrackerFusionEngine._evaluate_canonical_state(context, reference_time, diagnostics)

        return context, diagnostics

    @staticmethod
    def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        # Haversine formula
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def _evaluate_canonical_state(
        context: CanonicalStateContext,
        reference_time: datetime,
        diagnostics: List[TrackerFusionDiagnostic],
    ):
        if not hasattr(context, "_latest_inputs"):
            return

        active_inputs = {}
        for source_id, tracker_state in context.trackers.items():
            if tracker_state.is_trusted and source_id in context._latest_inputs:
                inp = context._latest_inputs[source_id]
                age = (reference_time - inp.observed_at).total_seconds()
                if age <= config.FUSION_STALE_MAX_AGE_SECONDS:
                    active_inputs[source_id] = (inp, tracker_state)

        if not active_inputs:
            # Handle degradation / offline
            if context.last_observed_at:
                age = (reference_time - context.last_observed_at).total_seconds()
                if age > config.FUSION_STALE_MAX_AGE_SECONDS:
                    context.state = CanonicalState.OFFLINE
                elif age > config.FUSION_DEGRADED_MAX_AGE_SECONDS:
                    context.state = CanonicalState.STALE
                elif age > config.FUSION_LIVE_MAX_AGE_SECONDS:
                    context.state = CanonicalState.DEGRADED
                else:
                    context.state = (
                        CanonicalState.DEGRADED
                    )  # No trusted trackers, degrade even if fresh
            return

        # Determine best source
        # Sort by: (reliability, observed_at, deterministic source string)
        sorted_candidates = sorted(
            active_inputs.values(),
            key=lambda item: (
                -item[1].last_reliability,
                -item[0].observed_at.timestamp(),
                item[0].source_id,
            ),
        )

        best_input, best_state = sorted_candidates[0]

        winning_source = best_input.source_id
        canonical_penalty = 0.0
        large_disagreement = False

        if len(sorted_candidates) > 1:
            alt_input, alt_state = sorted_candidates[1]
            dist = TrackerFusionEngine.distance_m(
                best_input.lat, best_input.lon, alt_input.lat, alt_input.lon
            )

            if dist > config.FUSION_DISAGREEMENT_MODERATE_M:
                large_disagreement = True
                diagnostics.append(TrackerFusionDiagnostic.LARGE_DISAGREEMENT)
            elif dist > config.FUSION_DISAGREEMENT_SMALL_M:
                diagnostics.append(TrackerFusionDiagnostic.MODERATE_DISAGREEMENT)
                canonical_penalty = config.CANONICAL_MODERATE_DISAGREEMENT_PENALTY

        # Hysteresis
        current_canonical = context.canonical_source
        if (
            current_canonical
            and current_canonical in active_inputs
            and current_canonical != winning_source
        ):
            current_rel = active_inputs[current_canonical][1].last_reliability
            winning_rel = best_state.last_reliability

            # If current is completely invalid, immediate switch
            # (already handled because it wouldn't be in active_inputs)
            if winning_rel > current_rel + config.SOURCE_SWITCH_MARGIN:
                if context.candidate_source_id == winning_source:
                    context.consecutive_source_switch_observations += 1
                else:
                    context.candidate_source_id = winning_source
                    context.consecutive_source_switch_observations = 1

                if (
                    context.consecutive_source_switch_observations
                    >= config.SOURCE_SWITCH_CONFIRMATION_OBSERVATIONS
                ):
                    # Switch confirmed
                    context.canonical_source = winning_source
                else:
                    # Prevent switch, stick to current
                    winning_source = current_canonical
                    best_input, best_state = active_inputs[current_canonical]
                    diagnostics.append(TrackerFusionDiagnostic.SOURCE_SWITCH_HYSTERESIS_ACTIVE)
            else:
                # Prevent switch, reset candidate
                context.candidate_source_id = None
                context.consecutive_source_switch_observations = 0
                winning_source = current_canonical
                best_input, best_state = active_inputs[current_canonical]
        else:
            context.canonical_source = winning_source
            context.candidate_source_id = None
            context.consecutive_source_switch_observations = 0

        # Recovery logic
        if context.last_observed_at:
            gap_seconds = (best_input.observed_at - context.last_observed_at).total_seconds()
            if gap_seconds > config.FUSION_DEGRADED_MAX_AGE_SECONDS:
                context.recovery_mode_active = True

            if context.recovery_mode_active:
                dist_moved = (
                    TrackerFusionEngine.distance_m(
                        context.lat, context.lon, best_input.lat, best_input.lon
                    )
                    if context.lat
                    else 0.0
                )
                if (
                    gap_seconds > 0
                    and (dist_moved / gap_seconds) > config.MAX_PLAUSIBLE_RECOVERY_SPEED_MPS
                ):
                    diagnostics.append(TrackerFusionDiagnostic.IMPOSSIBLE_RECOVERY_SPEED)
                    # Cannot use this observation to advance state immediately
                    best_state.consecutive_recovery_observations = 0
                    return
                else:
                    best_state.consecutive_recovery_observations += 1

                if (
                    best_state.consecutive_recovery_observations
                    >= config.RECOVERY_CONFIRMATION_OBSERVATIONS
                ):
                    context.recovery_mode_active = False
                else:
                    diagnostics.append(TrackerFusionDiagnostic.RECOVERY_IN_PROGRESS)

        # High-water mark protection: never go backward in canonical time
        if context.last_observed_at and best_input.observed_at < context.last_observed_at:
            return

        # Update canonical state
        context.last_observed_at = best_input.observed_at
        context.last_received_at = best_input.received_at
        context.lat = best_input.lat
        context.lon = best_input.lon

        # Phase 5 fields
        context.speed_mps = best_input.speed_mps
        context.heading = best_input.heading
        context.dwell_state = best_input.dwell_result.state

        # Stop progression
        if best_input.stop_progression.route_progress_m is not None:
            context.route_progress_m = best_input.stop_progression.route_progress_m
        if best_input.stop_progression.current_stop_id is not None:
            context.current_stop_id = best_input.stop_progression.current_stop_id
        if best_input.stop_progression.next_stop_id is not None:
            context.next_stop_id = best_input.stop_progression.next_stop_id

        # Confidence
        raw_confidence = best_state.last_reliability * (1.0 - canonical_penalty)
        raw_confidence = min(1.0, max(0.0, raw_confidence))

        if raw_confidence >= config.CANONICAL_CONFIDENCE_HIGH_THRESHOLD:
            context.confidence = "HIGH"
        elif raw_confidence >= config.CANONICAL_CONFIDENCE_MEDIUM_THRESHOLD:
            context.confidence = "MEDIUM"
        else:
            context.confidence = "LOW"

        # State determination
        age = (reference_time - best_input.observed_at).total_seconds()

        if large_disagreement or context.recovery_mode_active:
            context.state = CanonicalState.DEGRADED
        elif age <= config.FUSION_LIVE_MAX_AGE_SECONDS and context.confidence == "HIGH":
            context.state = CanonicalState.LIVE
        elif age <= config.FUSION_DEGRADED_MAX_AGE_SECONDS:
            context.state = CanonicalState.DEGRADED
        elif age <= config.FUSION_STALE_MAX_AGE_SECONDS:
            context.state = CanonicalState.STALE
        else:
            context.state = CanonicalState.OFFLINE
