"""
Transit Platform — Backend Timestamp Strategy.

BUILD 4 Phase 5B: Enforces safe timestamp generation for GoBus telemetry ingestion,
guaranteeing that emitted observations never violate the backend's 5.0s clock skew guard.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from simulator.service_day.clock import ServiceDayClock


class BackendTimestampStrategy(ABC):
    """Abstract strategy for generating telemetry packet observed_at timestamps."""

    @abstractmethod
    def get_telemetry_timestamp(self, clock: ServiceDayClock) -> datetime:
        """Returns the timestamp to attach to an outgoing telemetry packet."""
        pass


class LiveTimestampStrategy(BackendTimestampStrategy):
    """
    Live Operational Timestamp Strategy.

    Always emits current wall-clock UTC timestamps (datetime.now(timezone.utc)),
    strictly satisfying the GoBus backend's ALLOWED_CLOCK_SKEW_SECONDS = 5.0 rule
    regardless of the simulated service-day clock multiplier.
    """

    def get_telemetry_timestamp(self, clock: ServiceDayClock) -> datetime:
        return datetime.now(timezone.utc)


class SimulatedTimestampStrategy(BackendTimestampStrategy):
    """
    Simulated / Dry-Run Timestamp Strategy.

    Emits the simulated clock's current datetime converted to UTC.
    Used for local offline testing, validation, and dry-run execution
    without live backend ingestion.
    """

    def get_telemetry_timestamp(self, clock: ServiceDayClock) -> datetime:
        dt = clock.current_simulated_datetime
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)
