import uuid
from datetime import datetime, timezone, timedelta, date, time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session, selectinload, aliased

from app.db.session import get_db
from app.intelligence.crowding_engine import CrowdingEngine
from app.models.state import BusCurrentState
from app.models.trip import Trip
from app.models.organization import Organization
from app.models.route import Stop, StopAlias, Route, RouteStop
from app.models.service import Service, ServiceSchedule
from app.models.enums import Direction, TripStatus
from app.services.fare_service import FareCalculationService, FareCalculationError
from app.schemas.passenger import (
    PassengerCityResponse,
    PassengerDepartureResponse,
    PassengerPlanTripResponse,
    PassengerLiveBusResponse,
    PassengerServiceSearchResponse,
    PassengerServiceSearchNearestBus,
    PassengerVehicleStateResponse,
    PassengerOrganizationResponse,
    PassengerStopResponse,
    PassengerServiceSummaryResponse,
    PassengerServiceDetailResponse,
    RouteStopDetail,
    ServiceScheduleDetail,
)

router = APIRouter(tags=["passenger"])


def _resolve_org_ids(
    db: Session,
    city: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
) -> list[uuid.UUID]:
    if city and city.strip():
        clean_city = city.strip()
        stmt = select(Organization.id).where(
            Organization.status == "ACTIVE",
            or_(
                func.lower(Organization.city) == clean_city.lower(),
                func.lower(func.replace(Organization.city, " ", "_")) == clean_city.lower(),
            ),
        )
        org_ids = db.execute(stmt).scalars().all()
        if org_ids:
            return list(org_ids)
    if organization_id:
        return [organization_id]
    all_orgs = db.execute(
        select(Organization.id).where(Organization.status == "ACTIVE")
    ).scalars().all()
    return list(all_orgs)


@router.get("/api/passenger/cities", response_model=list[PassengerCityResponse])
def list_cities(
    db: Annotated[Session, Depends(get_db)],
) -> list[PassengerCityResponse]:
    rows = db.execute(
        select(Organization.city)
        .where(Organization.status == "ACTIVE")
        .distinct()
    ).scalars().all()

    cities = []
    seen = set()
    for c in rows:
        if c and c.strip():
            city_name = c.strip()
            city_id = city_name.lower().replace(" ", "_")
            if city_id not in seen:
                seen.add(city_id)
                cities.append(PassengerCityResponse(id=city_id, name=city_name))
    return cities


@router.get("/api/passenger/organizations", response_model=list[PassengerOrganizationResponse])
def list_organizations(
    db: Annotated[Session, Depends(get_db)],
) -> list[PassengerOrganizationResponse]:
    rows = db.execute(select(Organization).where(Organization.status == "ACTIVE")).scalars().all()
    return [PassengerOrganizationResponse(id=str(r.id), name=r.name) for r in rows]


@router.get("/api/passenger/stops", response_model=list[PassengerStopResponse])
def list_stops(
    db: Annotated[Session, Depends(get_db)],
    city: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    search: Optional[str] = None,
) -> list[PassengerStopResponse]:
    org_ids = _resolve_org_ids(db, city, organization_id)
    if not org_ids:
        return []

    stmt = (
        select(Stop)
        .options(selectinload(Stop.aliases))
        .where(Stop.organization_id.in_(org_ids), Stop.status == "ACTIVE")
    )
    if search and search.strip():
        clean_search = search.strip()
        stmt = (
            stmt.outerjoin(StopAlias, Stop.id == StopAlias.stop_id)
            .where(
                or_(
                    Stop.name.ilike(f"%{clean_search}%"),
                    StopAlias.alias_name.ilike(f"%{clean_search}%"),
                )
            )
            .distinct()
        )

    rows = db.execute(stmt).scalars().all()
    return [
        PassengerStopResponse(
            id=str(r.id),
            organization_id=str(r.organization_id),
            stop_code=r.stop_code,
            name=r.name,
            latitude=r.latitude,
            longitude=r.longitude,
            aliases=[a.alias_name for a in r.aliases] if hasattr(r, "aliases") and r.aliases else [],
        )
        for r in rows
    ]


@router.get("/api/passenger/services", response_model=list[PassengerServiceSummaryResponse])
def list_services(
    db: Annotated[Session, Depends(get_db)],
    city: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
) -> list[PassengerServiceSummaryResponse]:
    org_ids = _resolve_org_ids(db, city, organization_id)
    if not org_ids:
        return []
    stmt = select(Service).where(
        Service.organization_id.in_(org_ids), Service.status == "ACTIVE"
    )
    rows = db.execute(stmt).scalars().all()
    return [
        PassengerServiceSummaryResponse(
            id=str(r.id),
            organization_id=str(r.organization_id),
            service_code=r.service_code,
            service_name=r.service_name,
            route_id=str(r.route_id),
        )
        for r in rows
    ]


def _format_relative_wait(wait_seconds: Optional[int], is_live: bool) -> Optional[str]:
    if wait_seconds is None:
        return None
    mins = max(0, int(round(wait_seconds / 60)))
    if is_live:
        if mins <= 1:
            return "Arriving in 1 min"
        return f"Arriving in {mins} min"
    else:
        if mins <= 1:
            return "Starts in 1 min"
        elif mins < 60:
            return f"Starts in {mins} min"
        else:
            hrs = mins // 60
            rem = mins % 60
            if rem == 0:
                return f"Departs in {hrs} hr"
            return f"Departs in {hrs} hr {rem} min"


def _compute_travel_time(
    stops: list[RouteStop], current_seq: int, direction: Direction
) -> int | None:
    sorted_stops = sorted(stops, key=lambda x: x.sequence_number)
    if not sorted_stops:
        return None

    if any(s.nominal_travel_time_seconds is None for s in sorted_stops):
        return None

    try:
        current_stop = next(s for s in sorted_stops if s.sequence_number == current_seq)
    except StopIteration:
        return None

    if direction == Direction.A_TO_B:
        first_time = sorted_stops[0].nominal_travel_time_seconds or 0
        return max(0, (current_stop.nominal_travel_time_seconds or 0) - first_time)
    else:
        last_time = sorted_stops[-1].nominal_travel_time_seconds or 0
        return max(0, last_time - (current_stop.nominal_travel_time_seconds or 0))


def _get_next_scheduled_arrival(
    schedule: ServiceSchedule, travel_time_sec: int, ref_time: datetime
) -> datetime | None:
    ref_date = ref_time.date()
    start_dt = datetime.combine(ref_date, schedule.start_time).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(ref_date, schedule.end_time).replace(tzinfo=timezone.utc)

    if schedule.end_time < schedule.start_time:
        end_dt += timedelta(days=1)

    interval = timedelta(minutes=max(1, schedule.typical_interval_minutes))

    candidate = start_dt
    while candidate <= end_dt:
        arr_time = candidate + timedelta(seconds=travel_time_sec)
        if arr_time >= ref_time:
            return arr_time
        candidate += interval

    return None


@router.get("/api/passenger/services/search", response_model=list[PassengerServiceSearchResponse])
def search_services(
    origin_id: uuid.UUID,
    destination_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    city: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    search_date: Optional[date] = None,
    search_time: Optional[time] = None,
    sort_by: Optional[str] = "BEST_MATCH",
    filter_by: Optional[str] = "ALL",
) -> list[PassengerServiceSearchResponse]:
    if origin_id == destination_id:
        return []

    org_ids = _resolve_org_ids(db, city, organization_id)
    if not org_ids:
        return []

    orig_stop = db.execute(
        select(Stop).where(Stop.id == origin_id, Stop.organization_id.in_(org_ids))
    ).scalar_one_or_none()
    dest_stop = db.execute(
        select(Stop).where(Stop.id == destination_id, Stop.organization_id.in_(org_ids))
    ).scalar_one_or_none()

    if not orig_stop or not dest_stop:
        return []

    now = datetime.now(timezone.utc)
    target_date = search_date if search_date is not None else now.date()
    is_today = (target_date == now.date())

    if search_time is not None:
        target_time = search_time
    else:
        target_time = now.time() if is_today else time(0, 0, 0)

    search_dt = datetime.combine(target_date, target_time).replace(tzinfo=timezone.utc)

    # 1. Structural routing query
    RS_orig = aliased(RouteStop)
    RS_dest = aliased(RouteStop)

    stmt = (
        select(Service, RS_orig.sequence_number, RS_dest.sequence_number)
        .join(Route, Service.route_id == Route.id)
        .join(RS_orig, Route.id == RS_orig.route_id)
        .join(RS_dest, Route.id == RS_dest.route_id)
        .options(
            selectinload(Service.service_schedules),
            selectinload(Service.route).selectinload(Route.route_stops).selectinload(RouteStop.stop),
        )
        .where(
            Service.organization_id.in_(org_ids),
            Service.status == "ACTIVE",
            RS_orig.stop_id == origin_id,
            RS_dest.stop_id == destination_id,
            RS_orig.sequence_number != RS_dest.sequence_number,
        )
    )

    results = db.execute(stmt).all()
    if not results:
        return []

    ten_mins_ago = now - timedelta(minutes=10)
    candidates: list[PassengerServiceSearchResponse] = []

    for srv, orig_seq, dest_seq in results:
        req_direction = Direction.A_TO_B if orig_seq < dest_seq else Direction.B_TO_A

        route_stops = sorted(srv.route.route_stops, key=lambda s: s.sequence_number)
        if not route_stops:
            continue

        # Absolute route endpoints
        if req_direction == Direction.A_TO_B:
            abs_origin = route_stops[0].stop.name if route_stops[0].stop else orig_stop.name
            abs_dest = route_stops[-1].stop.name if route_stops[-1].stop else dest_stop.name
        else:
            abs_origin = route_stops[-1].stop.name if route_stops[-1].stop else orig_stop.name
            abs_dest = route_stops[0].stop.name if route_stops[0].stop else dest_stop.name

        stops_count = abs(dest_seq - orig_seq)

        # Authoritative segment travel time
        travel_time_orig = _compute_travel_time(route_stops, orig_seq, req_direction)
        travel_time_dest = _compute_travel_time(route_stops, dest_seq, req_direction)

        if travel_time_orig is not None and travel_time_dest is not None:
            segment_duration = abs(travel_time_dest - travel_time_orig)
        else:
            segment_duration = max(180, stops_count * 180)

        if segment_duration <= 0:
            segment_duration = max(180, stops_count * 180)

        # Check live buses ONLY if is_today
        nearest_bus = None
        active_qualifying_buses = []

        if is_today:
            bus_stmt = select(BusCurrentState).where(
                BusCurrentState.service_id == srv.id,
                BusCurrentState.direction == req_direction,
                BusCurrentState.state.notin_(["OFFLINE", "STALE"]),
                BusCurrentState.last_observed_at >= ten_mins_ago,
            )
            raw_buses = db.execute(bus_stmt).scalars().all()

            for b in raw_buses:
                if b.trip_id:
                    t = db.get(Trip, b.trip_id)
                    if t and t.status.value in ("COMPLETED", "ABANDONED", "CANCELLED"):
                        continue

                # Check if bus has passed passenger origin
                passed_origin = False
                if b.next_stop_id:
                    next_rs = next((s for s in route_stops if str(s.stop_id) == str(b.next_stop_id)), None)
                    if next_rs:
                        if req_direction == Direction.A_TO_B and next_rs.sequence_number > orig_seq:
                            passed_origin = True
                        elif req_direction == Direction.B_TO_A and next_rs.sequence_number < orig_seq:
                            passed_origin = True

                if not passed_origin:
                    active_qualifying_buses.append(b)

            if active_qualifying_buses:
                def bus_sort_key(b):
                    if b.eta_seconds is not None and b.eta_status != "UNAVAILABLE":
                        if b.next_stop_id and travel_time_orig is not None:
                            next_rs = next((s for s in route_stops if str(s.stop_id) == str(b.next_stop_id)), None)
                            if next_rs:
                                tt_next = _compute_travel_time(route_stops, next_rs.sequence_number, req_direction) or 0
                                return max(0, b.eta_seconds + (travel_time_orig - tt_next))
                        return b.eta_seconds
                    return 999999

                sorted_buses = sorted(active_qualifying_buses, key=bus_sort_key)
                best = sorted_buses[0]

                c_resp = None
                try:
                    c_resp = CrowdingEngine.aggregate_vehicle_crowding(db, best.vehicle_id)
                except Exception:
                    pass

                c_level = c_resp.state.value if c_resp else "UNKNOWN"
                if c_level == "FULL":
                    c_level = "HIGH"

                eta_to_origin = None
                if best.eta_seconds is not None and best.eta_status != "UNAVAILABLE":
                    if best.next_stop_id and travel_time_orig is not None:
                        next_rs = next((s for s in route_stops if str(s.stop_id) == str(best.next_stop_id)), None)
                        if next_rs:
                            tt_next = _compute_travel_time(route_stops, next_rs.sequence_number, req_direction) or 0
                            eta_to_origin = max(0, best.eta_seconds + (travel_time_orig - tt_next))
                    if eta_to_origin is None:
                        eta_to_origin = best.eta_seconds

                nearest_bus = PassengerServiceSearchNearestBus(
                    vehicle_id=str(best.vehicle_id),
                    eta_seconds=eta_to_origin,
                    eta_status=best.eta_status,
                    crowd_level=c_level,
                )

        # Fare calculation
        fare_val: Optional[float] = None
        if srv.fare_configuration_id:
            try:
                fare_dict = FareCalculationService.calculate_fare(
                    db=db,
                    organization_id=srv.organization_id,
                    service_id=srv.id,
                    origin_stop_id=origin_id,
                    destination_stop_id=destination_id,
                )
                fare_val = float(fare_dict["fare_amount"])
            except Exception:
                fare_val = None

        # AC detection
        service_code_str = srv.service_code or ""
        service_name_str = srv.service_name or ""
        is_ac = ("AC" in service_code_str.upper() or "AC" in service_name_str.upper())
        service_type = "AC" if is_ac else "NON_AC"

        # Determine Availability, Departure, and Arrival
        if is_today and nearest_bus and nearest_bus.eta_seconds is not None:
            # LIVE mode
            dep_ts = now + timedelta(seconds=nearest_bus.eta_seconds)
            exp_arr_ts = dep_ts + timedelta(seconds=segment_duration)
            rel_sec = nearest_bus.eta_seconds
            rel_msg = _format_relative_wait(rel_sec, is_live=True)

            candidates.append(
                PassengerServiceSearchResponse(
                    service_id=str(srv.id),
                    service_name=srv.service_name,
                    service_code=srv.service_code,
                    route_id=str(srv.route_id),
                    direction=req_direction.value,
                    availability_mode="LIVE",
                    departure_mode="LIVE_DEPARTURE",
                    arrival_mode="LIVE_ETA",
                    departure_timestamp=dep_ts,
                    arrival_timestamp=exp_arr_ts,
                    expected_arrival_timestamp=exp_arr_ts,
                    relative_wait_seconds=rel_sec,
                    relative_message=rel_msg,
                    journey_duration_seconds=segment_duration,
                    fare=fare_val,
                    is_direct=True,
                    is_ac=is_ac,
                    service_type=service_type,
                    absolute_origin=abs_origin,
                    absolute_destination=abs_dest,
                    searched_origin=orig_stop.name,
                    searched_destination=dest_stop.name,
                    stops_count=stops_count,
                    active_buses_count=len(active_qualifying_buses),
                    nearest_bus=nearest_bus,
                )
            )
        else:
            # SCHEDULED candidate search: find next scheduled departure >= search_dt
            candidate_departures: list[datetime] = []

            # 1. From Trip records on target_date
            trip_stmt = select(Trip).where(
                Trip.service_id == srv.id,
                Trip.direction == req_direction,
                Trip.operating_date == target_date,
                Trip.status.in_([TripStatus.PLANNED, TripStatus.ACTIVE]),
            )
            planned_trips = db.execute(trip_stmt).scalars().all()
            for pt in planned_trips:
                if pt.planned_start_at:
                    pt_dep = pt.planned_start_at + timedelta(seconds=(travel_time_orig or 0))
                    if pt_dep.tzinfo is None:
                        pt_dep = pt_dep.replace(tzinfo=timezone.utc)
                    if pt_dep >= search_dt:
                        candidate_departures.append(pt_dep)

            # 2. From ServiceSchedules
            for sch in srv.service_schedules:
                if sch.direction != req_direction or sch.status != "ACTIVE":
                    continue
                if sch.days_of_week is not None and target_date.weekday() not in sch.days_of_week and target_date.isoweekday() not in sch.days_of_week:
                    continue
                if sch.effective_from and target_date < sch.effective_from:
                    continue
                if sch.effective_until and target_date > sch.effective_until:
                    continue

                tt_orig = travel_time_orig or 0
                sch_dep = _get_next_scheduled_arrival(sch, tt_orig, search_dt)
                if sch_dep:
                    candidate_departures.append(sch_dep)

            if candidate_departures:
                earliest_dep = min(candidate_departures)
                exp_arr = earliest_dep + timedelta(seconds=segment_duration)
                rel_sec = max(0, int((earliest_dep - search_dt).total_seconds()))
                rel_msg = _format_relative_wait(rel_sec, is_live=False)

                candidates.append(
                    PassengerServiceSearchResponse(
                        service_id=str(srv.id),
                        service_name=srv.service_name,
                        service_code=srv.service_code,
                        route_id=str(srv.route_id),
                        direction=req_direction.value,
                        availability_mode="SCHEDULED",
                        departure_mode="SCHEDULED_DEPARTURE",
                        arrival_mode="SCHEDULED_ARRIVAL",
                        departure_timestamp=earliest_dep,
                        arrival_timestamp=exp_arr,
                        expected_arrival_timestamp=exp_arr,
                        relative_wait_seconds=rel_sec,
                        relative_message=rel_msg,
                        journey_duration_seconds=segment_duration,
                        fare=fare_val,
                        is_direct=True,
                        is_ac=is_ac,
                        service_type=service_type,
                        absolute_origin=abs_origin,
                        absolute_destination=abs_dest,
                        searched_origin=orig_stop.name,
                        searched_destination=dest_stop.name,
                        stops_count=stops_count,
                        active_buses_count=0,
                        nearest_bus=None,
                    )
                )
            else:
                # No upcoming departures for requested date/time
                candidates.append(
                    PassengerServiceSearchResponse(
                        service_id=str(srv.id),
                        service_name=srv.service_name,
                        service_code=srv.service_code,
                        route_id=str(srv.route_id),
                        direction=req_direction.value,
                        availability_mode="UNAVAILABLE",
                        departure_mode="SCHEDULED_DEPARTURE",
                        arrival_mode="SCHEDULED_ARRIVAL",
                        departure_timestamp=None,
                        arrival_timestamp=None,
                        expected_arrival_timestamp=None,
                        relative_wait_seconds=None,
                        relative_message=None,
                        journey_duration_seconds=segment_duration,
                        fare=fare_val,
                        is_direct=True,
                        is_ac=is_ac,
                        service_type=service_type,
                        absolute_origin=abs_origin,
                        absolute_destination=abs_dest,
                        searched_origin=orig_stop.name,
                        searched_destination=dest_stop.name,
                        stops_count=stops_count,
                        active_buses_count=0,
                        nearest_bus=None,
                    )
                )

    # Multi-factor scoring for available candidates
    avail_candidates = [c for c in candidates if c.availability_mode != "UNAVAILABLE"]
    if avail_candidates:
        arr_timestamps = [c.expected_arrival_timestamp.timestamp() for c in avail_candidates if c.expected_arrival_timestamp]
        min_arr = min(arr_timestamps) if arr_timestamps else 0.0
        max_arr = max(arr_timestamps) if arr_timestamps else 0.0

        durations = [c.journey_duration_seconds or 600 for c in avail_candidates]
        min_dur = min(durations)
        max_dur = max(durations)

        fares = [c.fare for c in avail_candidates if c.fare is not None]
        min_fare = min(fares) if fares else 0.0
        max_fare = max(fares) if fares else 0.0

        for c in avail_candidates:
            if c.expected_arrival_timestamp and max_arr > min_arr:
                arr_score = (max_arr - c.expected_arrival_timestamp.timestamp()) / (max_arr - min_arr)
            else:
                arr_score = 1.0

            if max_dur > min_dur:
                dur_score = (max_dur - (c.journey_duration_seconds or 600)) / (max_dur - min_dur)
            else:
                dur_score = 1.0

            if c.fare is not None and max_fare > min_fare:
                fare_score = (max_fare - c.fare) / (max_fare - min_fare)
            else:
                fare_score = 0.5

            direct_score = 1.0 if c.is_direct else 0.5
            live_bonus = 0.05 if c.availability_mode == "LIVE" else 0.0

            c.ranking_score = round(
                0.45 * arr_score + 0.30 * dur_score + 0.15 * fare_score + 0.10 * direct_score + live_bonus,
                4,
            )

    # Apply filter_by
    filtered_list = candidates
    if filter_by:
        f_upper = filter_by.upper().strip()
        if f_upper == "AC":
            filtered_list = [c for c in filtered_list if c.is_ac]
        elif f_upper == "NON_AC":
            filtered_list = [c for c in filtered_list if not c.is_ac]
        elif f_upper == "DIRECT":
            filtered_list = [c for c in filtered_list if c.is_direct]

    # Apply sort_by
    s_upper = (sort_by or "BEST_MATCH").upper().strip()
    far_future = datetime.max.replace(tzinfo=timezone.utc)

    if s_upper == "LOWEST_PRICE":
        filtered_list.sort(key=lambda c: (
            0 if c.availability_mode != "UNAVAILABLE" else 1,
            c.fare is None,
            c.fare if c.fare is not None else 999999,
            -(c.ranking_score or 0),
            c.service_id,
        ))
    elif s_upper == "QUICKEST":
        filtered_list.sort(key=lambda c: (
            0 if c.availability_mode != "UNAVAILABLE" else 1,
            c.journey_duration_seconds if c.journey_duration_seconds is not None else 999999,
            c.expected_arrival_timestamp if c.expected_arrival_timestamp is not None else far_future,
            c.service_id,
        ))
    elif s_upper == "EARLIEST_DEPARTURE":
        filtered_list.sort(key=lambda c: (
            0 if c.availability_mode != "UNAVAILABLE" else 1,
            c.departure_timestamp is None,
            c.departure_timestamp if c.departure_timestamp is not None else far_future,
            c.service_id,
        ))
    else:  # BEST_MATCH
        filtered_list.sort(key=lambda c: (
            0 if c.availability_mode != "UNAVAILABLE" else 1,
            -(c.ranking_score or 0),
            c.expected_arrival_timestamp if c.expected_arrival_timestamp is not None else far_future,
            c.journey_duration_seconds if c.journey_duration_seconds is not None else 999999,
            c.fare if c.fare is not None else 999999,
            c.departure_timestamp if c.departure_timestamp is not None else far_future,
            c.service_id,
        ))

    return filtered_list


@router.get("/api/passenger/services/{service_id}", response_model=PassengerServiceDetailResponse)
def get_service_details(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    city: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
) -> PassengerServiceDetailResponse:
    stmt = (
        select(Service)
        .options(
            selectinload(Service.route).selectinload(Route.route_stops).selectinload(RouteStop.stop),
            selectinload(Service.service_schedules),
        )
        .where(Service.id == service_id)
    )
    if organization_id:
        stmt = stmt.where(Service.organization_id == organization_id)
    elif city:
        org_ids = _resolve_org_ids(db, city=city)
        if org_ids:
            stmt = stmt.where(Service.organization_id.in_(org_ids))

    service = db.execute(stmt).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or organization mismatch")

    route = service.route
    if not route:
        raise HTTPException(status_code=404, detail="Route not found for service")

    # Sort route stops by sequence
    sorted_stops = sorted(route.route_stops, key=lambda rs: rs.sequence_number)

    stops_detail = [
        RouteStopDetail(
            stop_id=str(rs.stop_id),
            stop_name=rs.stop.name,
            sequence_number=rs.sequence_number,
            latitude=rs.stop.latitude,
            longitude=rs.stop.longitude,
            distance_from_start=rs.distance_from_start,
            nominal_travel_time_seconds=rs.nominal_travel_time_seconds,
        )
        for rs in sorted_stops
    ]

    import json
    geojson_str = db.execute(select(func.ST_AsGeoJSON(Route.geometry)).where(Route.id == route.id)).scalar()
    route_geometry = json.loads(geojson_str) if geojson_str else None

    schedules_detail = [
        ServiceScheduleDetail(
            direction=sch.direction.value,
            start_time=sch.start_time.strftime("%H:%M:%S"),
            end_time=sch.end_time.strftime("%H:%M:%S"),
            typical_interval_minutes=sch.typical_interval_minutes,
            days_of_week=sch.days_of_week,
        )
        for sch in service.service_schedules
    ]

    return PassengerServiceDetailResponse(
        id=str(service.id),
        organization_id=str(service.organization_id),
        service_code=service.service_code,
        service_name=service.service_name,
        route_id=str(route.id),
        route_code=route.route_code,
        route_name=route.route_name,
        route_geometry=route_geometry,
        stops=stops_detail,
        schedules=schedules_detail,
    )


@router.get("/api/passenger/vehicles/{vehicle_id}", response_model=PassengerVehicleStateResponse)
def get_vehicle_state(
    vehicle_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PassengerVehicleStateResponse:
    row = db.execute(
        select(BusCurrentState).where(BusCurrentState.vehicle_id == vehicle_id)
    ).scalar_one_or_none()

    if not row or not row.last_observed_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle state not found")

    crowding_response = None
    try:
        crowding_response = CrowdingEngine.aggregate_vehicle_crowding(db, vehicle_id)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    row_last_observed_at = row.last_observed_at
    if row_last_observed_at.tzinfo is None:
        row_last_observed_at = row_last_observed_at.replace(tzinfo=timezone.utc)

    age_seconds = (now - row_last_observed_at).total_seconds()
    current_state = row.state if row.state else "UNKNOWN"
    if age_seconds > 600:
        current_state = "OFFLINE"

    trip_status = None
    if row.trip_id:
        trip = db.get(Trip, row.trip_id)
        if trip:
            trip_status = trip.status.value

    eta_sec = getattr(row, "eta_seconds", None)
    eta_stat = getattr(row, "eta_status", None)

    if eta_stat == "UNAVAILABLE":
        eta_sec = None

    return PassengerVehicleStateResponse(
        vehicle_id=str(vehicle_id),
        route_id=str(row.route_id) if row.route_id else None,
        direction=row.direction.value if row.direction else None,
        current_stop_id=str(row.current_stop_id) if row.current_stop_id else None,
        next_stop_id=str(row.next_stop_id) if row.next_stop_id else None,
        state=current_state,
        trip_status=trip_status,
        eta_seconds=eta_sec,
        eta_status=eta_stat,
        crowding=crowding_response,
        last_updated_at=row.last_received_at or row.last_observed_at,
    )


from app.models.enums import Direction, CrowdingState
from app.intelligence.core_models import ETAStatus
from app.intelligence.crowding_engine import CrowdingEngine
from sqlalchemy.orm import aliased
from datetime import timedelta
from sqlalchemy import func


@router.get(
    "/api/passenger/services/{service_id}/live", response_model=list[PassengerLiveBusResponse]
)
def get_service_live(
    service_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]
) -> list[PassengerLiveBusResponse]:
    ten_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=10)

    bus_stmt = select(BusCurrentState).where(
        BusCurrentState.service_id == service_id,
        BusCurrentState.state.notin_(["OFFLINE", "STALE"]),
        BusCurrentState.last_observed_at >= ten_mins_ago,
    )
    buses = db.execute(bus_stmt).scalars().all()

    result = []
    for b in buses:
        if b.trip_id:
            t = db.get(Trip, b.trip_id)
            if t and t.status.value in ("COMPLETED", "ABANDONED", "CANCELLED"):
                continue

        c_resp = None
        try:
            c_resp = CrowdingEngine.aggregate_vehicle_crowding(db, b.vehicle_id)
        except Exception:
            pass

        c_level = c_resp.state.value if c_resp else "UNKNOWN"
        if c_level == "FULL":
            c_level = "HIGH"

        result.append(
            PassengerLiveBusResponse(
                vehicle_id=str(b.vehicle_id),
                latitude=b.latitude,
                longitude=b.longitude,
                direction=b.direction.value if b.direction else None,
                current_stop_id=str(b.current_stop_id) if b.current_stop_id else None,
                next_stop_id=str(b.next_stop_id) if b.next_stop_id else None,
                eta_seconds=b.eta_seconds if b.eta_status != "UNAVAILABLE" else None,
                eta_status=b.eta_status,
                crowd_level=c_level,
                state=b.state,
                last_updated_at=b.last_received_at or b.last_observed_at,
            )
        )

    return result




@router.get(
    "/api/passenger/stops/{stop_id}/departures", response_model=list[PassengerDepartureResponse]
)
def get_departures(
    stop_id: uuid.UUID,
    organization_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    service_id: Optional[uuid.UUID] = Query(None),
    direction: Optional[Direction] = Query(None),
) -> list[PassengerDepartureResponse]:
    # 1. Verify Stop and Org scope
    stop = db.execute(
        select(Stop).where(Stop.id == stop_id, Stop.organization_id == organization_id)
    ).scalar_one_or_none()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found or organization mismatch")

    # 2. Get all services that pass through this stop
    stmt = (
        select(Service, RouteStop)
        .join(Route, Service.route_id == Route.id)
        .join(RouteStop, Route.id == RouteStop.route_id)
        .options(
            selectinload(Service.service_schedules),
            selectinload(Service.route).selectinload(Route.route_stops),
        )
        .where(
            Service.organization_id == organization_id,
            Service.status == "ACTIVE",
            RouteStop.stop_id == stop_id,
        )
    )

    if service_id:
        stmt = stmt.where(Service.id == service_id)

    results = db.execute(stmt).all()

    now = datetime.now(timezone.utc)
    ten_mins_ago = now - timedelta(minutes=10)

    response_items = []

    for srv, rs in results:
        route_stops = sorted(srv.route.route_stops, key=lambda x: x.sequence_number)

        # Service can operate in A_TO_B or B_TO_A, check schedules
        for sch in srv.service_schedules:
            if sch.status != "ACTIVE":
                continue

            if direction and sch.direction != direction:
                continue

            dir_enum = sch.direction
            # Compute route origin/dest based on direction
            if dir_enum == Direction.A_TO_B:
                route_origin = db.get(Stop, route_stops[0].stop_id).name
                route_dest = db.get(Stop, route_stops[-1].stop_id).name
            else:
                route_origin = db.get(Stop, route_stops[-1].stop_id).name
                route_dest = db.get(Stop, route_stops[0].stop_id).name

            # If current stop is the destination, no departures from here
            if (
                dir_enum == Direction.A_TO_B
                and rs.sequence_number == route_stops[-1].sequence_number
            ):
                continue
            if (
                dir_enum == Direction.B_TO_A
                and rs.sequence_number == route_stops[0].sequence_number
            ):
                continue

            # Compute scheduled arrival time
            travel_time = _compute_travel_time(route_stops, rs.sequence_number, dir_enum)
            sch_arrival = None
            if travel_time is not None:
                sch_arrival = _get_next_scheduled_arrival(sch, travel_time, now)

            # Find live buses for this service/direction approaching this stop
            # (In a real system, we'd check if sequence_number > bus.current_sequence_number)
            bus_stmt = select(BusCurrentState).where(
                BusCurrentState.service_id == srv.id,
                BusCurrentState.direction == dir_enum,
                BusCurrentState.state.notin_(["OFFLINE", "STALE"]),
                BusCurrentState.last_observed_at >= ten_mins_ago,
                BusCurrentState.eta_seconds.isnot(None),
                BusCurrentState.eta_status != "UNAVAILABLE",
            )
            live_buses = db.execute(bus_stmt).scalars().all()

            # Find the best live bus. For MVP, just pick the nearest one.
            # In a real departure board, we would pick the bus specifically predicting THIS stop.
            # But ETAEngine provides ETA to next stop / destination.
            # We will just map the nearest bus's ETA if it exists, since the UX is simple.

            best_bus = None
            if live_buses:
                sorted_buses = sorted(live_buses, key=lambda b: b.eta_seconds)
                # Ensure the bus hasn't passed us. We can't strictly know without sequence, but we assume
                # the nearest bus is the one coming.
                best_bus = sorted_buses[0]

            expected_arrival = None
            status = "UNAVAILABLE"

            if best_bus:
                expected_arrival = now + timedelta(seconds=best_bus.eta_seconds)
                # Map status
                if sch_arrival:
                    delay = (expected_arrival - sch_arrival).total_seconds()
                    if delay > 300:
                        status = "DELAYED"
                    else:
                        status = "ON_TIME"
                else:
                    status = "ON_TIME"

                if best_bus.eta_seconds < 60:
                    status = "ARRIVING"
            else:
                if sch_arrival:
                    status = "ON_TIME"  # Scheduled

            # If no live bus and no scheduled arrival, skip
            if not best_bus and not sch_arrival:
                continue

            response_items.append(
                PassengerDepartureResponse(
                    service_id=str(srv.id),
                    service_name=srv.service_name,
                    direction=dir_enum.value,
                    route_origin=route_origin,
                    route_destination=route_dest,
                    scheduled_time=sch_arrival,
                    expected_time=expected_arrival,
                    status=status,
                )
            )

    # Sort by expected time (or scheduled time)
    def sort_key(item):
        t = item.expected_time or item.scheduled_time
        return t if t else datetime.max.replace(tzinfo=timezone.utc)

    response_items.sort(key=sort_key)
    return response_items


@router.get("/api/passenger/plan", response_model=list[PassengerPlanTripResponse])
def plan_trip(
    organization_id: uuid.UUID,
    origin_id: uuid.UUID,
    destination_id: uuid.UUID,
    date: date,
    time: time,
    db: Annotated[Session, Depends(get_db)],
) -> list[PassengerPlanTripResponse]:
    if origin_id == destination_id:
        raise HTTPException(status_code=400, detail="Origin and destination must be different")

    # Org scope check
    orig_stop = db.execute(
        select(Stop).where(Stop.id == origin_id, Stop.organization_id == organization_id)
    ).scalar_one_or_none()
    dest_stop = db.execute(
        select(Stop).where(Stop.id == destination_id, Stop.organization_id == organization_id)
    ).scalar_one_or_none()

    if not orig_stop or not dest_stop:
        raise HTTPException(status_code=404, detail="Stops not found or organization mismatch")

    RS_orig = aliased(RouteStop)
    RS_dest = aliased(RouteStop)

    stmt = (
        select(Service, RS_orig.sequence_number, RS_dest.sequence_number)
        .join(Route, Service.route_id == Route.id)
        .join(RS_orig, Route.id == RS_orig.route_id)
        .join(RS_dest, Route.id == RS_dest.route_id)
        .options(
            selectinload(Service.service_schedules),
            selectinload(Service.route).selectinload(Route.route_stops),
        )
        .where(
            Service.organization_id == organization_id,
            Service.status == "ACTIVE",
            RS_orig.stop_id == origin_id,
            RS_dest.stop_id == destination_id,
            RS_orig.sequence_number != RS_dest.sequence_number,
        )
    )

    results = db.execute(stmt).all()

    req_datetime = datetime.combine(date, time).replace(tzinfo=timezone.utc)

    response_items = []

    for srv, orig_seq, dest_seq in results:
        req_direction = Direction.A_TO_B if orig_seq < dest_seq else Direction.B_TO_A
        route_stops = srv.route.route_stops

        # Route names
        if req_direction == Direction.A_TO_B:
            route_origin = db.get(
                Stop, min(route_stops, key=lambda x: x.sequence_number).stop_id
            ).name
            route_dest = db.get(
                Stop, max(route_stops, key=lambda x: x.sequence_number).stop_id
            ).name
        else:
            route_origin = db.get(
                Stop, max(route_stops, key=lambda x: x.sequence_number).stop_id
            ).name
            route_dest = db.get(
                Stop, min(route_stops, key=lambda x: x.sequence_number).stop_id
            ).name

        travel_time_orig = _compute_travel_time(route_stops, orig_seq, req_direction)
        travel_time_dest = _compute_travel_time(route_stops, dest_seq, req_direction)

        for sch in srv.service_schedules:
            if sch.direction != req_direction or sch.status != "ACTIVE":
                continue

            # Filter days_of_week
            if sch.days_of_week is not None and req_datetime.weekday() not in sch.days_of_week:
                continue

            if travel_time_orig is not None and travel_time_dest is not None:
                sch_dep = _get_next_scheduled_arrival(sch, travel_time_orig, req_datetime)
                if sch_dep:
                    # Calculate arrival time at destination for THIS specific departure
                    # Departure at origin terminal was: sch_dep - travel_time_orig
                    origin_dep = sch_dep - timedelta(seconds=travel_time_orig)
                    sch_arr = origin_dep + timedelta(seconds=travel_time_dest)

                    response_items.append(
                        PassengerPlanTripResponse(
                            service_id=str(srv.id),
                            service_name=srv.service_name,
                            direction=req_direction.value,
                            route_origin=route_origin,
                            route_destination=route_dest,
                            scheduled_departure=sch_dep,
                            scheduled_arrival=sch_arr,
                        )
                    )

    def sort_key(item):
        return (item.scheduled_departure, item.service_name)

    response_items.sort(key=sort_key)
    return response_items


from app.services.fare_service import FareCalculationService, FareCalculationError
from app.schemas.passenger import PassengerFareCalculationResponse

@router.get("/api/passenger/fares/calculate", response_model=PassengerFareCalculationResponse)
def calculate_fare(
    organization_id: uuid.UUID,
    origin_stop_id: uuid.UUID,
    destination_stop_id: uuid.UUID,
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PassengerFareCalculationResponse:
    """Calculate authoritative passenger fare."""
    try:
        result = FareCalculationService.calculate_fare(
            db=db,
            organization_id=organization_id,
            service_id=service_id,
            origin_stop_id=origin_stop_id,
            destination_stop_id=destination_stop_id,
        )
        
        # Convert UUIDs to strings for passenger response schema
        result["matched_slab"]["id"] = str(result["matched_slab"]["id"])
        result["fare_configuration_id"] = str(result["fare_configuration_id"])
        
        return PassengerFareCalculationResponse(**result)
    except FareCalculationError as e:
        raise HTTPException(status_code=400, detail=str(e))

