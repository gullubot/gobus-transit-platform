"""
Transit Platform — Deterministic Simulation Clock.

Maintains independent simulated time progression with configurable speed multipliers.
Does not rely on wall-clock sleep inside calculations, ensuring complete testability.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


class SimulationClock:
    """
    Deterministic clock for simulating vehicle time independently from real time.
    """

    def __init__(
        self,
        start_time: Optional[datetime] = None,
        time_multiplier: float = 1.0,
    ):
        if time_multiplier <= 0:
            raise ValueError(f"time_multiplier must be > 0, got {time_multiplier}")

        self.time_multiplier = float(time_multiplier)
        self._initial_time = (
            start_time if start_time is not None else datetime.now(timezone.utc)
        )
        if self._initial_time.tzinfo is None:
            self._initial_time = self._initial_time.replace(tzinfo=timezone.utc)

        self._current_sim_time = self._initial_time
        self.elapsed_sim_seconds: float = 0.0
        self.elapsed_real_seconds: float = 0.0
        self.is_paused: bool = False

    @property
    def current_time(self) -> datetime:
        """Current simulated UTC timestamp."""
        return self._current_sim_time

    def tick(self, delta_real_seconds: float) -> datetime:
        """
        Advances the simulation clock by real elapsed seconds multiplied by time_multiplier.
        Returns the new simulated datetime.
        """
        if delta_real_seconds < 0:
            raise ValueError(f"delta_real_seconds cannot be negative, got {delta_real_seconds}")

        if self.is_paused:
            return self._current_sim_time

        delta_sim = delta_real_seconds * self.time_multiplier
        self.elapsed_real_seconds += delta_real_seconds
        self.elapsed_sim_seconds += delta_sim
        self._current_sim_time += timedelta(seconds=delta_sim)
        return self._current_sim_time

    def pause(self) -> None:
        """Pauses clock progression."""
        self.is_paused = True

    def resume(self) -> None:
        """Resumes clock progression."""
        self.is_paused = False

    def reset(self, new_start_time: Optional[datetime] = None) -> None:
        """Resets clock to initial or new starting time."""
        if new_start_time is not None:
            self._initial_time = new_start_time
            if self._initial_time.tzinfo is None:
                self._initial_time = self._initial_time.replace(tzinfo=timezone.utc)

        self._current_sim_time = self._initial_time
        self.elapsed_sim_seconds = 0.0
        self.elapsed_real_seconds = 0.0
        self.is_paused = False

    def __repr__(self) -> str:
        return (
            f"SimulationClock(current={self._current_sim_time.isoformat()}, "
            f"multiplier={self.time_multiplier}x, elapsed_sim_s={self.elapsed_sim_seconds:.1f}, "
            f"paused={self.is_paused})"
        )
