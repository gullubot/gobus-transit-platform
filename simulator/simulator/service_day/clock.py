"""
Transit Platform — Service-Day Simulation Clock.

BUILD 4 Phase 5B: Dedicated scheduling clock managing simulated service-day time,
acceleration multipliers, and deterministic progression independently of backend timestamps.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo


class ServiceDayClock:
    """
    Simulation scheduling clock for a full operating day.

    Separates simulated service-day time from real-world telemetry event timestamps,
    ensuring that high-speed or accelerated scheduling never violates backend
    future timestamp guards.
    """

    def __init__(
        self,
        service_date: date,
        start_time_of_day: str = "05:00:00",
        timezone_name: str = "Asia/Kolkata",
        time_multiplier: float = 1.0,
    ):
        self.service_date = service_date
        self.timezone_name = timezone_name
        try:
            self.tz = ZoneInfo(timezone_name)
        except Exception:
            self.tz = timezone.utc

        # Parse start time
        parts = [int(p) for p in start_time_of_day.split(":")]
        hour = parts[0]
        minute = parts[1] if len(parts) > 1 else 0
        second = parts[2] if len(parts) > 2 else 0

        self.start_datetime = datetime(
            self.service_date.year,
            self.service_date.month,
            self.service_date.day,
            hour,
            minute,
            second,
            tzinfo=self.tz,
        )

        self.current_simulated_datetime = self.start_datetime
        self.elapsed_service_seconds: float = 0.0
        self.time_multiplier = max(0.1, float(time_multiplier))
        self.paused: bool = False
        self.completed: bool = False

    def advance(self, real_delta_seconds: float) -> float:
        """
        Advances the service-day clock by real_delta_seconds * time_multiplier.
        Returns the simulated seconds advanced.
        """
        if self.paused or self.completed:
            return 0.0

        sim_delta = real_delta_seconds * self.time_multiplier
        self.elapsed_service_seconds += sim_delta
        self.current_simulated_datetime += timedelta(seconds=sim_delta)
        return sim_delta

    def set_multiplier(self, multiplier: float) -> None:
        """Adjusts the time acceleration multiplier."""
        self.time_multiplier = max(0.1, float(multiplier))

    def pause(self) -> None:
        """Pauses clock progression."""
        self.paused = True

    def resume(self) -> None:
        """Resumes clock progression."""
        self.paused = False

    def mark_completed(self) -> None:
        """Marks the service day as finished."""
        self.completed = True

    def reset(self) -> None:
        """Resets clock to initial start datetime."""
        self.current_simulated_datetime = self.start_datetime
        self.elapsed_service_seconds = 0.0
        self.paused = False
        self.completed = False

    @property
    def time_string(self) -> str:
        """Formatted current simulated time string (HH:MM:SS)."""
        return self.current_simulated_datetime.strftime("%H:%M:%S")

    @property
    def isoformat(self) -> str:
        """ISO 8601 string of current simulated datetime."""
        return self.current_simulated_datetime.isoformat()
