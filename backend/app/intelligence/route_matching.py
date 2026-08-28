import math
from typing import List, Optional, Tuple

from .config import (
    CONTINUITY_PROGRESS_SCALE,
    MAX_IMPOSSIBLE_SPEED_MPS,
    MEANINGFUL_RETROGRADE_SCORE,
    MIN_ROUTE_MATCH_SCORE,
    MIN_SCORE_MARGIN,
    ROUTE_DISTANCE_SCALE,
    ROUTE_WEIGHT_CONTINUITY,
    ROUTE_WEIGHT_DISTANCE,
    ROUTE_WEIGHT_HEADING,
    ROUTE_WEIGHT_PROGRESSION,
    ROUTE_WEIGHT_SPEED,
    SEARCH_RADIUS_ACCURACY_FACTOR,
    SEARCH_RADIUS_BASE_M,
    SEARCH_RADIUS_MAX_M,
    SEARCH_RADIUS_SAFETY_MARGIN_M,
    SMALL_RETROGRADE_SCORE,
    SMALL_RETROGRADE_TOLERANCE_M,
    SPEED_CONSISTENCY_LARGE_MPS,
    SPEED_CONSISTENCY_MODERATE_MPS,
)
from .core_models import (
    Direction,
    RouteCandidate,
    RouteMatchContext,
    RouteMatchDiagnostic,
    RouteMatchResult,
    RouteMatchStatus,
    TelemetryPacket,
)
from .direction import DirectionEngine
from .gps_validation import haversine_distance


def calculate_search_radius(
    accuracy_m: Optional[float], expected_distance: Optional[float] = None
) -> float:
    """Calculates adaptive search radius for PostGIS candidate retrieval."""
    acc = accuracy_m if accuracy_m is not None else 10.0
    r_acc = acc * SEARCH_RADIUS_ACCURACY_FACTOR

    r_exp = 0.0
    if expected_distance is not None:
        r_exp = expected_distance + SEARCH_RADIUS_SAFETY_MARGIN_M

    return min(SEARCH_RADIUS_MAX_M, max(SEARCH_RADIUS_BASE_M, r_acc, r_exp))


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate forward bearing from point 1 to point 2."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlon_r = math.radians(lon2 - lon1)

    x = math.sin(dlon_r) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - (
        math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon_r)
    )

    initial_bearing = math.atan2(x, y)
    return (math.degrees(initial_bearing) + 360) % 360


def project_and_distance(
    lat: float, lon: float, lat_a: float, lon_a: float, lat_b: float, lon_b: float
) -> Tuple[float, float, float, float, float]:
    """
    Project point onto a line segment locally.
    Returns: (proj_lat, proj_lon, cross_track_m, t_fraction, segment_length_m)
    """
    mean_lat_rad = math.radians((lat_a + lat_b) / 2.0)
    cos_lat = math.cos(mean_lat_rad)

    R = 6371000.0
    deg2rad = math.pi / 180.0

    x_p = (lon - lon_a) * deg2rad * cos_lat * R
    y_p = (lat - lat_a) * deg2rad * R

    x_b = (lon_b - lon_a) * deg2rad * cos_lat * R
    y_b = (lat_b - lat_a) * deg2rad * R

    l2 = x_b * x_b + y_b * y_b
    if l2 == 0:
        return lat_a, lon_a, haversine_distance(lat, lon, lat_a, lon_a), 0.0, 0.0

    t = (x_p * x_b + y_p * y_b) / l2
    t = max(0.0, min(1.0, t))

    proj_x = t * x_b
    proj_y = t * y_b

    cross_track = math.hypot(x_p - proj_x, y_p - proj_y)

    proj_lon = lon_a + (proj_x / (deg2rad * cos_lat * R)) if cos_lat != 0 else lon_a
    proj_lat = lat_a + (proj_y / (deg2rad * R))

    segment_len = math.sqrt(l2)

    return proj_lat, proj_lon, cross_track, t, segment_len


class RouteMatcher:
    @staticmethod
    def match_route(
        packet: TelemetryPacket,
        candidates: List[RouteCandidate],
        previous_context: Optional[RouteMatchContext] = None,
    ) -> RouteMatchResult:
        if not candidates:
            return RouteMatchResult(
                status=RouteMatchStatus.NO_MATCH,
                route_id=None,
                segment_index=None,
                projected_lat=None,
                projected_lon=None,
                cross_track_distance_m=None,
                route_progress_m=None,
                match_confidence=0.0,
                direction=Direction.UNKNOWN,
                diagnostic_codes=[RouteMatchDiagnostic.NO_ROUTE_CANDIDATE],
            )

        dt = 0.0
        if previous_context:
            dt = (packet.observed_at - previous_context.matched_at).total_seconds()

        best_candidate = None
        best_score = -1.0
        second_best_score = -1.0

        for candidate in candidates:
            # 1. Evaluate geometry
            coords = candidate.geometry_coordinates
            if len(coords) < 2:
                continue

            lat_a, lon_a = coords[0]
            lat_b, lon_b = coords[1]

            p_lat, p_lon, dist, t, seg_len = project_and_distance(
                packet.lat, packet.lon, lat_a, lon_a, lat_b, lon_b
            )

            closest_idx = candidate.segment_index
            closest_dist = dist
            closest_proj = (p_lat, p_lon)
            closest_seg_len = seg_len
            closest_progress = candidate.segment_progress_start_m + (t * seg_len)

            # 2. Score Candidate
            # Sdist
            acc = packet.accuracy_m if packet.accuracy_m is not None else 10.0
            s_dist = math.exp(-closest_dist / max(acc, ROUTE_DISTANCE_SCALE))

            # Shead
            s_head = None
            if packet.heading is not None and closest_seg_len > 0:
                seg_heading = bearing(lat_a, lon_a, lat_b, lon_b)
                diff1 = abs(packet.heading - seg_heading) % 360
                if diff1 > 180:
                    diff1 = 360 - diff1

                diff2 = abs(packet.heading - ((seg_heading + 180) % 360)) % 360
                if diff2 > 180:
                    diff2 = 360 - diff2

                best_diff = min(diff1, diff2)
                s_head = max(0.0, 1.0 - (best_diff / 90.0))

            # Scont, Sprog, Sspeed
            s_cont = None
            s_prog = None
            s_speed = None

            if previous_context and previous_context.route_id == candidate.route_id:
                prev_prog = previous_context.route_progress_m
                cand_prog_delta = closest_progress - prev_prog

                if dt > 0:
                    cand_speed = abs(cand_prog_delta) / dt

                    # Sspeed
                    if packet.speed_mps is not None:
                        speed_delta = abs(cand_speed - packet.speed_mps)
                        if speed_delta <= SPEED_CONSISTENCY_MODERATE_MPS:
                            s_speed = 1.0
                        elif speed_delta < SPEED_CONSISTENCY_LARGE_MPS:
                            s_speed = 1.0 - (speed_delta - SPEED_CONSISTENCY_MODERATE_MPS) / (
                                SPEED_CONSISTENCY_LARGE_MPS - SPEED_CONSISTENCY_MODERATE_MPS
                            )
                        else:
                            s_speed = 0.0

                    # Sprog
                    if cand_speed > MAX_IMPOSSIBLE_SPEED_MPS:
                        s_prog = 0.0
                    else:
                        prev_dir = previous_context.direction
                        is_retrograde = False

                        if prev_dir == Direction.A_TO_B and cand_prog_delta < 0:
                            is_retrograde = True
                        elif prev_dir == Direction.B_TO_A and cand_prog_delta > 0:
                            is_retrograde = True

                        if is_retrograde:
                            if abs(cand_prog_delta) <= SMALL_RETROGRADE_TOLERANCE_M:
                                s_prog = SMALL_RETROGRADE_SCORE
                            else:
                                # We do not blindly reject (0.0). We return a strong penalty
                                # to reduce confidence or create an AMBIGUOUS result, unless we
                                # eventually add trip state logic that promotes it to LEGITIMATE_REVERSAL_SCORE.
                                s_prog = MEANINGFUL_RETROGRADE_SCORE
                        else:
                            s_prog = 1.0

                    # Scont
                    if packet.speed_mps is not None:
                        expected_prog_delta = 0.0
                        if previous_context.direction == Direction.A_TO_B:
                            expected_prog_delta = packet.speed_mps * dt
                        elif previous_context.direction == Direction.B_TO_A:
                            expected_prog_delta = -packet.speed_mps * dt

                        error_m = abs(cand_prog_delta - expected_prog_delta)
                        s_cont = math.exp(-error_m / CONTINUITY_PROGRESS_SCALE)
                    else:
                        s_cont = None  # Unavailable if no speed evidence

            # Weight Renormalization
            weights = {"dist": ROUTE_WEIGHT_DISTANCE}
            scores = {"dist": s_dist}

            if s_head is not None:
                weights["head"] = ROUTE_WEIGHT_HEADING
                scores["head"] = s_head
            if s_cont is not None:
                weights["cont"] = ROUTE_WEIGHT_CONTINUITY
                scores["cont"] = s_cont
            if s_prog is not None:
                weights["prog"] = ROUTE_WEIGHT_PROGRESSION
                scores["prog"] = s_prog
            if s_speed is not None:
                weights["speed"] = ROUTE_WEIGHT_SPEED
                scores["speed"] = s_speed

            total_weight = sum(weights.values())
            if total_weight == 0:
                total_weight = 1.0

            final_score = sum(scores[k] * (weights[k] / total_weight) for k in weights.keys())

            if final_score > best_score:
                second_best_score = best_score
                best_score = final_score
                best_candidate = {
                    "route_id": candidate.route_id,
                    "segment_index": closest_idx,
                    "projected_lat": closest_proj[0],
                    "projected_lon": closest_proj[1],
                    "cross_track_m": closest_dist,
                    "progress_m": closest_progress,
                    "score": final_score,
                }
            elif final_score > second_best_score:
                second_best_score = final_score

        if not best_candidate:
            return RouteMatchResult(
                status=RouteMatchStatus.NO_MATCH,
                route_id=None,
                segment_index=None,
                projected_lat=None,
                projected_lon=None,
                cross_track_distance_m=None,
                route_progress_m=None,
                match_confidence=0.0,
                direction=Direction.UNKNOWN,
                diagnostic_codes=[RouteMatchDiagnostic.NO_ROUTE_CANDIDATE],
            )

        diagnostics = []
        if best_score < MIN_ROUTE_MATCH_SCORE:
            diagnostics.append(RouteMatchDiagnostic.LOW_ROUTE_CONFIDENCE)
            return RouteMatchResult(
                status=RouteMatchStatus.NO_MATCH,
                route_id=None,
                segment_index=None,
                projected_lat=None,
                projected_lon=None,
                cross_track_distance_m=None,
                route_progress_m=None,
                match_confidence=best_score,
                direction=Direction.UNKNOWN,
                diagnostic_codes=diagnostics,
            )

        if (best_score - second_best_score) < MIN_SCORE_MARGIN and second_best_score > 0:
            diagnostics.append(RouteMatchDiagnostic.AMBIGUOUS_CANDIDATES)
            return RouteMatchResult(
                status=RouteMatchStatus.AMBIGUOUS,
                route_id=None,
                segment_index=None,
                projected_lat=None,
                projected_lon=None,
                cross_track_distance_m=None,
                route_progress_m=None,
                match_confidence=best_score,
                direction=Direction.UNKNOWN,
                diagnostic_codes=diagnostics,
            )

        # Direction inference
        new_dir = Direction.UNKNOWN
        if previous_context and previous_context.route_id == best_candidate["route_id"]:
            new_dir, _, _ = DirectionEngine.infer_direction_state(
                best_candidate["progress_m"], previous_context
            )

        diagnostics.append(RouteMatchDiagnostic.MATCHED)

        return RouteMatchResult(
            status=RouteMatchStatus.MATCHED,
            route_id=best_candidate["route_id"],
            segment_index=best_candidate["segment_index"],
            projected_lat=best_candidate["projected_lat"],
            projected_lon=best_candidate["projected_lon"],
            cross_track_distance_m=best_candidate["cross_track_m"],
            route_progress_m=best_candidate["progress_m"],
            match_confidence=best_candidate["score"],
            direction=new_dir,
            diagnostic_codes=diagnostics,
        )
