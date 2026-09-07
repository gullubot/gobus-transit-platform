"""
Tests for RouteModel and RouteSegment.
"""

import unittest

from simulator.core.route import RouteModel, RouteSegment, SimulatedStop


class TestRouteModel(unittest.TestCase):

    def setUp(self):
        self.stop1 = SimulatedStop("s1", "Stop 1", 1, 22.5000, 88.3000, 0.0)
        self.stop2 = SimulatedStop("s2", "Stop 2", 2, 22.5100, 88.3000, 1.1)
        self.stop3 = SimulatedStop("s3", "Stop 3", 3, 22.5200, 88.3000, 2.2)

    def test_valid_route_construction(self):
        route = RouteModel(
            route_id="r-100",
            route_code="SD5",
            route_name="Route SD5",
            stops=[self.stop1, self.stop2, self.stop3],
            direction="A_TO_B",
        )
        self.assertEqual(route.stop_count, 3)
        self.assertEqual(route.segment_count, 2)
        self.assertGreater(route.total_distance_m, 2000.0)

        # Check segments
        seg0 = route.get_segment(0)
        self.assertEqual(seg0.from_stop.stop_id, "s1")
        self.assertEqual(seg0.to_stop.stop_id, "s2")
        self.assertAlmostEqual(seg0.bearing, 0.0, delta=1.0)  # North

        seg1 = route.get_segment(1)
        self.assertEqual(seg1.from_stop.stop_id, "s2")
        self.assertEqual(seg1.to_stop.stop_id, "s3")

    def test_rejection_fewer_than_two_stops(self):
        with self.assertRaises(ValueError):
            RouteModel("r1", "R1", "Route", [self.stop1])

    def test_rejection_invalid_coordinates(self):
        bad_stop = SimulatedStop("sb", "Bad Stop", 2, 95.0, 88.0)
        with self.assertRaises(ValueError):
            RouteModel("r1", "R1", "Route", [self.stop1, bad_stop])

        bad_lon = SimulatedStop("sb2", "Bad Lon", 2, 22.0, 195.0)
        with self.assertRaises(ValueError):
            RouteModel("r1", "R1", "Route", [self.stop1, bad_lon])

    def test_segment_interpolation(self):
        route = RouteModel("r1", "R1", "Route", [self.stop1, self.stop2])
        seg = route.get_segment(0)

        # Progress 0
        lat, lon, b = seg.interpolate(0.0)
        self.assertAlmostEqual(lat, 22.5000)
        self.assertAlmostEqual(lon, 88.3000)

        # Progress half
        lat, lon, b = seg.interpolate(seg.distance_m / 2.0)
        self.assertAlmostEqual(lat, 22.5050)
        self.assertAlmostEqual(lon, 88.3000)

        # Progress full
        lat, lon, b = seg.interpolate(seg.distance_m)
        self.assertAlmostEqual(lat, 22.5100)
        self.assertAlmostEqual(lon, 88.3000)


if __name__ == "__main__":
    unittest.main()
