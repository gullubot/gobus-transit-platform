"""
Tests for geographic math utilities (Haversine, forward bearing, interpolation).
"""

import math
import unittest

from simulator.core.geo import calculate_bearing, haversine_distance, interpolate_point


class TestGeo(unittest.TestCase):

    def test_haversine_distance_zero(self):
        dist = haversine_distance(22.572646, 88.363895, 22.572646, 88.363895)
        self.assertAlmostEqual(dist, 0.0, places=1)

    def test_haversine_distance_known_points(self):
        # Howrah Station (22.5855, 88.3426) to Esplanade (22.5645, 88.3518) ~2.5 km
        dist = haversine_distance(22.5855, 88.3426, 22.5645, 88.3518)
        self.assertGreater(dist, 2000.0)
        self.assertLess(dist, 3500.0)

    def test_calculate_bearing_cardinals(self):
        # Due North: lat increases, lon constant -> 0 deg
        b_north = calculate_bearing(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(b_north, 0.0, delta=0.5)

        # Due East: lat constant, lon increases -> 90 deg
        b_east = calculate_bearing(0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(b_east, 90.0, delta=0.5)

        # Due South: lat decreases, lon constant -> 180 deg
        b_south = calculate_bearing(1.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(b_south, 180.0, delta=0.5)

        # Due West: lat constant, lon decreases -> 270 deg
        b_west = calculate_bearing(0.0, 1.0, 0.0, 0.0)
        self.assertAlmostEqual(b_west, 270.0, delta=0.5)

    def test_bearing_normalization(self):
        # Any bearing must satisfy 0 <= bearing < 360
        b = calculate_bearing(22.57, 88.36, 22.58, 88.35)
        self.assertGreaterEqual(b, 0.0)
        self.assertLess(b, 360.0)

    def test_interpolate_point(self):
        lat1, lon1 = 10.0, 20.0
        lat2, lon2 = 20.0, 40.0

        # Fraction 0.0 -> start
        lat, lon = interpolate_point(lat1, lon1, lat2, lon2, 0.0)
        self.assertAlmostEqual(lat, lat1)
        self.assertAlmostEqual(lon, lon1)

        # Fraction 1.0 -> end
        lat, lon = interpolate_point(lat1, lon1, lat2, lon2, 1.0)
        self.assertAlmostEqual(lat, lat2)
        self.assertAlmostEqual(lon, lon2)

        # Fraction 0.5 -> midpoint
        lat, lon = interpolate_point(lat1, lon1, lat2, lon2, 0.5)
        self.assertAlmostEqual(lat, 15.0)
        self.assertAlmostEqual(lon, 30.0)


if __name__ == "__main__":
    unittest.main()
