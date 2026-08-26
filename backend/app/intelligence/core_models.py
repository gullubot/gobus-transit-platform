from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple


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


# =================================================================
# PHASE 2: ROUTE MATCHING & DIRECTION
# =================================================================


class Direction(Enum):
    A_TO_B = "A_TO_B"
    B_TO_A = "B_TO_A"
    UNKNOWN = "UNKNOWN"


class RouteMatchStatus(Enum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"


class RouteMatchDiagnostic(Enum):
    MATCHED = "MATCHED"
    LOW_ROUTE_CONFIDENCE = "LOW_ROUTE_CONFIDENCE"
    AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"
    NO_ROUTE_CANDIDATE = "NO_ROUTE_CANDIDATE"
    GPS_TOO_FAR = "GPS_TOO_FAR"
    PROGRESS_INCONSISTENT = "PROGRESS_INCONSISTENT"
    DIRECTION_UNCERTAIN = "DIRECTION_UNCERTAIN"
    PARALLEL_ROUTE_AMBIGUITY = "PARALLEL_ROUTE_AMBIGUITY"


@dataclass
class RouteCandidate:
    route_id: str
    # A LineString segment (exactly 2 points: start and end).
    geometry_coordinates: List[Tuple[float, float]]
    segment_index: int = 0
    segment_progress_start_m: float = 0.0


@dataclass
class RouteMatchContext:
    route_id: str
    segment_index: int
    route_progress_m: float
    direction: Direction
    matched_at: datetime
    confidence: float
    direction_observations: int = 1
    opposite_direction_observations: int = 0


@dataclass
class RouteMatchResult:
    status: RouteMatchStatus
    route_id: Optional[str]
    segment_index: Optional[int]
    projected_lat: Optional[float]
    projected_lon: Optional[float]
    cross_track_distance_m: Optional[float]
    route_progress_m: Optional[float]
    match_confidence: Optional[float]
    direction: Direction
    diagnostic_codes: List[RouteMatchDiagnostic] = field(default_factory=list)
