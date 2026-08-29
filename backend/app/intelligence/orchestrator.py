import logging

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.intelligence.core_models import (
    CanonicalStateContext,
    Direction,
    DwellResult,
    DwellState,
    RouteCandidate,
    RouteMatchResult,
    RouteMatchStatus,
    StopProgressResult,
    StopState,
    TelemetryPacket,
    TrackerInput,
    TripInferenceResult,
    ValidationStatus,
)
from app.intelligence.direction import DirectionEngine
from app.intelligence.dwell_detection import DwellEngine
from app.intelligence.eta_engine import ETAEngine
from app.intelligence.gps_validation import GPSValidator
from app.intelligence.route_matching import RouteMatcher
from app.intelligence.stop_progression import StopProgressionEngine
from app.intelligence.tracker_fusion import TrackerFusionEngine
from app.intelligence.trip_inference import TripInferenceEngine
from app.models.enums import TripStatus
from app.models.state import BusCurrentState
from app.models.tracking import TrackingEvent, TrackingSession
from app.models.trip import Trip
from app.repositories.historical_eta import HistoricalETARepository
from app.repositories.route_spatial import get_candidate_segments_query
from app.repositories.state_repository import upsert_canonical_state

logger = logging.getLogger(__name__)

class IntelligenceOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.eta_repo = HistoricalETARepository(db)

        self.gps_validator = GPSValidator()
        self.route_matcher = RouteMatcher()
        self.direction_engine = DirectionEngine()
        self.stop_engine = StopProgressionEngine()
        self.dwell_engine = DwellEngine()
        self.trip_engine = TripInferenceEngine()
        self.eta_engine = ETAEngine(self.eta_repo)

    def process_telemetry_batch(self, session: TrackingSession, events: list[TrackingEvent]):
        """
        Processes a batch of accepted telemetry events in chronological order.
        """
        if not events:
            return

        events = sorted(events, key=lambda e: e.observed_at)

        trip = None
        route_stops = None
        vehicle_id = None
        if session.trip_id:
            trip = self.db.get(Trip, session.trip_id)
            if trip:
                vehicle_id = trip.vehicle_id
                if trip.route_id:
                    route_stops = self._get_route_stops(trip.route_id)

        canonical_ctx = CanonicalStateContext(vehicle_id=str(vehicle_id) if vehicle_id else "")
        if vehicle_id:
            row = self.db.execute(select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)).scalar_one_or_none()
            if row:
                canonical_ctx.vehicle_id = str(row.vehicle_id)
                canonical_ctx.trip_id = str(row.trip_id) if row.trip_id else None
                canonical_ctx.route_id = str(row.route_id) if row.route_id else None
                canonical_ctx.direction = row.direction
                canonical_ctx.lat = row.latitude
                canonical_ctx.lon = row.longitude
                canonical_ctx.speed_mps = row.speed
                canonical_ctx.heading = row.heading
                canonical_ctx.route_progress_m = row.route_progress
                canonical_ctx.current_stop_id = str(row.current_stop_id) if row.current_stop_id else None
                canonical_ctx.next_stop_id = str(row.next_stop_id) if row.next_stop_id else None
                if row.dwell_state:
                    try:
                        canonical_ctx.dwell_state = DwellState(row.dwell_state)
                    except ValueError:
                        pass
                canonical_ctx.last_observed_at = row.last_observed_at
                canonical_ctx.last_received_at = row.last_received_at
                if row.state:
                    from app.intelligence.core_models import CanonicalState
                    try:
                        canonical_ctx.state = CanonicalState(row.state)
                    except ValueError:
                        pass
                if row.confidence:
                    canonical_ctx.confidence = row.confidence.value

        # Deserialization from DB
        from app.intelligence.serialization import deserialize_contexts, serialize_contexts
        
        trip_ctx, stop_ctx, dwell_ctx, dir_ctx, trackers = None, None, None, None, {}
        if vehicle_id and 'row' in locals() and row and row.engine_contexts:
            trip_ctx, stop_ctx, dwell_ctx, dir_ctx, trackers = deserialize_contexts(
                row.engine_contexts, str(session.trip_id) if session.trip_id else ""
            )
            
        canonical_ctx.trackers = trackers
        rm_ctx = None  # rm_ctx is transient per observation, dir_ctx holds RouteMatchContext for direction hysteresis

        for event in events:
            packet = TelemetryPacket(
                lat=float(event.latitude) if event.latitude is not None else 0.0,
                lon=float(event.longitude) if event.longitude is not None else 0.0,
                accuracy_m=float(event.accuracy_m) if getattr(event, 'accuracy_m', None) is not None else None,
                speed_mps=float(event.speed_mps) if getattr(event, 'speed_mps', None) is not None else None,
                heading=float(event.heading) if event.heading is not None else None,
                observed_at=event.observed_at
            )

            # 1. GPS Validation
            gps_report = self.gps_validator.validate_packet(packet, event.received_at)

            # 2. Route Matching
            route_match = RouteMatchResult(
                status=RouteMatchStatus.NO_MATCH,
                route_id=None,
                segment_index=None,
                projected_lat=None,
                projected_lon=None,
                cross_track_distance_m=None,
                route_progress_m=None,
                match_confidence=None,
                direction=Direction.UNKNOWN
            )
            if gps_report.status == ValidationStatus.VALID and trip and trip.route_id:
                route_topology = self._get_route_topology(packet.lat, packet.lon, 200.0)
                # Fallback to dir_ctx (from previous batch) if rm_ctx is None (first packet in batch)
                prev_rm_ctx = rm_ctx if rm_ctx is not None else dir_ctx
                route_match = self.route_matcher.match_route(packet, route_topology, prev_rm_ctx)

            # 3. Direction
            direction = Direction.UNKNOWN
            if route_match.status == RouteMatchStatus.MATCHED:
                dir_tuple = self.direction_engine.infer_direction_state(
                    route_match.route_progress_m,
                    dir_ctx
                )
                if dir_tuple:
                    direction, dir_obs, opp_obs = dir_tuple
                    
                    # Update dir_ctx for temporal continuity
                    from app.intelligence.core_models import RouteMatchContext
                    dir_ctx = RouteMatchContext(
                        route_id=route_match.route_id,
                        segment_index=route_match.segment_index,
                        route_progress_m=route_match.route_progress_m,
                        direction=direction,
                        matched_at=packet.observed_at,
                        confidence=route_match.match_confidence or 0.0,
                        direction_observations=dir_obs,
                        opposite_direction_observations=opp_obs
                    )

            # 4. Stop Progression
            stop_progress = StopProgressResult(
                state=StopState.BEFORE_STOP,
                current_stop_id=None,
                next_stop_id=None,
                previous_stop_id=None,
                route_progress_m=None,
                progression_confidence=0.0
            )
            if route_match.status == RouteMatchStatus.MATCHED and route_stops:
                if stop_ctx is None:
                    from app.intelligence.core_models import StopProgressContext
                    stop_ctx = StopProgressContext()
                # RouteMatchResult does not reflect the dynamically updated direction from DirectionEngine
                # We should update it if StopProgression needs it, but signature expects `match`.
                route_match.direction = direction
                stop_progress = self.stop_engine.evaluate_progression(
                    packet, route_match, route_stops, stop_ctx
                )

            # 5. Dwell Detection
            dwell = DwellResult(
                state=DwellState.UNKNOWN,
                duration_seconds=0.0,
                confidence=0.0,
                associated_stop_id=None
            )
            if gps_report.status == ValidationStatus.VALID:
                if dwell_ctx is None:
                    from app.intelligence.core_models import DwellContext
                    dwell_ctx = DwellContext()
                dwell = self.dwell_engine.evaluate_dwell(packet, stop_progress, dwell_ctx)

            # 6. Trip Inference
            trip_result = TripInferenceResult(status=TripStatus.PLANNED, score=0.0, context=None, diagnostics=[])
            if trip:
                if trip_ctx is None:
                    from app.intelligence.core_models import TripInferenceContext
                    trip_ctx = TripInferenceContext(trip_id=str(trip.id), status=trip.status.value)
                auth_dir = Direction(trip.direction) if trip.direction else None

                tracking_loss_duration_sec = 0.0
                if trip_ctx and trip_ctx.score_timestamp:
                    tracking_loss_duration_sec = max(0.0, (packet.observed_at - trip_ctx.score_timestamp).total_seconds())

                trip_result = self.trip_engine.evaluate(
                    packet=packet,
                    session_status=session.status,
                    assigned_trip_id=str(session.trip_id),
                    planned_start_at=trip.planned_start_at,
                    route_match=route_match,
                    direction=direction,
                    stop_progress=stop_progress,
                    dwell=dwell,
                    context=trip_ctx,
                    authoritative_trip_direction=auth_dir,
                    tracking_loss_duration_sec=tracking_loss_duration_sec
                )
                if trip_result.context:
                    trip_ctx = trip_result.context
                    if trip.status != trip_result.status:
                        trip.status = trip_result.status
                        if trip.status == TripStatus.ACTIVE:
                            trip.actual_start_at = packet.observed_at

            # 7. Tracker Fusion -> Canonical State
            tracker_input = TrackerInput(
                packet_id=event.packet_id,
                source_id=str(session.device_id),
                lat=packet.lat,
                lon=packet.lon,
                accuracy_m=packet.accuracy_m,
                speed_mps=packet.speed_mps,
                heading=packet.heading,
                observed_at=packet.observed_at,
                received_at=event.received_at,
                session_health=1.0,
                gps_validation=gps_report,
                route_match=route_match,
                stop_progression=stop_progress,
                dwell_result=dwell,
                trip_inference=trip_result
            )
            canonical_ctx, _ = TrackerFusionEngine.process_tracker_input(
                canonical_ctx, tracker_input, event.received_at
            )

            if vehicle_id:
                canonical_ctx.vehicle_id = str(vehicle_id)
            canonical_ctx.organization_id = str(trip.organization_id) if trip else None
            canonical_ctx.trip_id = str(session.trip_id) if session.trip_id else None
            canonical_ctx.route_id = str(trip.route_id) if trip else None
            canonical_ctx.direction = trip.direction if trip else None
            canonical_ctx.trip_status = trip.status.value if trip else None

            # 8. ETA
            if canonical_ctx.route_id and route_stops and canonical_ctx.next_stop_id:
                eta = self.eta_engine.calculate_eta(
                    canonical=canonical_ctx,
                    route_stops=route_stops,
                    target_stop_id=canonical_ctx.next_stop_id,
                    total_route_distance=route_stops[-1].distance_from_start if route_stops else 0.0,
                    time_of_day_bucket="MORNING",
                    day_of_week=0,
                    now=event.received_at
                )
                if not hasattr(canonical_ctx, 'eta_seconds'):
                    canonical_ctx.eta_seconds = 0
                if not hasattr(canonical_ctx, 'eta_status'):
                    canonical_ctx.eta_status = "UNKNOWN"

                canonical_ctx.eta_seconds = eta.eta_seconds
                canonical_ctx.eta_status = eta.status.value

        # Serialize intermediate engine states before saving to DB
        canonical_ctx.engine_contexts = serialize_contexts(
            trip_ctx, stop_ctx, dwell_ctx, dir_ctx, canonical_ctx.trackers
        )

        if vehicle_id:
            upsert_canonical_state(self.db, canonical_ctx)
        self.db.commit()

    def _get_route_topology(self, lat: float, lon: float, search_radius_m: float) -> list[RouteCandidate]:
        from app.intelligence.core_models import RouteCandidate
        query = text(get_candidate_segments_query())
        result = self.db.execute(query, {"lon": lon, "lat": lat, "search_radius_m": search_radius_m})
        candidates = []
        for row in result:
            candidates.append(RouteCandidate(
                route_id=str(row.route_id),
                geometry_coordinates=[(row.start_lat, row.start_lon), (row.end_lat, row.end_lon)],
                segment_index=row.segment_index,
                segment_progress_start_m=float(row.segment_progress_start_m) if row.segment_progress_start_m is not None else 0.0
            ))
        return candidates

    def _get_route_stops(self, route_id: str):
        from app.intelligence.core_models import RouteStop as CoreRouteStop
        from app.models.route import RouteStop as DBRouteStop
        from app.models.route import Stop
        stmt = (
            select(DBRouteStop, Stop)
            .join(Stop, DBRouteStop.stop_id == Stop.id)
            .where(DBRouteStop.route_id == route_id)
            .order_by(DBRouteStop.sequence_number)
        )
        result = self.db.execute(stmt).all()
        stops = []
        for rs, stop in result:
            stops.append(CoreRouteStop(
                id=str(stop.id),
                sequence_number=rs.sequence_number,
                distance_from_start=float(rs.distance_from_start) if rs.distance_from_start is not None else 0.0,
                nominal_travel_time_seconds=60,
                lat=float(stop.latitude) if stop.latitude is not None else 0.0,
                lon=float(stop.longitude) if stop.longitude is not None else 0.0
            ))
        return stops
