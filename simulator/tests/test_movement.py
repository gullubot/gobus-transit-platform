"""
Tests for MovementEngine and physical spatial progression.
"""

import unittest

from simulator.core.movement import MovementEngine
from simulator.core.route import RouteModel, SimulatedStop


class TestMovementEngine(unittest.TestCase):

    def setUp(self):
        # 3 stops along a straight line going North:
        # Stop 1 -> Stop 2 (~1110 meters)
        # Stop 2 -> Stop 3 (~1110 meters)
        self.stop1 = SimulatedStop("s1", "Stop 1", 1, 22.0000, 88.0000, 0.0)
        self.stop2 = SimulatedStop("s2", "Stop 2", 2, 22.0100, 88.0000, 1.11)
        self.stop3 = SimulatedStop("s3", "Stop 3", 3, 22.0200, 88.0000, 2.22)
        self.route = RouteModel("r1", "R1", "Route", [self.stop1, self.stop2, self.stop3])

    def test_initial_state_at_first_stop(self):
        engine = MovementEngine(self.route, cruise_speed_mps=10.0, dwell_duration_seconds=5.0)
        state = engine.get_state()

        self.assertEqual(state.current_latitude, 22.0000)
        self.assertEqual(state.current_longitude, 88.0000)
        self.assertEqual(state.current_segment_index, 0)
        self.assertEqual(state.total_progress_m, 0.0)
        self.assertEqual(state.completed_stops_count, 1)
        self.assertFalse(state.is_dwelling)
        self.assertFalse(state.is_completed)
        self.assertEqual(state.current_stop.stop_id, "s1")
        self.assertEqual(state.next_stop.stop_id, "s2")

    def test_advance_along_segment(self):
        engine = MovementEngine(self.route, cruise_speed_mps=10.0, dwell_duration_seconds=5.0)

        # Advance 10 seconds at 10 m/s = 100 meters
        state = engine.advance(10.0)

        self.assertAlmostEqual(state.segment_progress_m, 100.0, delta=1.0)
        self.assertAlmostEqual(state.total_progress_m, 100.0, delta=1.0)
        self.assertEqual(state.current_speed_mps, 10.0)
        self.assertFalse(state.is_dwelling)
        self.assertFalse(state.is_completed)
        # Lat should have increased northward
        self.assertGreater(state.current_latitude, 22.0000)
        self.assertEqual(state.current_longitude, 88.0000)
        # Heading should be ~0 deg (North)
        self.assertAlmostEqual(state.current_heading, 0.0, delta=1.0)

    def test_arrival_at_stop_and_dwell(self):
        seg0_dist = self.route.get_segment(0).distance_m
        engine = MovementEngine(self.route, cruise_speed_mps=10.0, dwell_duration_seconds=10.0)

        # Advance enough time to reach Stop 2 exactly
        time_to_reach = seg0_dist / 10.0
        state = engine.advance(time_to_reach)

        # Should arrive at Stop 2 and enter dwell
        self.assertEqual(state.completed_stops_count, 2)
        self.assertTrue(state.is_dwelling)
        self.assertEqual(state.current_speed_mps, 0.0)
        self.assertAlmostEqual(state.current_latitude, 22.0100, places=4)
        self.assertEqual(state.current_stop.stop_id, "s2")
        self.assertEqual(state.dwell_time_remaining_s, 10.0)

        # Advance 4 seconds: still dwelling
        state = engine.advance(4.0)
        self.assertTrue(state.is_dwelling)
        self.assertEqual(state.current_speed_mps, 0.0)
        self.assertAlmostEqual(state.dwell_time_remaining_s, 6.0, delta=0.5)

        # Advance 6 seconds: dwell finishes, ready to start segment 1
        state = engine.advance(6.0)
        self.assertFalse(state.is_dwelling)
        self.assertEqual(state.current_segment_index, 1)

    def test_route_completion_at_final_stop(self):
        engine = MovementEngine(self.route, cruise_speed_mps=50.0, dwell_duration_seconds=2.0)

        # Run until completed
        max_ticks = 200
        ticks = 0
        while not engine.is_completed and ticks < max_ticks:
            engine.advance(1.0)
            ticks += 1

        state = engine.get_state()
        self.assertTrue(state.is_completed)
        self.assertEqual(state.current_speed_mps, 0.0)
        self.assertEqual(state.completed_stops_count, 3)
        self.assertAlmostEqual(state.current_latitude, 22.0200, places=4)
        self.assertEqual(state.current_stop.stop_id, "s3")
        self.assertIsNone(state.next_stop)

    def test_deterministic_noise_with_seed(self):
        engine1 = MovementEngine(self.route, cruise_speed_mps=10.0, enable_noise=True, random_seed=999)
        engine2 = MovementEngine(self.route, cruise_speed_mps=10.0, enable_noise=True, random_seed=999)

        state1 = engine1.advance(5.0)
        state2 = engine2.advance(5.0)

        self.assertEqual(state1.current_latitude, state2.current_latitude)
        self.assertEqual(state1.current_longitude, state2.current_longitude)
        self.assertEqual(state1.current_speed_mps, state2.current_speed_mps)


if __name__ == "__main__":
    unittest.main()
