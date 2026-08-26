from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class ValidationStatus(Enum):
    VALID = "VALID"
    SUSPICIOUS = "SUSPICIOUS"
    REJECTED = "REJECTED"


class ValidationDiagnostic(Enum):
    COARSE_OUT_OF_BOUNDS = "COARSE_OUT_OF_BOUNDS"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    IMPOSSIBLE_SPEED = "IMPOSSIBLE_SPEED"
    HIGH_IMPLIED_SPEED = "HIGH_IMPLIED_SPEED"
    HIGH_IMPLIED_ACCELERATION = "HIGH_IMPLIED_ACCELERATION"
    LOW_GPS_CONFIDENCE = "LOW_GPS_CONFIDENCE"
    SPEED_INCONSISTENCY = "SPEED_INCONSISTENCY"


@dataclass
class TelemetryPacket:
    lat: float
    lon: float
    observed_at: datetime
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    heading: Optional[float] = None


@dataclass
class PreviousStateContext:
    lat: float
    lon: float
    observed_at: datetime
    speed_mps: Optional[float] = None
    heading: Optional[float] = None
    route_progress: Optional[float] = None


@dataclass
class ValidationReport:
    status: ValidationStatus
    confidence_score: Optional[float]
    is_historical: bool
    diagnostic_codes: List[ValidationDiagnostic] = field(default_factory=list)
