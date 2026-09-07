from enum import Enum

class ScenarioType(str, Enum):
    NORMAL_OPERATION = "NORMAL_OPERATION"
    DELAY = "DELAY"
    TRACKING_STALE = "TRACKING_STALE"
    RECOVERY = "RECOVERY"
    CROWDING = "CROWDING"
    VEHICLE_OFFLINE_SCHEDULED = "VEHICLE_OFFLINE_SCHEDULED"

class ScenarioEngine:
    def __init__(self, scenario: str):
        self.scenario = ScenarioType(scenario)
        self.state = "INIT"
        self.time_in_state = 0.0

    def get_speed_mps(self, base_speed_mps: float) -> float:
        if self.scenario == ScenarioType.NORMAL_OPERATION:
            return base_speed_mps
        elif self.scenario == ScenarioType.DELAY:
            # Simulate heavy traffic by moving at 20% speed
            return base_speed_mps * 0.2
        elif self.scenario == ScenarioType.CROWDING:
            return base_speed_mps
        elif self.scenario == ScenarioType.TRACKING_STALE:
            return base_speed_mps
        elif self.scenario == ScenarioType.RECOVERY:
            return base_speed_mps
        return base_speed_mps

    def should_send_telemetry(self, elapsed_real_seconds: float) -> bool:
        if self.scenario == ScenarioType.TRACKING_STALE:
            # Stop sending telemetry entirely to trigger stale alert
            return False
        return True

    def update(self, real_delta_seconds: float):
        self.time_in_state += real_delta_seconds
        
        # Scenario transitions could happen here
        if self.scenario == ScenarioType.TRACKING_STALE and self.time_in_state > 130.0:
            # Maybe transition to recovery after 130 seconds of being stale (to trigger the 2 minute backend alert)
            self.scenario = ScenarioType.RECOVERY
            self.time_in_state = 0.0
