"""
Transit Platform — Intelligence Core Configuration
BUILD 3 Phase 1: Prototype configuration for GPS Validation.
"""

from typing import Tuple

# Coarse Geographic Sanity Guard (India Bounding Box)
COARSE_GEO_BOUNDS: Tuple[float, float, float, float] = (
    6.0,
    36.0,
    68.0,
    98.0,
)  # lat_min, lat_max, lon_min, lon_max

# Timestamps
ALLOWED_CLOCK_SKEW_SECONDS = 5.0
HISTORICAL_CLASSIFICATION_HORIZON_SECONDS = 900.0

# Physical Plausibility & Speeds
MAX_IMPOSSIBLE_SPEED_MPS = 50.0  # 180 km/h - Hard safety guard
SUSPICIOUS_SPEED_THRESHOLD_MPS = 33.3  # 120 km/h
MIN_PHYSICAL_DELTA_T_SECONDS = 2.0
MAX_PLAUSIBLE_ACCEL_MPS2 = 4.0

# Speed Consistency
SPEED_CONSISTENCY_MODERATE_MPS = 5.0
SPEED_CONSISTENCY_LARGE_MPS = 15.0
CONTINUITY_SPEED_SCALE = 10.0

# Confidence Component Initial Prototype Weights
WEIGHT_ACCURACY = 0.40
WEIGHT_SPEED = 0.25
WEIGHT_CONTINUITY = 0.20
WEIGHT_TIMESTAMP = 0.15

# Historical Score
HISTORICAL_TIMESTAMP_SCORE = 0.90

# Diagnostic Penalties (Multipliers)
CONFIDENCE_PENALTY_LOW_GPS = 0.80
CONFIDENCE_PENALTY_HIGH_SPEED = 0.60
CONFIDENCE_PENALTY_HIGH_ACCELERATION = 0.65
CONFIDENCE_PENALTY_SPEED_INCONSISTENCY = 0.75

# =================================================================
# PHASE 2: ROUTE MATCHING & DIRECTION
# =================================================================

# Adaptive Search Radius
SEARCH_RADIUS_BASE_M = 50.0
SEARCH_RADIUS_MAX_M = 300.0
SEARCH_RADIUS_ACCURACY_FACTOR = 1.5
SEARCH_RADIUS_SAFETY_MARGIN_M = 20.0

# Candidate Score Weights
ROUTE_WEIGHT_DISTANCE = 0.30
ROUTE_WEIGHT_HEADING = 0.15
ROUTE_WEIGHT_CONTINUITY = 0.25
ROUTE_WEIGHT_PROGRESSION = 0.20
ROUTE_WEIGHT_SPEED = 0.10

# Route Match Thresholds
MIN_ROUTE_MATCH_SCORE = 0.50
MIN_SCORE_MARGIN = 0.10

# Score Scales and Tolerances
ROUTE_DISTANCE_SCALE = 15.0  # Decays relative to max(accuracy, DISTANCE_SCALE)
CONTINUITY_PROGRESS_SCALE = 50.0  # Error scaling for expected progress delta

# Progression / Retrograde Handling
SMALL_RETROGRADE_TOLERANCE_M = 15.0
SMALL_RETROGRADE_SCORE = 0.30

# Direction Engine
DIRECTION_CONFIRMATION_OBSERVATIONS = 3
DIRECTION_MIN_PROGRESS_DELTA = 15.0
