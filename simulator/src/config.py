import json
from pydantic import BaseModel, HttpUrl, Field
from typing import List

class ApiConfig(BaseModel):
    base_url: str = "http://localhost:8000"
    timeout_seconds: float = 10.0

class OperatorConfig(BaseModel):
    username: str
    password: str
    direction: str = "A_TO_B"
    scenario: str = "NORMAL_OPERATION"

class SimulationConfig(BaseModel):
    route_code: str = "SD5"
    speed_multiplier: float = 10.0
    telemetry_interval_real_seconds: float = 2.0

class AppConfig(BaseModel):
    api: ApiConfig
    simulation: SimulationConfig
    operators: List[OperatorConfig]

def load_config(path: str) -> AppConfig:
    with open(path, 'r') as f:
        data = json.load(f)
    return AppConfig(**data)
