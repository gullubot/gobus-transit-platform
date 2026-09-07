"""
Tests for ScenarioDefinition and ScenarioEvent models.
"""

import unittest

from simulator.core.bus_simulator import BusConfig
from simulator.core.scenario import ScenarioDefinition, ScenarioEvent, ScenarioEventType


class TestScenario(unittest.TestCase):

    def test_scenario_chronological_sorting(self):
        b = BusConfig("b1", "O-001", "p1")
        e3 = ScenarioEvent(60.0, ScenarioEventType.RESTORE_SPEED, "b1")
        e1 = ScenarioEvent(10.0, ScenarioEventType.START_BUS, "b1")
        e2 = ScenarioEvent(30.0, ScenarioEventType.SET_SPEED, "b1", {"speed_mps": 3.0})

        scenario = ScenarioDefinition(
            name="test_scenario",
            description="Testing chronological sorting",
            buses=[b],
            events=[e3, e1, e2],
        )

        self.assertEqual(scenario.events[0].sim_time_offset_s, 10.0)
        self.assertEqual(scenario.events[1].sim_time_offset_s, 30.0)
        self.assertEqual(scenario.events[2].sim_time_offset_s, 60.0)

    def test_negative_time_offset_rejected(self):
        with self.assertRaises(ValueError):
            ScenarioEvent(-5.0, ScenarioEventType.START_BUS, "b1")

    def test_empty_buses_rejected(self):
        with self.assertRaises(ValueError):
            ScenarioDefinition("empty", "No buses", buses=[])


if __name__ == "__main__":
    unittest.main()
