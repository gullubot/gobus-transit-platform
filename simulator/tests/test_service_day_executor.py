"""
Tests for ServiceDayExecutor and VehicleDutyExecutor.

BUILD 4 Phase 5C: Full-fleet live service-day execution engine, state machines,
sequential duty progression, failure isolation, and live timestamp enforcement.
"""

from datetime import datetime, timezone
import unittest

from simulator.config.settings import Settings
from simulator.service_day.clock import ServiceDayClock
from simulator.service_day.executor import (
    ServiceDayExecutor,
    VehicleDutyExecutor,
    KNOWN_OPERATOR_PASSWORDS,
)
from simulator.service_day.manifest import create_default_manifest
from simulator.service_day.models import (
    ScheduledTrip,
    ServiceDayPlan,
    ServiceDayState,
    TripExecutionState,
    VehicleDuty,
    VehicleOperationalState,
)
from simulator.service_day.planner import ServiceDayPlanner
from simulator.service_day.timestamp_strategy import (
    LiveTimestampStrategy,
    SimulatedTimestampStrategy,
)


class TestServiceDayExecutor(unittest.TestCase):

    def setUp(self):
        self.manifest = create_default_manifest(service_date="2026-09-03")
        self.plan = ServiceDayPlanner.build_plan(self.manifest)
        self.settings = Settings()

    def test_executor_initialization(self):
        executor = ServiceDayExecutor(plan=self.plan, settings=self.settings, dry_run=True)
        self.assertEqual(executor.state, ServiceDayState.DAY_READY)
        self.assertEqual(len(executor.vehicle_executors), 4)
        self.assertFalse(executor.is_completed)

        status = executor.get_status()
        self.assertEqual(status["state"], "DAY_READY")
        self.assertEqual(status["fleet"]["planned"], 4)
        self.assertEqual(status["fleet"]["completed"], 0)
        self.assertEqual(status["trips"]["total"], 7)
        self.assertEqual(status["trips"]["pending"], 7)

    def test_executor_full_day_dry_run_progression(self):
        executor = ServiceDayExecutor(plan=self.plan, settings=self.settings, dry_run=True)
        status = executor.run_live(tick_seconds=0.0)

        self.assertEqual(status["state"], "DAY_COMPLETED")
        self.assertEqual(status["fleet"]["completed"], 4)
        self.assertEqual(status["trips"]["completed"], 7)
        self.assertEqual(status["trips"]["error"], 0)
        self.assertTrue(executor.is_completed)

        # Check vehicle duties
        for ve in executor.vehicle_executors.values():
            self.assertTrue(ve.is_duty_completed)
            self.assertEqual(ve.state, VehicleOperationalState.IDLE)
            self.assertEqual(ve.trips_failed_count, 0)

        # Check individual trips
        for trip in self.plan.trips:
            self.assertEqual(trip.state, TripExecutionState.COMPLETED)
            self.assertIsNotNone(trip.actual_start)
            self.assertIsNotNone(trip.actual_end)
            self.assertGreaterEqual(trip.actual_end, trip.actual_start)

    def test_executor_threshold_limits(self):
        executor = ServiceDayExecutor(plan=self.plan, settings=self.settings, dry_run=True)
        # Run until at least 2 trips complete
        status = executor.run_live(max_trips=2, tick_seconds=0.0)
        self.assertGreaterEqual(status["trips"]["completed"], 2)

    def test_failure_isolation(self):
        """Simulate a trip failure on Vehicle 1; verify sibling vehicles continue."""
        executor = ServiceDayExecutor(plan=self.plan, settings=self.settings, dry_run=True)
        v1_id = "8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e"
        v1_executor = executor.vehicle_executors[v1_id]

        # Force fail trip on Vehicle 1
        t1 = v1_executor.duty.trips[0]
        v1_executor._fail_trip(t1, "Simulated network timeout")

        self.assertEqual(t1.state, TripExecutionState.ERROR)
        self.assertEqual(v1_executor.trips_failed_count, 1)

        # Run remaining day
        status = executor.run_live(tick_seconds=0.0)

        # Vehicle 2, 3, 4 should complete cleanly
        v2_id = "50000000-0000-0000-0000-000000000001"
        self.assertEqual(executor.vehicle_executors[v2_id].trips_failed_count, 0)
        self.assertEqual(executor.vehicle_executors[v2_id].trips_completed_count, 2)
        self.assertEqual(status["trips"]["error"], 1)

    def test_live_timestamp_strategy_enforcement(self):
        """Verify LiveTimestampStrategy strictly emits current UTC timestamps within 5s skew."""
        strategy = LiveTimestampStrategy()
        clock = ServiceDayClock(
            service_date=datetime(2026, 9, 3).date(),
            start_time_of_day="05:30:00",
            time_multiplier=10.0,
        )
        # Advance clock by 3600 simulated seconds (1 hour into simulated future)
        clock.advance(360.0)
        self.assertEqual(clock.time_string, "06:30:00")

        # Telemetry timestamp MUST still be current wall-clock UTC, NOT simulated clock time!
        emitted_ts = strategy.get_telemetry_timestamp(clock)
        now_utc = datetime.now(timezone.utc)
        diff_s = abs((emitted_ts - now_utc).total_seconds())

        self.assertLess(diff_s, 2.0)  # Within 2 seconds of real time
        self.assertNotEqual(emitted_ts.hour, clock.current_simulated_datetime.hour)

    def test_pause_resume_stop_lifecycle(self):
        executor = ServiceDayExecutor(plan=self.plan, settings=self.settings, dry_run=True)
        executor.start()
        self.assertEqual(executor.state, ServiceDayState.DAY_RUNNING)

        executor.pause()
        self.assertEqual(executor.state, ServiceDayState.DAY_PAUSED)

        executor.resume()
        self.assertEqual(executor.state, ServiceDayState.DAY_RUNNING)

        executor.stop()
        self.assertEqual(executor.state, ServiceDayState.DAY_COMPLETED)


if __name__ == "__main__":
    unittest.main()
