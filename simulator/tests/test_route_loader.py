"""
Tests for route loader API adapter.
"""

import unittest
from unittest.mock import MagicMock

from simulator.api.route import fetch_service_route
from simulator.core.exceptions import SimulatorError


class TestRouteLoader(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()

    def test_fetch_service_route_a_to_b(self):
        self.mock_client.get.return_value = {
            "id": "srv-1",
            "service_code": "AC4B",
            "service_name": "AC4B Service",
            "route_id": "rt-1",
            "route_code": "SD5",
            "route_name": "Howrah to Salt Lake",
            "stops": [
                {
                    "stop_id": "st-2",
                    "stop_name": "Esplanade",
                    "sequence_number": 2,
                    "latitude": 22.5645,
                    "longitude": 88.3518,
                    "distance_from_start": 2.5,
                },
                {
                    "stop_id": "st-1",
                    "stop_name": "Howrah Station",
                    "sequence_number": 1,
                    "latitude": 22.5855,
                    "longitude": 88.3426,
                    "distance_from_start": 0.0,
                },
                {
                    "stop_id": "st-3",
                    "stop_name": "Salt Lake Karunamoyee",
                    "sequence_number": 3,
                    "latitude": 22.5867,
                    "longitude": 88.4178,
                    "distance_from_start": 9.2,
                },
            ],
        }

        route = fetch_service_route(
            self.mock_client,
            service_id="srv-1",
            organization_id="org-1",
            direction="A_TO_B",
        )

        self.mock_client.get.assert_called_once_with(
            "/api/passenger/services/srv-1",
            params={"organization_id": "org-1"}
        )
        self.assertEqual(route.route_code, "SD5")
        self.assertEqual(route.stop_count, 3)
        # Verify sorted ascending sequence
        self.assertEqual(route.stops[0].stop_id, "st-1")
        self.assertEqual(route.stops[1].stop_id, "st-2")
        self.assertEqual(route.stops[2].stop_id, "st-3")

    def test_fetch_service_route_b_to_a_reversed(self):
        self.mock_client.get.return_value = {
            "route_id": "rt-1",
            "route_code": "SD5",
            "route_name": "Howrah to Salt Lake",
            "stops": [
                {"stop_id": "st-1", "stop_name": "Stop 1", "sequence_number": 1, "latitude": 22.5, "longitude": 88.3},
                {"stop_id": "st-2", "stop_name": "Stop 2", "sequence_number": 2, "latitude": 22.6, "longitude": 88.4},
            ],
        }

        route = fetch_service_route(
            self.mock_client,
            service_id="srv-1",
            organization_id="org-1",
            direction="B_TO_A",
        )

        # Reversed order: Stop 2 first, then Stop 1
        self.assertEqual(route.stops[0].stop_id, "st-2")
        self.assertEqual(route.stops[1].stop_id, "st-1")
        self.assertEqual(route.direction, "B_TO_A")

    def test_insufficient_stops_raises_simulator_error(self):
        self.mock_client.get.return_value = {
            "route_id": "rt-1",
            "stops": [{"stop_id": "st-1", "sequence_number": 1, "latitude": 22.5, "longitude": 88.3}],
        }

        with self.assertRaises(SimulatorError):
            fetch_service_route(self.mock_client, "srv-1", "org-1")


if __name__ == "__main__":
    unittest.main()
