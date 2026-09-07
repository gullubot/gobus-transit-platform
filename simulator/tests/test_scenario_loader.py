"""
Tests for ScenarioLoader and dry-run validation.
"""

import unittest

from simulator.config.settings import Settings
from simulator.core.bus_simulator import BusConfig
from simulator.core.scenario import ScenarioDefinition, ScenarioEvent, ScenarioEventType
from simulator.core.scenario_loader import build_scenario, validate_scenario


class TestScenarioLoader(unittest.TestCase):

    def setUp(self):
        self.settings = Settings(
            backend_url="http://mock-backend:8000",
            operator_employee_code="O-001",
            operator_password="Password123!",
        )

    def test_build_all_builtin_scenarios(self):
        builtin_names = [
            "normal_single_bus",
            "delay_demo",
            "offline_demo",
            "crowding_demo",
            "service_shortage_demo",
            "multi_bus_demo",
            "full_demo",
        ]
        for name in builtin_names:
            scenario = build_scenario(name, self.settings)
            self.assertIsInstance(scenario, ScenarioDefinition)
            self.assertGreater(len(scenario.buses), 0)
            errors = validate_scenario(scenario)
            self.assertEqual(errors, [], f"Built-in scenario '{name}' failed validation: {errors}")

    def test_dry_run_validation_duplicate_operator_rejected(self):
        # Scenario assigning the SAME operator to two concurrent buses
        b1 = BusConfig("bus-1", "O-001", "p1")
        b2 = BusConfig("bus-2", "O-001", "p2")  # Same employee_code!

        scenario = ScenarioDefinition(
            name="invalid_duplicate_op",
            description="Duplicate operator test",
            buses=[b1, b2],
        )
        errors = validate_scenario(scenario)
        self.assertTrue(any("Duplicate employee_code" in err for err in errors))

    def test_dry_run_validation_unknown_target_bus_rejected(self):
        b1 = BusConfig("bus-1", "O-001", "p1")
        scenario = ScenarioDefinition(
            name="invalid_target",
            description="Unknown bus target",
            buses=[b1],
            events=[
                ScenarioEvent(10.0, ScenarioEventType.SET_SPEED, "bus-99", {"speed_mps": 4.0})
            ],
        )
        errors = validate_scenario(scenario)
        self.assertTrue(any("targets non-existent bus" in err for err in errors))

    def test_dry_run_validation_invalid_crowding_state_rejected(self):
        b1 = BusConfig("bus-1", "O-001", "p1")
        scenario = ScenarioDefinition(
            name="invalid_crowding",
            description="Bad crowding state",
            buses=[b1],
            events=[
                ScenarioEvent(10.0, ScenarioEventType.SET_CROWDING, "bus-1", {"crowding_state": "SUPER_PACKED"})
            ],
        )
        errors = validate_scenario(scenario)
        self.assertTrue(any("invalid" in err.lower() for err in errors))


if __name__ == "__main__":
    unittest.main()
