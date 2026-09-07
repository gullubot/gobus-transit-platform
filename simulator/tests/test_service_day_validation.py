"""
Tests for ServiceDayPlanner Validation Rules.

BUILD 4 Phase 5B: Strict verification of duplicate IDs, vehicle duty overlaps,
and operator single simultaneous assignment enforcement.
"""

import unittest

from simulator.service_day.manifest import ServiceDayManifest
from simulator.service_day.planner import ServiceDayPlanner, PlanValidationError


class TestServiceDayValidation(unittest.TestCase):

    def test_validation_rejects_duplicate_trip_id(self):
        manifest = ServiceDayManifest(
            service_date="2026-09-03",
            timezone="Asia/Kolkata",
            vehicles=[{"vehicle_id": "v1", "vehicle_number": "BUS-1"}],
            operators=[
                {"operator_code": "O-1"},
                {"operator_code": "O-2"},
            ],
            trips=[
                {
                    "trip_id": "duplicate_id",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "v1",
                    "operator_code": "O-1",
                    "direction": "A_TO_B",
                    "planned_start": "2026-09-03T06:00:00+05:30",
                },
                {
                    "trip_id": "duplicate_id",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "v1",
                    "operator_code": "O-2",
                    "direction": "B_TO_A",
                    "planned_start": "2026-09-03T07:00:00+05:30",
                },
            ],
        )
        with self.assertRaises(PlanValidationError) as ctx:
            ServiceDayPlanner.build_plan(manifest)
        self.assertTrue(any("Duplicate trip_id 'duplicate_id'" in err for err in ctx.exception.errors))

    def test_validation_rejects_unconfigured_vehicle_and_operator(self):
        manifest = ServiceDayManifest(
            service_date="2026-09-03",
            timezone="Asia/Kolkata",
            vehicles=[{"vehicle_id": "v1", "vehicle_number": "BUS-1"}],
            operators=[{"operator_code": "O-1"}],
            trips=[
                {
                    "trip_id": "t1",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "non_existent_vehicle",
                    "operator_code": "non_existent_op",
                    "direction": "A_TO_B",
                    "planned_start": "2026-09-03T06:00:00+05:30",
                }
            ],
        )
        with self.assertRaises(PlanValidationError) as ctx:
            ServiceDayPlanner.build_plan(manifest)
        errs = " ".join(ctx.exception.errors)
        self.assertIn("unconfigured vehicle_id 'non_existent_vehicle'", errs)
        self.assertIn("unconfigured operator_code 'non_existent_op'", errs)

    def test_validation_rejects_overlapping_vehicle_trips(self):
        manifest = ServiceDayManifest(
            service_date="2026-09-03",
            timezone="Asia/Kolkata",
            vehicles=[{"vehicle_id": "v1", "vehicle_number": "BUS-1"}],
            operators=[
                {"operator_code": "O-1"},
                {"operator_code": "O-2"},
            ],
            trips=[
                {
                    "trip_id": "t1",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "v1",
                    "operator_code": "O-1",
                    "direction": "A_TO_B",
                    "planned_start": "2026-09-03T06:00:00+05:30",
                    "planned_end": "2026-09-03T07:15:00+05:30",
                },
                {
                    "trip_id": "t2",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "v1",
                    "operator_code": "O-2",
                    "direction": "B_TO_A",
                    "planned_start": "2026-09-03T07:00:00+05:30",  # Overlaps before 07:15!
                    "planned_end": "2026-09-03T08:00:00+05:30",
                },
            ],
        )
        with self.assertRaises(PlanValidationError) as ctx:
            ServiceDayPlanner.build_plan(manifest)
        self.assertTrue(any("Overlapping vehicle duty on vehicle" in err for err in ctx.exception.errors))

    def test_validation_rejects_single_operator_simultaneous_assignment(self):
        manifest = ServiceDayManifest(
            service_date="2026-09-03",
            timezone="Asia/Kolkata",
            vehicles=[
                {"vehicle_id": "v1", "vehicle_number": "BUS-1"},
                {"vehicle_id": "v2", "vehicle_number": "BUS-2"},
            ],
            operators=[{"operator_code": "O-001", "operator_name": "Shared Driver"}],
            trips=[
                {
                    "trip_id": "trip_bus1",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "v1",
                    "operator_code": "O-001",  # O-001 on Bus 1
                    "direction": "A_TO_B",
                    "planned_start": "2026-09-03T06:00:00+05:30",
                    "planned_end": "2026-09-03T07:00:00+05:30",
                },
                {
                    "trip_id": "trip_bus2",
                    "service_id": "s1",
                    "route_id": "r1",
                    "vehicle_id": "v2",
                    "operator_code": "O-001",  # O-001 simultaneously on Bus 2!
                    "direction": "A_TO_B",
                    "planned_start": "2026-09-03T06:30:00+05:30",  # Conflict!
                    "planned_end": "2026-09-03T07:30:00+05:30",
                },
            ],
        )
        with self.assertRaises(PlanValidationError) as ctx:
            ServiceDayPlanner.build_plan(manifest)
        self.assertTrue(any("Operator assignment conflict for operator 'O-001'" in err for err in ctx.exception.errors))


if __name__ == "__main__":
    unittest.main()
