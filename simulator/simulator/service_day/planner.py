"""
Transit Platform — Service-Day Planner.

BUILD 4 Phase 5B: Deterministic plan construction, vehicle-duty chaining,
operator assignment verification, and schedule validation engine.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from simulator.service_day.manifest import ServiceDayManifest
from simulator.service_day.models import (
    FleetCoverageSummary,
    OperatorDuty,
    ScheduledTrip,
    ServiceCoverageSummary,
    ServiceDayEvent,
    ServiceDayEventType,
    ServiceDayPlan,
    ServiceDayState,
    TripExecutionState,
    VehicleDuty,
    VehicleOperationalState,
)


class PlanValidationError(Exception):
    """Raised when a service-day manifest contains structural or operational conflicts."""
    def __init__(self, errors: List[str]):
        super().__init__(f"ServiceDayPlan validation failed with {len(errors)} error(s): " + "; ".join(errors))
        self.errors = errors


class ServiceDayPlanner:
    """
    Constructs and validates a deterministic ServiceDayPlan from a manifest.
    """

    @classmethod
    def build_plan(cls, manifest: ServiceDayManifest) -> ServiceDayPlan:
        """
        Parses, validates, and builds an immutable ServiceDayPlan.
        Raises PlanValidationError if schedule or assignment conflicts are detected.
        """
        errors: List[str] = []

        # 1. Index available vehicles and operators
        vehicle_map: Dict[str, Dict[str, Any]] = {v["vehicle_id"]: v for v in manifest.vehicles}
        operator_map: Dict[str, Dict[str, Any]] = {o["operator_code"]: o for o in manifest.operators}

        tz_name = manifest.timezone or "Asia/Kolkata"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = timezone.utc

        parsed_trips: List[ScheduledTrip] = []
        seen_trip_ids: Set[str] = set()

        for idx, t_data in enumerate(manifest.trips):
            tid = str(t_data.get("trip_id", ""))
            if not tid:
                errors.append(f"Trip #{idx} is missing 'trip_id'")
                continue

            if tid in seen_trip_ids:
                errors.append(f"Duplicate trip_id '{tid}' detected")
            seen_trip_ids.add(tid)

            # Check vehicle existence
            vid = str(t_data.get("vehicle_id", ""))
            if vid not in vehicle_map:
                errors.append(f"Trip '{tid}' references unconfigured vehicle_id '{vid}'")

            # Check operator existence
            op_code = str(t_data.get("operator_code", ""))
            if op_code not in operator_map:
                errors.append(f"Trip '{tid}' references unconfigured operator_code '{op_code}'")

            # Parse start and end datetimes
            try:
                p_start = datetime.fromisoformat(t_data["planned_start"])
                if p_start.tzinfo is None:
                    p_start = p_start.replace(tzinfo=tz)
            except Exception as e:
                errors.append(f"Trip '{tid}' has invalid planned_start: {e}")
                continue

            p_end: Optional[datetime] = None
            if t_data.get("planned_end"):
                try:
                    p_end = datetime.fromisoformat(t_data["planned_end"])
                    if p_end.tzinfo is None:
                        p_end = p_end.replace(tzinfo=tz)
                    if p_end <= p_start:
                        errors.append(f"Trip '{tid}' has planned_end <= planned_start ({p_end} <= {p_start})")
                except Exception as e:
                    errors.append(f"Trip '{tid}' has invalid planned_end: {e}")

            v_info = vehicle_map.get(vid, {})
            parsed_trips.append(
                ScheduledTrip(
                    trip_id=tid,
                    service_id=str(t_data.get("service_id", "")),
                    service_code=str(t_data.get("service_code", "UNKNOWN")),
                    route_id=str(t_data.get("route_id", "")),
                    route_code=str(t_data.get("route_code", "UNKNOWN")),
                    vehicle_id=vid,
                    vehicle_number=str(v_info.get("vehicle_number", "UNKNOWN")),
                    operator_code=op_code,
                    direction=str(t_data.get("direction", "A_TO_B")),
                    operating_date=str(t_data.get("operating_date", manifest.service_date)),
                    planned_start=p_start,
                    planned_end=p_end,
                    source=str(t_data.get("source", "SCHEDULE")),
                    state=TripExecutionState.PENDING,
                )
            )

        # 2. Deterministic Sorting:
        # 1. operating_date, 2. planned_start, 3. vehicle_id, 4. trip_id
        parsed_trips.sort(
            key=lambda t: (t.operating_date, t.planned_start, t.vehicle_id, t.trip_id)
        )

        # 3. Build & Validate Vehicle Duties
        vehicle_duties: Dict[str, VehicleDuty] = {}
        for vid, v_info in vehicle_map.items():
            vehicle_duties[vid] = VehicleDuty(
                vehicle_id=vid,
                vehicle_number=v_info.get("vehicle_number", "UNKNOWN"),
                vehicle_type=v_info.get("vehicle_type", "BUS"),
                trips=[],
                state=VehicleOperationalState.IDLE,
            )

        for trip in parsed_trips:
            if trip.vehicle_id in vehicle_duties:
                vehicle_duties[trip.vehicle_id].trips.append(trip)

        # Validate sequential non-overlapping trips per vehicle
        for vid, duty in vehicle_duties.items():
            for i in range(len(duty.trips) - 1):
                t1 = duty.trips[i]
                t2 = duty.trips[i + 1]
                t1_end = t1.planned_end or t1.planned_start
                if t2.planned_start < t1_end:
                    errors.append(
                        f"Overlapping vehicle duty on vehicle '{duty.vehicle_number}' ({vid}): "
                        f"Trip '{t1.trip_id}' ends at {t1_end} but Trip '{t2.trip_id}' starts earlier at {t2.planned_start}"
                    )

        # 4. Build & Validate Operator Duties (Strict Single Simultaneous Assignment rule)
        operator_duties: Dict[str, OperatorDuty] = {}
        for op_code, op_info in operator_map.items():
            operator_duties[op_code] = OperatorDuty(
                operator_code=op_code,
                operator_name=op_info.get("operator_name", "Operator"),
                trips=[],
            )

        for trip in parsed_trips:
            if trip.operator_code in operator_duties:
                operator_duties[trip.operator_code].trips.append(trip)

        # Validate that no operator is assigned to overlapping simultaneous trips
        for op_code, op_duty in operator_duties.items():
            # Sort operator trips chronologically
            op_duty.trips.sort(key=lambda t: t.planned_start)
            for i in range(len(op_duty.trips) - 1):
                t1 = op_duty.trips[i]
                t2 = op_duty.trips[i + 1]
                t1_end = t1.planned_end or t1.planned_start
                if t2.planned_start < t1_end:
                    errors.append(
                        f"Operator assignment conflict for operator '{op_code}': "
                        f"Assigned to overlapping trips '{t1.trip_id}' (ends {t1_end}) and '{t2.trip_id}' (starts {t2.planned_start})"
                    )

        # Check accumulated errors
        if errors:
            raise PlanValidationError(errors)

        # 5. Timeline boundaries
        first_dep: Optional[datetime] = parsed_trips[0].planned_start if parsed_trips else None
        final_arr: Optional[datetime] = None
        if parsed_trips:
            final_arr = max(
                (t.planned_end or t.planned_start) for t in parsed_trips
            )

        total_duration_s = 0.0
        if first_dep and final_arr and final_arr >= first_dep:
            total_duration_s = (final_arr - first_dep).total_seconds()

        # 6. Generate ServiceDayEvents
        events: List[ServiceDayEvent] = []
        for trip in parsed_trips:
            start_offset = (trip.planned_start - first_dep).total_seconds() if first_dep else 0.0
            events.append(
                ServiceDayEvent(
                    event_id=f"EV_START_{trip.trip_id}",
                    event_type=ServiceDayEventType.TRIP_START,
                    sim_time_offset_s=start_offset,
                    sim_datetime=trip.planned_start,
                    target_vehicle_id=trip.vehicle_id,
                    target_trip_id=trip.trip_id,
                    target_operator_code=trip.operator_code,
                    payload={"direction": trip.direction, "service_code": trip.service_code},
                )
            )

            if trip.planned_end:
                end_offset = (trip.planned_end - first_dep).total_seconds() if first_dep else 0.0
                events.append(
                    ServiceDayEvent(
                        event_id=f"EV_END_{trip.trip_id}",
                        event_type=ServiceDayEventType.TRIP_END,
                        sim_time_offset_s=end_offset,
                        sim_datetime=trip.planned_end,
                        target_vehicle_id=trip.vehicle_id,
                        target_trip_id=trip.trip_id,
                        target_operator_code=trip.operator_code,
                    )
                )

        # Sort events chronologically by sim_time_offset_s
        events.sort(key=lambda e: (e.sim_time_offset_s, e.event_type.value))

        # 7. Coverage Summaries
        # Calculate max simultaneous vehicles by sweeping active intervals
        active_intervals: List[Tuple[datetime, datetime]] = [
            (t.planned_start, t.planned_end or t.planned_start) for t in parsed_trips
        ]
        max_simultaneous = cls._calculate_max_simultaneous(active_intervals)

        active_veh_count = sum(1 for d in vehicle_duties.values() if d.trip_count > 0)
        idle_veh_count = len(vehicle_duties) - active_veh_count

        fleet_coverage = FleetCoverageSummary(
            total_vehicles=len(vehicle_duties),
            active_vehicles_with_duties=active_veh_count,
            idle_vehicles_without_duties=idle_veh_count,
            max_simultaneous_vehicles=max_simultaneous,
            total_scheduled_trips=len(parsed_trips),
        )

        service_coverages = cls._calculate_service_coverage(parsed_trips)

        return ServiceDayPlan(
            service_date=manifest.service_date,
            timezone_name=tz_name,
            vehicle_duties=vehicle_duties,
            operator_duties=operator_duties,
            trips=parsed_trips,
            events=events,
            fleet_coverage=fleet_coverage,
            service_coverages=service_coverages,
            state=ServiceDayState.DAY_READY,
            first_departure=first_dep,
            final_arrival=final_arr,
            total_duration_s=total_duration_s,
        )

    @staticmethod
    def _calculate_max_simultaneous(intervals: List[Tuple[datetime, datetime]]) -> int:
        """Finds the peak count of overlapping active trip intervals."""
        if not intervals:
            return 0
        events = []
        for start, end in intervals:
            events.append((start, 1))
            events.append((end, -1))
        # Sort by timestamp; ends (-1) before starts (1) if times are equal
        events.sort(key=lambda x: (x[0], x[1]))

        current = 0
        max_seen = 0
        for _, delta in events:
            current += delta
            if current > max_seen:
                max_seen = current
        return max_seen

    @staticmethod
    def _calculate_service_coverage(trips: List[ScheduledTrip]) -> List[ServiceCoverageSummary]:
        """Groups trips by (service_id, direction) and computes coverage metrics."""
        groups: Dict[Tuple[str, str], List[ScheduledTrip]] = {}
        for t in trips:
            key = (t.service_id, t.direction)
            if key not in groups:
                groups[key] = []
            groups[key].append(t)

        coverages: List[ServiceCoverageSummary] = []
        for (sid, direct), t_list in groups.items():
            t_list.sort(key=lambda x: x.planned_start)
            first_d = t_list[0].planned_start
            final_d = t_list[-1].planned_start

            # Calculate average headway if > 1 trip
            headway_mins: Optional[int] = None
            if len(t_list) > 1:
                intervals = [
                    (t_list[i + 1].planned_start - t_list[i].planned_start).total_seconds() / 60.0
                    for i in range(len(t_list) - 1)
                ]
                headway_mins = int(round(sum(intervals) / len(intervals)))

            coverages.append(
                ServiceCoverageSummary(
                    service_id=sid,
                    service_code=t_list[0].service_code,
                    service_name=t_list[0].service_code,
                    route_id=t_list[0].route_id,
                    direction=direct,
                    first_departure=first_d,
                    final_departure=final_d,
                    trip_count=len(t_list),
                    headway_minutes=headway_mins,
                )
            )
        return coverages
