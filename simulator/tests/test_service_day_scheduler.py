"""
Tests for ServiceDayScheduler.

BUILD 4 Phase 5B: Dry-run execution, failure isolation, sequential vehicle reuse,
and status telemetry metrics.
"""

import unittest

from simulator.service_day.manifest import create_default_manifest
from simulator.service_day.models import (
    ServiceDayState,
    TripExecutionState,
    VehicleOperationalState,
)
from simulator.service_day.planner import ServiceDayPlanner
from simulator.service_day.scheduler import ServiceDayScheduler


class TestServiceDayScheduler(unittest.TestCase):

    def test_scheduler_initialization(self):
        manifest = create_default_manifest()
        plan = ServiceDayPlanner.build_plan(manifest)
        scheduler = ServiceDayScheduler(plan=plan, dry_run=True)

        self.assertEqual(scheduler.plan.state, ServiceDayState.DAY_READY)
        self.assertFalse(scheduler.is_completed)
        status = scheduler.get_status()
        self.assertEqual(status["state"], "DAY_READY")
        self.assertEqual(status["trips_total"], 7)
        self.assertEqual(status["trips_pending"], 7)
        self.assertEqual(status["trips_completed"], 0)

    def test_scheduler_dry_run_execution(self):
        manifest = create_default_manifest()
        plan = ServiceDayPlanner.build_plan(manifest)
        scheduler = ServiceDayScheduler(plan=plan, dry_run=True)

        results = scheduler.run_dry_run_full_day(step_seconds=60.0)
        self.assertEqual(results["status"], "COMPLETED")
        self.assertEqual(results["completed_trips"], 7)
        self.assertEqual(results["failed_trips"], 0)
        self.assertTrue(scheduler.is_completed)
        self.assertEqual(scheduler.plan.state, ServiceDayState.DAY_COMPLETED)

        # Verify that all trips transitioned to COMPLETED
        for trip in plan.trips:
            self.assertEqual(trip.state, TripExecutionState.COMPLETED)
            self.assertIsNotNone(trip.actual_start)
            self.assertIsNotNone(trip.actual_end)

        # Verify that all vehicles finished their duties and transitioned to IDLE
        for duty in plan.vehicle_duties.values():
            self.assertEqual(duty.state, VehicleOperationalState.IDLE)

    def test_scheduler_pause_resume(self):
        manifest = create_default_manifest()
        plan = ServiceDayPlanner.build_plan(manifest)
        scheduler = ServiceDayScheduler(plan=plan, dry_run=True)

        scheduler.start()
        self.assertEqual(scheduler.plan.state, ServiceDayState.DAY_RUNNING)

        scheduler.pause()
        self.assertEqual(scheduler.plan.state, ServiceDayState.DAY_PAUSED)
        self.assertTrue(scheduler.clock.paused)

        scheduler.resume()
        self.assertEqual(scheduler.plan.state, ServiceDayState.DAY_RUNNING)
        self.assertFalse(scheduler.clock.paused)

        scheduler.stop()
        self.assertEqual(scheduler.plan.state, ServiceDayState.DAY_COMPLETED)


if __name__ == "__main__":
    unittest.main()
