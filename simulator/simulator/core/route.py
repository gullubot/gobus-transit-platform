"""
Transit Platform — Simulation Route Model.

Represents an immutable, ordered sequence of transit stops and segments,
calculating cumulative distances and interpolation points along the route.
Does not copy or duplicate Build 3 RouteMatcher or StopProgression logic.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from simulator.core.geo import calculate_bearing, haversine_distance, interpolate_point


@dataclass(frozen=True)
class SimulatedStop:
    """Individual stop along a simulated route."""
    stop_id: str
    stop_name: str
    sequence_number: int
    latitude: float
    longitude: float
    distance_from_start_km: Optional[float] = None


@dataclass(frozen=True)
class RouteSegment:
    """Segment between two consecutive stops along the route."""
    segment_index: int
    from_stop: SimulatedStop
    to_stop: SimulatedStop
    distance_m: float
    bearing: float
    start_cumulative_m: float
    end_cumulative_m: float

    def interpolate(self, progress_m: float) -> Tuple[float, float, float]:
        """
        Interpolates coordinates and heading along this segment.
        progress_m is the distance traveled from from_stop in meters.
        Returns: (latitude, longitude, bearing)
        """
        if self.distance_m <= 0:
            return self.from_stop.latitude, self.from_stop.longitude, self.bearing
        fraction = max(0.0, min(1.0, progress_m / self.distance_m))
        lat, lon = interpolate_point(
            self.from_stop.latitude,
            self.from_stop.longitude,
            self.to_stop.latitude,
            self.to_stop.longitude,
            fraction,
        )
        return lat, lon, self.bearing


class RouteModel:
    """
    Simulation-only immutable model of a configured transit route.
    Maintains ordered stops, pre-computed segments, and cumulative distances.
    """

    def __init__(
        self,
        route_id: str,
        route_code: str,
        route_name: str,
        stops: List[SimulatedStop],
        direction: str = "A_TO_B",
    ):
        if len(stops) < 2:
            raise ValueError(f"Route {route_code} must have at least 2 stops, got {len(stops)}")

        for stop in stops:
            if not (-90.0 <= stop.latitude <= 90.0):
                raise ValueError(f"Invalid latitude {stop.latitude} for stop {stop.stop_name} ({stop.stop_id})")
            if not (-180.0 <= stop.longitude <= 180.0):
                raise ValueError(f"Invalid longitude {stop.longitude} for stop {stop.stop_name} ({stop.stop_id})")

        self.route_id = route_id
        self.route_code = route_code
        self.route_name = route_name
        self.direction = direction
        self.stops: List[SimulatedStop] = list(stops)

        # Precompute segments and cumulative distances
        self.segments: List[RouteSegment] = []
        cumulative_m = 0.0

        for i in range(len(self.stops) - 1):
            s1 = self.stops[i]
            s2 = self.stops[i + 1]
            seg_dist = haversine_distance(s1.latitude, s1.longitude, s2.latitude, s2.longitude)
            bearing = calculate_bearing(s1.latitude, s1.longitude, s2.latitude, s2.longitude)
            start_cum = cumulative_m
            end_cum = cumulative_m + seg_dist

            self.segments.append(
                RouteSegment(
                    segment_index=i,
                    from_stop=s1,
                    to_stop=s2,
                    distance_m=seg_dist,
                    bearing=bearing,
                    start_cumulative_m=start_cum,
                    end_cumulative_m=end_cum,
                )
            )
            cumulative_m = end_cum

        self.total_distance_m = cumulative_m

    @property
    def stop_count(self) -> int:
        return len(self.stops)

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    def get_segment(self, segment_index: int) -> RouteSegment:
        if not (0 <= segment_index < len(self.segments)):
            raise IndexError(f"Segment index {segment_index} out of range [0, {len(self.segments)})")
        return self.segments[segment_index]

    def __repr__(self) -> str:
        return (
            f"RouteModel(code={self.route_code!r}, stops={len(self.stops)}, "
            f"segments={len(self.segments)}, total_distance_km={self.total_distance_m / 1000.0:.2f}, "
            f"direction={self.direction!r})"
        )
