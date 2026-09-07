"""
Tests for ServiceDayPlanner.

BUILD 4 Phase 5B: Deterministic plan construction, sorting, duty chaining, and metrics.
"""

from datetime import datetime
import unittest

from simulator.service_day.manifest import create_default_manifest, ServiceDayManifest
from simulator.service_day.planner import ServiceDayPlanner, PlanValidationError


class TestServiceDayPlanner(unittest.TestCase):

    def test_build_plan_from_default_manifest(self):
        manifest = create_default_manifest(service_date="2026-09-03")
        plan = ServiceDayPlanner.build_plan(manifest)

        self.assertEqual(plan.service_date, "2026-09-03")
        self.assertEqual(len(plan.trips), 7)
        self.assertEqual(len(plan.vehicle_duties), 4)
        self.assertEqual(len(plan.operator_duties), 7)

        # Check deterministic sorting: trips must be sorted by planned_start
        starts = [t.planned_start for t in plan.trips]
        self.assertEqual(starts, sorted(starts))

        # Check vehicle duties
        v1_duty = plan.vehicle_duties["8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e"]
        self.assertEqual(v1_duty.vehicle_number, "WB04-DEMO-001")
        self.assertEqual(v1_duty.trip_count, 3)
        self.assertEqual(v1_duty.first_departure.strftime("%H:%M"), "05:30")
        self.assertEqual(v1_duty.final_arrival.strftime("%H:%M"), "09:20")

        # Check fleet coverage
        self.assertIsNotNone(plan.fleet_coverage)
        self.assertEqual(plan.fleet_coverage.total_vehicles, 4)
        self.assertEqual(plan.fleet_coverage.active_vehicles_with_duties, 4)
        self.assertEqual(plan.fleet_coverage.idle_vehicles_without_duties, 0)
        self.assertEqual(plan.fleet_coverage.max_simultaneous_vehicles, 3)

        # Check service coverage
        self.assertGreaterEqual(len(plan.service_coverages), 3)

    def test_deterministic_sorting_stability(self):
        manifest = create_default_manifest()
        # Reverse trip order in manifest
        manifest.trips.reverse()

        plan = ServiceDayPlanner.build_plan(manifest)
        # The output trips must still be deterministically sorted
        first_trip = plan.trips[0]
        self.assertEqual(first_trip.planned_start.strftime("%H:%M"), "05:30")
        self.assertEqual(first_trip.vehicle_number, "WB04-DEMO-001")
        self.assertEqual(first_trip.operator_code, "O-001")

    def test_plan_serialization_omits_secrets(self):
        manifest = create_default_manifest()
        plan = ServiceDayPlanner.build_plan(manifest)
        plan_dict = plan.to_dict()

        self.assertIn("service_date", plan_dict)
        self.assertIn("vehicle_duties", plan_dict)
        self.assertIn("trips", plan_dict)
        self.assertEqual(len(plan_dict["trips"]), 7)

        # Validate that no secret keys are present in serialization
        serialized_str = str(plan_dict).lower()
        for forbidden in ("password", "jwt", "bearer", "authorization", "secret"):
            self.assertNotIn(forbidden, serialized_str)


if __name__ == "__main__":
    unittest.main()
