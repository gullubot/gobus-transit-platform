import math
from datetime import datetime
from typing import Optional

from .config import (
    ALLOWED_CLOCK_SKEW_SECONDS,
    COARSE_GEO_BOUNDS,
    CONFIDENCE_PENALTY_HIGH_ACCELERATION,
    CONFIDENCE_PENALTY_HIGH_SPEED,
    CONFIDENCE_PENALTY_LOW_GPS,
    CONFIDENCE_PENALTY_SPEED_INCONSISTENCY,
    CONTINUITY_SPEED_SCALE,
    HISTORICAL_CLASSIFICATION_HORIZON_SECONDS,
    HISTORICAL_TIMESTAMP_SCORE,
    MAX_IMPOSSIBLE_SPEED_MPS,
    MAX_PLAUSIBLE_ACCEL_MPS2,
    MIN_PHYSICAL_DELTA_T_SECONDS,
    SPEED_CONSISTENCY_LARGE_MPS,
    SPEED_CONSISTENCY_MODERATE_MPS,
    SUSPICIOUS_SPEED_THRESHOLD_MPS,
    WEIGHT_ACCURACY,
    WEIGHT_CONTINUITY,
    WEIGHT_SPEED,
    WEIGHT_TIMESTAMP,
)
from .core_models import (
    PreviousStateContext,
    TelemetryPacket,
    ValidationDiagnostic,
    ValidationReport,
    ValidationStatus,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two coordinates."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


class GPSValidator:
    @staticmethod
    def validate_packet(
        packet: TelemetryPacket,
        current_time: datetime,
        previous_state: Optional[PreviousStateContext] = None,
    ) -> ValidationReport:
        diagnostics = []
        is_historical = False

        # STEP 1: Coarse geographic sanity
        if packet.lat == 0.0 and packet.lon == 0.0:
            diagnostics.append(ValidationDiagnostic.COARSE_OUT_OF_BOUNDS)
            return ValidationReport(ValidationStatus.REJECTED, None, is_historical, diagnostics)

        lat_min, lat_max, lon_min, lon_max = COARSE_GEO_BOUNDS
        if not (lat_min <= packet.lat <= lat_max and lon_min <= packet.lon <= lon_max):
            diagnostics.append(ValidationDiagnostic.COARSE_OUT_OF_BOUNDS)
            return ValidationReport(ValidationStatus.REJECTED, None, is_historical, diagnostics)

        # STEP 2: Timestamp
        time_diff = (packet.observed_at - current_time).total_seconds()
        if time_diff > ALLOWED_CLOCK_SKEW_SECONDS:
            diagnostics.append(ValidationDiagnostic.FUTURE_TIMESTAMP)
            return ValidationReport(ValidationStatus.REJECTED, None, is_historical, diagnostics)

        if time_diff < -HISTORICAL_CLASSIFICATION_HORIZON_SECONDS:
            is_historical = True

        # STEP 3: Physical plausibility
        implied_speed: Optional[float] = None
        implied_acceleration: Optional[float] = None
        delta_t: Optional[float] = None

        if previous_state is not None:
            delta_t = (packet.observed_at - previous_state.observed_at).total_seconds()
            distance = haversine_distance(
                previous_state.lat, previous_state.lon, packet.lat, packet.lon
            )

            if delta_t > 0:
                implied_speed = distance / delta_t
            elif delta_t == 0 and distance > 0:
                implied_speed = float("inf")
            elif delta_t == 0 and distance == 0:
                implied_speed = 0.0

            if (
                delta_t is not None
                and delta_t >= MIN_PHYSICAL_DELTA_T_SECONDS
                and implied_speed is not None
            ):
                if previous_state.speed_mps is not None:
                    implied_acceleration = abs(implied_speed - previous_state.speed_mps) / delta_t
                else:
                    implied_acceleration = None

        # STEP 4: Compare reported vs implied speed
        speed_consistency_delta: Optional[float] = None
        if packet.speed_mps is not None and implied_speed is not None:
            speed_consistency_delta = abs(packet.speed_mps - implied_speed)

        # STEP 5: Determine Plausible, Improbable, Impossible
        is_impossible = False
        is_improbable = False

        if implied_speed is not None:
            if implied_speed > MAX_IMPOSSIBLE_SPEED_MPS:
                is_impossible = True
                if ValidationDiagnostic.IMPOSSIBLE_SPEED not in diagnostics:
                    diagnostics.append(ValidationDiagnostic.IMPOSSIBLE_SPEED)
            elif implied_speed > SUSPICIOUS_SPEED_THRESHOLD_MPS:
                is_improbable = True
                if ValidationDiagnostic.HIGH_IMPLIED_SPEED not in diagnostics:
                    diagnostics.append(ValidationDiagnostic.HIGH_IMPLIED_SPEED)

        if implied_acceleration is not None and implied_acceleration > MAX_PLAUSIBLE_ACCEL_MPS2:
            is_improbable = True
            if ValidationDiagnostic.HIGH_IMPLIED_ACCELERATION not in diagnostics:
                diagnostics.append(ValidationDiagnostic.HIGH_IMPLIED_ACCELERATION)

        if (
            speed_consistency_delta is not None
            and speed_consistency_delta >= SPEED_CONSISTENCY_LARGE_MPS
        ):
            is_improbable = True
            if ValidationDiagnostic.SPEED_INCONSISTENCY not in diagnostics:
                diagnostics.append(ValidationDiagnostic.SPEED_INCONSISTENCY)

        if packet.accuracy_m is not None and packet.accuracy_m >= 50.0:
            if ValidationDiagnostic.LOW_GPS_CONFIDENCE not in diagnostics:
                diagnostics.append(ValidationDiagnostic.LOW_GPS_CONFIDENCE)

        # STEP 6: Map
        if is_impossible:
            return ValidationReport(ValidationStatus.REJECTED, None, is_historical, diagnostics)

        status = ValidationStatus.SUSPICIOUS if is_improbable else ValidationStatus.VALID

        # STEP 7: Calculate Confidence
        accuracy_score: Optional[float] = None
        if packet.accuracy_m is not None:
            if packet.accuracy_m <= 10.0:
                accuracy_score = 1.0
            elif packet.accuracy_m < 50.0:
                accuracy_score = 1.0 - 0.5 * ((packet.accuracy_m - 10.0) / 40.0)
            elif packet.accuracy_m <= 100.0:
                accuracy_score = 0.5 - 0.5 * ((packet.accuracy_m - 50.0) / 50.0)
            else:
                accuracy_score = 0.0

        speed_score: Optional[float] = None
        if speed_consistency_delta is not None:
            if speed_consistency_delta <= SPEED_CONSISTENCY_MODERATE_MPS:
                speed_score = 1.0
            elif speed_consistency_delta < SPEED_CONSISTENCY_LARGE_MPS:
                speed_score = 1.0 - (
                    (speed_consistency_delta - SPEED_CONSISTENCY_MODERATE_MPS)
                    / (SPEED_CONSISTENCY_LARGE_MPS - SPEED_CONSISTENCY_MODERATE_MPS)
                )
            else:
                speed_score = 0.0

        continuity_score: Optional[float] = None
        if previous_state is not None and implied_speed is not None:
            expected_speed = (
                previous_state.speed_mps if previous_state.speed_mps is not None else implied_speed
            )
            speed_error = abs(implied_speed - expected_speed)
            continuity_score = math.exp(-speed_error / CONTINUITY_SPEED_SCALE)

        timestamp_score = HISTORICAL_TIMESTAMP_SCORE if is_historical else 1.0

        # Renormalize weights
        weights = {}
        if accuracy_score is not None:
            weights["accuracy"] = WEIGHT_ACCURACY
        if speed_score is not None:
            weights["speed"] = WEIGHT_SPEED
        if continuity_score is not None:
            weights["continuity"] = WEIGHT_CONTINUITY
        weights["timestamp"] = WEIGHT_TIMESTAMP

        total_weight = sum(weights.values())
        if total_weight == 0.0:
            total_weight = 1.0  # Fallback to avoid division by zero

        base_confidence = 0.0
        if accuracy_score is not None:
            base_confidence += accuracy_score * (WEIGHT_ACCURACY / total_weight)
        if speed_score is not None:
            base_confidence += speed_score * (WEIGHT_SPEED / total_weight)
        if continuity_score is not None:
            base_confidence += continuity_score * (WEIGHT_CONTINUITY / total_weight)

        base_confidence += timestamp_score * (WEIGHT_TIMESTAMP / total_weight)

        # Apply non-historical diagnostic penalties
        penalized_confidence = base_confidence

        if ValidationDiagnostic.LOW_GPS_CONFIDENCE in diagnostics:
            penalized_confidence *= CONFIDENCE_PENALTY_LOW_GPS
        if ValidationDiagnostic.HIGH_IMPLIED_SPEED in diagnostics:
            penalized_confidence *= CONFIDENCE_PENALTY_HIGH_SPEED
        if ValidationDiagnostic.HIGH_IMPLIED_ACCELERATION in diagnostics:
            penalized_confidence *= CONFIDENCE_PENALTY_HIGH_ACCELERATION
        if ValidationDiagnostic.SPEED_INCONSISTENCY in diagnostics:
            penalized_confidence *= CONFIDENCE_PENALTY_SPEED_INCONSISTENCY

        final_confidence = max(0.0, min(1.0, penalized_confidence))

        return ValidationReport(status, final_confidence, is_historical, diagnostics)
