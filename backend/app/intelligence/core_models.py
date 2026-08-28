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


# =================================================================
# PHASE 3: STOP PROGRESSION & DWELL DETECTION
# =================================================================


class StopState(Enum):
    BEFORE_STOP = "BEFORE_STOP"
    AT_STOP = "AT_STOP"
    PASSED_STOP = "PASSED_STOP"
    UNKNOWN = "UNKNOWN"


class DwellState(Enum):
    MOVING = "MOVING"
    DWELL_AT_STOP = "DWELL_AT_STOP"
    DWELL_NON_STOP = "DWELL_NON_STOP"
    UNKNOWN = "UNKNOWN"


@dataclass
class RouteStop:
    id: str
    sequence_number: int
    distance_from_start: float
    nominal_travel_time_seconds: int
    lat: float
    lon: float


@dataclass
class StopProgressContext:
    # Maps stop_id to its state
    stop_states: dict[str, StopState] = field(default_factory=dict)
    current_stop_id: Optional[str] = None
    next_stop_id: Optional[str] = None
    previous_stop_id: Optional[str] = None


@dataclass
class StopProgressResult:
    state: StopState
    current_stop_id: Optional[str]
    next_stop_id: Optional[str]
    previous_stop_id: Optional[str]
    route_progress_m: Optional[float]
    progression_confidence: float
    diagnostic_codes: List[str] = field(default_factory=list)


@dataclass
class DwellContext:
    stationary_since: Optional[datetime] = None
    last_moving_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    previous_dwell_state: DwellState = DwellState.UNKNOWN
    associated_stop_id: Optional[str] = None
    consecutive_movement_observations: int = 0
    previous_route_progress_m: Optional[float] = None


@dataclass
class DwellResult:
    state: DwellState
    duration_seconds: float
    associated_stop_id: Optional[str]
    confidence: float
    diagnostic_codes: List[str] = field(default_factory=list)


# =================================================================
# PHASE 4: TRIP INFERENCE & SCHEDULE ALIGNMENT
# =================================================================


class TripInferenceDiagnostic(Enum):
    SCHEDULE_WINDOW_MATCH = "SCHEDULE_WINDOW_MATCH"
    ORIGIN_PROXIMITY = "ORIGIN_PROXIMITY"
    MOVEMENT_CONFIRMED = "MOVEMENT_CONFIRMED"
    ROUTE_PROGRESSION_CONFIRMED = "ROUTE_PROGRESSION_CONFIRMED"
    DIRECTION_CONFIRMED = "DIRECTION_CONFIRMED"
    REPEATED_EVIDENCE = "REPEATED_EVIDENCE"
    PERSISTENT_OFF_ROUTE = "PERSISTENT_OFF_ROUTE"
    POSSIBLE_WRONG_TRIP = "POSSIBLE_WRONG_TRIP"
    ASSIGNMENT_MISMATCH = "ASSIGNMENT_MISMATCH"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    NO_ACTIVE_TRACKING_SESSION = "NO_ACTIVE_TRACKING_SESSION"
    TRACKING_LOST = "TRACKING_LOST"
    RECOVERY_OBSERVED = "RECOVERY_OBSERVED"
    AMBIGUOUS_SCHEDULE_MATCH = "AMBIGUOUS_SCHEDULE_MATCH"


@dataclass
class TripInferenceContext:
    trip_id: str
    status: str  # TripStatus value
    score: float = 0.0
    score_timestamp: Optional[datetime] = None
    suspected_start_at: Optional[datetime] = None
    last_route_evidence_progress_m: Optional[float] = None
    route_evidence_contribution: float = 0.0
    stop_evidence_contribution: float = 0.0
    tracking_lost_since: Optional[datetime] = None

    @property
    def is_tracking_lost(self) -> bool:
        return self.tracking_lost_since is not None


@dataclass
class TripInferenceResult:
    status: str  # TripStatus value
    score: float
    context: TripInferenceContext
    diagnostics: List[TripInferenceDiagnostic] = field(default_factory=list)


# =================================================================
# PHASE 5: TRACKER FUSION & CANONICAL BUS STATE
# =================================================================


class CanonicalState(Enum):
    NOT_ACTIVE = "NOT_ACTIVE"
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    OFFLINE = "OFFLINE"


class TrackerFusionDiagnostic(Enum):
    STALE_DATA = "STALE_DATA"
    OFFLINE = "OFFLINE"
    LOW_RELIABILITY = "LOW_RELIABILITY"
    DUPLICATE_PACKET = "DUPLICATE_PACKET"
    HISTORICAL_PACKET = "HISTORICAL_PACKET"
    MODERATE_DISAGREEMENT = "MODERATE_DISAGREEMENT"
    LARGE_DISAGREEMENT = "LARGE_DISAGREEMENT"
    IMPOSSIBLE_RECOVERY_SPEED = "IMPOSSIBLE_RECOVERY_SPEED"
    SOURCE_SWITCH_HYSTERESIS_ACTIVE = "SOURCE_SWITCH_HYSTERESIS_ACTIVE"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"


@dataclass
class TrackerInput:
    source_id: str
    packet_id: str
    observed_at: datetime
    received_at: datetime
    lat: float
    lon: float
    accuracy_m: Optional[float]
    speed_mps: Optional[float]
    heading: Optional[float]
    gps_validation: ValidationReport
    route_match: RouteMatchResult
    stop_progression: StopProgressResult
    dwell_result: DwellResult
    trip_inference: TripInferenceResult
    session_health: float  # [0, 1]


@dataclass
class TrackerState:
    # State for a single tracker
    source_id: str
    last_packet_id: Optional[str] = None
    last_observed_at: Optional[datetime] = None
    last_reliability: float = 0.0
    consecutive_valid_observations: int = 0
    consecutive_recovery_observations: int = 0
    is_trusted: bool = False


@dataclass
class CanonicalStateContext:
    vehicle_id: str
    organization_id: Optional[str] = None
    trip_id: Optional[str] = None
    service_id: Optional[str] = None
    route_id: Optional[str] = None
    direction: Optional[str] = None

    canonical_source: Optional[str] = None
    last_observed_at: Optional[datetime] = None
    last_received_at: Optional[datetime] = None

    lat: Optional[float] = None
    lon: Optional[float] = None
    speed_mps: Optional[float] = None
    heading: Optional[float] = None

    route_progress_m: Optional[float] = None
    current_stop_id: Optional[str] = None
    next_stop_id: Optional[str] = None
    dwell_state: DwellState = DwellState.UNKNOWN

    state: CanonicalState = CanonicalState.OFFLINE
    confidence: str = "LOW"  # string representing Confidence enum

    # Internal fusion state
    trackers: dict[str, TrackerState] = field(default_factory=dict)
    recovery_mode_active: bool = False
    consecutive_source_switch_observations: int = 0
    candidate_source_id: Optional[str] = None


# =================================================================
# PHASE 6: ETA ENGINE
# =================================================================


class ETAStatus(Enum):
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    FALLBACK = "FALLBACK"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class ETAResult:
    target_stop_id: str
    eta_seconds: int
    lower_bound_seconds: int
    upper_bound_seconds: int
    confidence_score: float
    status: ETAStatus
    fallback_level: int
    reason_codes: List[str] = field(default_factory=list)
    generated_at: Optional[datetime] = None
    source_observed_at: Optional[datetime] = None
