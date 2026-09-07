"""
Transit Platform — Real Route-Driven Bus Movement Engine.

Models deterministic spatial progression along route segments between configured stops.
Features realistic stop arrival, dwell periods, bearing calculations, and route completion.
"""

from dataclasses import dataclass
import random
from typing import Optional

from simulator.core.route import RouteModel, SimulatedStop


@dataclass
class MovementState:
    """Current spatial and operational state of the moving simulated bus."""
    current_latitude: float
    current_longitude: float
    current_heading: float
    current_speed_mps: float
    current_segment_index: int
    segment_progress_m: float
    total_progress_m: float
    completed_stops_count: int
    is_dwelling: bool
    dwell_time_remaining_s: float
    is_completed: bool
    current_stop: SimulatedStop
    next_stop: Optional[SimulatedStop]


class MovementEngine:
    """
    Simulates physical bus movement along an immutable RouteModel.
    Calculates position via distance = speed * delta_time, pauses at intermediate
    stops for dwell periods, and cleanly detects route completion.
    """

    def __init__(
        self,
        route: RouteModel,
        cruise_speed_mps: float = 8.33,  # ~30 km/h
        dwell_duration_seconds: float = 15.0,
        enable_noise: bool = False,
        random_seed: Optional[int] = 42,
    ):
        if cruise_speed_mps <= 0:
            raise ValueError(f"cruise_speed_mps must be > 0, got {cruise_speed_mps}")
        if dwell_duration_seconds < 0:
            raise ValueError(f"dwell_duration_seconds cannot be negative, got {dwell_duration_seconds}")

        self.route = route
        self.cruise_speed_mps = float(cruise_speed_mps)
        self.dwell_duration_seconds = float(dwell_duration_seconds)
        self.enable_noise = enable_noise
        self._rng = random.Random(random_seed) if enable_noise else None

        # Initialize at Stop 0
        first_stop = self.route.stops[0]
        first_segment = self.route.get_segment(0)

        self.current_segment_index: int = 0
        self.segment_progress_m: float = 0.0
        self.total_progress_m: float = 0.0
        self.completed_stops_count: int = 1  # Origin stop already visited

        self.current_latitude: float = first_stop.latitude
        self.current_longitude: float = first_stop.longitude
        self.current_heading: float = first_segment.bearing
        self.current_speed_mps: float = 0.0

        self.is_dwelling: bool = False
        self.dwell_time_remaining_s: float = 0.0
        self.is_completed: bool = False

    @property
    def current_stop(self) -> SimulatedStop:
        """Returns the most recently reached stop."""
        if self.is_completed:
            return self.route.stops[-1]
        seg = self.route.get_segment(self.current_segment_index)
        return seg.to_stop if self.is_dwelling else seg.from_stop

    @property
    def next_stop(self) -> Optional[SimulatedStop]:
        """Returns the upcoming stop being approached."""
        if self.is_completed:
            return None
        return self.route.get_segment(self.current_segment_index).to_stop

    def get_state(self) -> MovementState:
        """Returns an immutable snapshot of current movement state."""
        lat = self.current_latitude
        lon = self.current_longitude
        speed = self.current_speed_mps

        if self.enable_noise and self._rng and not self.is_dwelling and not self.is_completed:
            # Small realistic GPS jitter (approx 1-2 meters)
            lat += self._rng.uniform(-0.000015, 0.000015)
            lon += self._rng.uniform(-0.000015, 0.000015)
            speed = max(0.5, speed * self._rng.uniform(0.95, 1.05))

        return MovementState(
            current_latitude=round(lat, 6),
            current_longitude=round(lon, 6),
            current_heading=round(self.current_heading, 1),
            current_speed_mps=round(speed, 2),
            current_segment_index=self.current_segment_index,
            segment_progress_m=round(self.segment_progress_m, 1),
            total_progress_m=round(self.total_progress_m, 1),
            completed_stops_count=self.completed_stops_count,
            is_dwelling=self.is_dwelling,
            dwell_time_remaining_s=round(max(0.0, self.dwell_time_remaining_s), 1),
            is_completed=self.is_completed,
            current_stop=self.current_stop,
            next_stop=self.next_stop,
        )

    def advance(self, delta_sim_seconds: float) -> MovementState:
        """
        Advances the simulated bus position forward by delta_sim_seconds.
        Handles dwell countdowns, segment traversal, and trip completion.
        """
        if delta_sim_seconds < 0:
            raise ValueError(f"delta_sim_seconds cannot be negative, got {delta_sim_seconds}")

        if self.is_completed:
            self.current_speed_mps = 0.0
            return self.get_state()

        remaining_time = delta_sim_seconds

        # 1. Handle Active Dwell at a Stop
        if self.is_dwelling:
            if remaining_time < self.dwell_time_remaining_s:
                self.dwell_time_remaining_s -= remaining_time
                self.current_speed_mps = 0.0
                return self.get_state()
            else:
                # Dwell completed during this tick
                remaining_time -= self.dwell_time_remaining_s
                self.is_dwelling = False
                self.dwell_time_remaining_s = 0.0

                # Advance to next segment
                self.current_segment_index += 1
                self.segment_progress_m = 0.0

                if self.current_segment_index >= self.route.segment_count:
                    # Trip complete
                    self.is_completed = True
                    self.current_speed_mps = 0.0
                    return self.get_state()

        # 2. Advance Movement along Route Segments
        while remaining_time > 0 and not self.is_completed:
            segment = self.route.get_segment(self.current_segment_index)
            dist_remaining_in_segment = segment.distance_m - self.segment_progress_m
            dist_to_advance = self.cruise_speed_mps * remaining_time

            if dist_to_advance < dist_remaining_in_segment:
                # Normal progress along the current segment
                self.segment_progress_m += dist_to_advance
                self.total_progress_m += dist_to_advance
                self.current_speed_mps = self.cruise_speed_mps

                lat, lon, bearing = segment.interpolate(self.segment_progress_m)
                self.current_latitude = lat
                self.current_longitude = lon
                self.current_heading = bearing
                remaining_time = 0.0
            else:
                # Arrived at destination stop of this segment
                time_to_reach_stop = dist_remaining_in_segment / max(0.1, self.cruise_speed_mps)
                remaining_time = max(0.0, remaining_time - time_to_reach_stop)

                self.total_progress_m += dist_remaining_in_segment
                self.segment_progress_m = segment.distance_m
                self.completed_stops_count += 1

                self.current_latitude = segment.to_stop.latitude
                self.current_longitude = segment.to_stop.longitude
                self.current_heading = segment.bearing

                # Check if this is the final stop of the route
                is_last_segment = self.current_segment_index == (self.route.segment_count - 1)
                if is_last_segment:
                    self.is_completed = True
                    self.current_speed_mps = 0.0
                    remaining_time = 0.0
                else:
                    # Intermediate stop: begin dwell period
                    self.is_dwelling = True
                    self.dwell_time_remaining_s = self.dwell_duration_seconds
                    self.current_speed_mps = 0.0

                    # Consume remaining tick time in dwell
                    if remaining_time > 0:
                        if remaining_time < self.dwell_time_remaining_s:
                            self.dwell_time_remaining_s -= remaining_time
                            remaining_time = 0.0
                        else:
                            remaining_time -= self.dwell_time_remaining_s
                            self.is_dwelling = False
                            self.dwell_time_remaining_s = 0.0
                            self.current_segment_index += 1
                            self.segment_progress_m = 0.0

        return self.get_state()
