"""
Transit Platform — Integration Test Fixture Data.

STRICTLY FOR AUTOMATED TESTS TARGETING 'transit_platform_test'.
NEVER RUN AGAINST LIVE 'transit_platform'.
Protected by assert_testing_database(db).
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy.orm import Session

from app.db.guard import assert_testing_database
from app.db.session import SessionLocal
from app.models.device import Device
from app.models.enums import (
    AssignmentStatus,
    DeviceStatus,
    Direction,
    OrganizationStatus,
    OrganizationType,
    RouteStatus,
    ServiceStatus,
    StopStatus,
    TripStatus,
    UserRole,
    VehicleStatus,
    VerificationStatus,
)
from app.models.organization import Organization
from app.models.route import Route, RouteStop, Stop
from app.models.service import DepotSchedule, Service, ServiceSchedule
from app.models.trip import Trip, TripAssignment, TripStateHistory
from app.models.user import OperatorProfile, User
from app.models.vehicle import Vehicle
from app.models.fare import FareConfiguration, FareSlab

# ═══════════════════════════════════════════════════════════════════════
# DETERMINISTIC UUIDs — reproducible across seed runs
# ═══════════════════════════════════════════════════════════════════════

# Organization
ORG_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")

# Routes
ROUTE_R1_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
ROUTE_R2_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")

# Stops — 8 canonical stops
STOP_IDS = {
    "CC": uuid.UUID("30000000-0000-0000-0000-000000000001"),
    "MG": uuid.UUID("30000000-0000-0000-0000-000000000002"),
    "KP": uuid.UUID("30000000-0000-0000-0000-000000000003"),
    "TP": uuid.UUID("30000000-0000-0000-0000-000000000004"),
    "AP": uuid.UUID("30000000-0000-0000-0000-000000000005"),
    "LN": uuid.UUID("30000000-0000-0000-0000-000000000006"),
    "GM": uuid.UUID("30000000-0000-0000-0000-000000000007"),
    "RS": uuid.UUID("30000000-0000-0000-0000-000000000008"),
}

# Services
SVC_AC4B_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
SVC_SD5_ID = uuid.UUID("40000000-0000-0000-0000-000000000002")

# Vehicles
VEH_IDS = {
    "PNB005234": uuid.UUID("50000000-0000-0000-0000-000000000001"),
    "PNB005781": uuid.UUID("50000000-0000-0000-0000-000000000002"),
    "PNB006421": uuid.UUID("50000000-0000-0000-0000-000000000003"),
}

# Users
USER_DRIVER_ID = uuid.UUID("60000000-0000-0000-0000-000000000001")
USER_CONDUCTOR_ID = uuid.UUID("60000000-0000-0000-0000-000000000002")
USER_FLEET_ADMIN_ID = uuid.UUID("60000000-0000-0000-0000-000000000003")
USER_DEPOT_ADMIN_ID = uuid.UUID("60000000-0000-0000-0000-000000000004")

# Operator Profiles
OP_DRIVER_ID = uuid.UUID("61000000-0000-0000-0000-000000000001")
OP_CONDUCTOR_ID = uuid.UUID("61000000-0000-0000-0000-000000000002")

# Devices
DEV_DRIVER_ID = uuid.UUID("70000000-0000-0000-0000-000000000001")
DEV_CONDUCTOR_ID = uuid.UUID("70000000-0000-0000-0000-000000000002")

# Schedules
SCHED_SVC_ID = uuid.UUID("80000000-0000-0000-0000-000000000001")
SCHED_DEPOT_ID = uuid.UUID("81000000-0000-0000-0000-000000000001")

# Trips
TRIP_PLANNED_ID = uuid.UUID("90000000-0000-0000-0000-000000000001")
TRIP_COMPLETED_ID = uuid.UUID("90000000-0000-0000-0000-000000000002")

# Trip Assignments
ASSIGN_DRIVER_ID = uuid.UUID("91000000-0000-0000-0000-000000000001")
ASSIGN_CONDUCTOR_ID = uuid.UUID("91000000-0000-0000-0000-000000000002")

# Route Stops
RS_IDS = {f"R1_{i}": uuid.UUID(f"21000000-0000-0000-0000-00000000000{i}") for i in range(1, 5)}
RS_IDS.update(
    {f"R2_{i}": uuid.UUID(f"22000000-0000-0000-0000-00000000000{i}") for i in range(1, 5)}
)

# Trip State History
TSH_PLANNED_ID = uuid.UUID("92000000-0000-0000-0000-000000000001")
TSH_COMPLETED_ID = uuid.UUID("92000000-0000-0000-0000-000000000002")

# Fares
FARE_CONFIG_ID = uuid.UUID("A0000000-0000-0000-0000-000000000001")
FARE_SLAB_IDS = [
    uuid.UUID("A1000000-0000-0000-0000-000000000001"),
    uuid.UUID("A1000000-0000-0000-0000-000000000002"),
    uuid.UUID("A1000000-0000-0000-0000-000000000003"),
]

NOW = datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# STOP DEFINITIONS — coherent coordinates with PostGIS geometry
# ═══════════════════════════════════════════════════════════════════════

STOPS_DATA = [
    ("CC", "City Center", 30.7333, 76.7794),
    ("MG", "MG Road", 30.7350, 76.7850),
    ("KP", "Knowledge Park", 30.7400, 76.7900),
    ("TP", "Tech Park", 30.7450, 76.7950),
    ("AP", "Airport Terminal", 30.6700, 76.7900),
    ("LN", "Lake Nagar", 30.6800, 76.7800),
    ("GM", "Gandhi Maidan", 30.6900, 76.7750),
    ("RS", "Railway Station", 30.7000, 76.7700),
]


def _wkt_point(lon: float, lat: float) -> str:
    """Produce WKT POINT string (lon, lat order per WKT/PostGIS convention)."""
    return f"SRID=4326;POINT({lon} {lat})"


def _wkt_linestring(coords: list[tuple[float, float]]) -> str:
    """Produce WKT LINESTRING from list of (lon, lat) pairs."""
    pts = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"SRID=4326;LINESTRING({pts})"


def seed_dev_data(db: Session) -> dict[str, int]:
    """
    Seed development data. Idempotent — safe to run multiple times.

    Returns a dict of entity -> count seeded.
    """
    assert_testing_database(db)
    counts: dict[str, int] = {}

    # ── Organization ─────────────────────────────────────────────────
    org = db.get(Organization, ORG_ID)
    if org is None:
        org = Organization(
            id=ORG_ID,
            name="Transit Demo Authority",
            type=OrganizationType.GOVERNMENT,
            status=OrganizationStatus.ACTIVE,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(org)
        db.flush()
        counts["organizations"] = 1
    else:
        counts["organizations"] = 0

    # ── Users ────────────────────────────────────────────────────────
    from app.core.security import get_password_hash

    demo_password_hash = get_password_hash("operator123")
    users_created = 0
    users_data = [
        (USER_DRIVER_ID, "Demo Driver", UserRole.DRIVER, "driver@demo.com"),
        (USER_CONDUCTOR_ID, "Demo Conductor", UserRole.CONDUCTOR, "conductor@demo.com"),
        (USER_FLEET_ADMIN_ID, "Fleet Admin", UserRole.FLEET_ADMIN, "fleet@demo.com"),
        (USER_DEPOT_ADMIN_ID, "Depot Admin", UserRole.DEPOT_ADMIN, "depot@demo.com"),
    ]
    for uid, uname, role, email in users_data:
        user = db.get(User, uid)
        if user is None:
            db.add(
                User(
                    id=uid,
                    organization_id=ORG_ID,
                    name=uname,
                    email=email,
                    role=role,
                    password_hash=demo_password_hash,
                    status="ACTIVE",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            users_created += 1
        else:
            if not user.password_hash:
                user.password_hash = demo_password_hash
            if not user.email:
                user.email = email
    db.flush()
    counts["users"] = users_created

    # ── Operator Profiles ────────────────────────────────────────────
    ops_created = 0
    if db.get(OperatorProfile, OP_DRIVER_ID) is None:
        db.add(
            OperatorProfile(
                id=OP_DRIVER_ID,
                user_id=USER_DRIVER_ID,
                employee_code="DRV001",
                operator_type="DRIVER",
                verification_status=VerificationStatus.VERIFIED,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        ops_created += 1
    if db.get(OperatorProfile, OP_CONDUCTOR_ID) is None:
        db.add(
            OperatorProfile(
                id=OP_CONDUCTOR_ID,
                user_id=USER_CONDUCTOR_ID,
                employee_code="CND001",
                operator_type="CONDUCTOR",
                verification_status=VerificationStatus.VERIFIED,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        ops_created += 1
    db.flush()
    counts["operator_profiles"] = ops_created

    # ── Devices ──────────────────────────────────────────────────────
    devs_created = 0
    if db.get(Device, DEV_DRIVER_ID) is None:
        db.add(
            Device(
                id=DEV_DRIVER_ID,
                organization_id=ORG_ID,
                device_name="Demo Driver Phone",
                platform="ANDROID",
                status=DeviceStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        devs_created += 1
    if db.get(Device, DEV_CONDUCTOR_ID) is None:
        db.add(
            Device(
                id=DEV_CONDUCTOR_ID,
                organization_id=ORG_ID,
                device_name="Demo Conductor Phone",
                platform="ANDROID",
                status=DeviceStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        devs_created += 1
    db.flush()
    counts["devices"] = devs_created


    # ── Stops ────────────────────────────────────────────────────────
    stops_created = 0
    for code, name, lat, lon in STOPS_DATA:
        stop_id = STOP_IDS[code]
        if db.get(Stop, stop_id) is None:
            db.add(
                Stop(
                    id=stop_id,
                    organization_id=ORG_ID,
                    stop_code=code,
                    name=name,
                    latitude=lat,
                    longitude=lon,
                    location=_wkt_point(lon, lat),
                    status=StopStatus.ACTIVE,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            stops_created += 1
    db.flush()
    counts["stops"] = stops_created

    # ── Routes ───────────────────────────────────────────────────────
    routes_created = 0
    if db.get(Route, ROUTE_R1_ID) is None:
        r1_coords = [(76.7794, 30.7333), (76.7850, 30.7350), (76.7900, 30.7400), (76.7950, 30.7450)]
        db.add(
            Route(
                id=ROUTE_R1_ID,
                organization_id=ORG_ID,
                route_code="R1",
                route_name="City Center to Tech Park",
                geometry=_wkt_linestring(r1_coords),
                distance_km=5.2,
                status=RouteStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        routes_created += 1

    if db.get(Route, ROUTE_R2_ID) is None:
        r2_coords = [(76.7900, 30.6700), (76.7800, 30.6800), (76.7750, 30.6900), (76.7700, 30.7000)]
        db.add(
            Route(
                id=ROUTE_R2_ID,
                organization_id=ORG_ID,
                route_code="R2",
                route_name="Airport to Railway Station",
                geometry=_wkt_linestring(r2_coords),
                distance_km=4.8,
                status=RouteStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        routes_created += 1
    db.flush()
    counts["routes"] = routes_created

    # ── Route Stops ──────────────────────────────────────────────────
    rs_created = 0
    r1_stops = [("CC", 1, 0.0), ("MG", 2, 1.3), ("KP", 3, 3.1), ("TP", 4, 5.2)]
    for code, seq, dist in r1_stops:
        rs_id = RS_IDS[f"R1_{seq}"]
        if db.get(RouteStop, rs_id) is None:
            db.add(
                RouteStop(
                    id=rs_id,
                    route_id=ROUTE_R1_ID,
                    stop_id=STOP_IDS[code],
                    sequence_number=seq,
                    distance_from_start=dist,
                    nominal_travel_time_seconds=seq * 300,
                )
            )
            rs_created += 1

    r2_stops = [("AP", 1, 0.0), ("LN", 2, 1.5), ("GM", 3, 2.8), ("RS", 4, 4.8)]
    for code, seq, dist in r2_stops:
        rs_id = RS_IDS[f"R2_{seq}"]
        if db.get(RouteStop, rs_id) is None:
            db.add(
                RouteStop(
                    id=rs_id,
                    route_id=ROUTE_R2_ID,
                    stop_id=STOP_IDS[code],
                    sequence_number=seq,
                    distance_from_start=dist,
                    nominal_travel_time_seconds=seq * 300,
                )
            )
            rs_created += 1
    db.flush()
    counts["route_stops"] = rs_created

    # ── Vehicles ─────────────────────────────────────────────────────
    vehs_created = 0
    vehicles_data = [
        ("PNB005234", "PB01AB1234", "BUS"),
        ("PNB005781", "PB01CD5678", "BUS"),
        ("PNB006421", "PB01EF9012", "MINI_BUS"),
    ]
    for vnum, reg, vtype in vehicles_data:
        vid = VEH_IDS[vnum]
        if db.get(Vehicle, vid) is None:
            db.add(
                Vehicle(
                    id=vid,
                    organization_id=ORG_ID,
                    vehicle_number=vnum,
                    registration_number=reg,
                    vehicle_type=vtype,
                    status=VehicleStatus.ACTIVE,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            vehs_created += 1
    db.flush()
    counts["vehicles"] = vehs_created

    # ── Fares ────────────────────────────────────────────────────────
    fares_created = 0
    if db.get(FareConfiguration, FARE_CONFIG_ID) is None:
        db.add(
            FareConfiguration(
                id=FARE_CONFIG_ID,
                organization_id=ORG_ID,
                name="Base Fare Schedule 2026",
                currency="INR",
                is_active=True,
                effective_from=date(2026, 1, 1),
                created_by=USER_FLEET_ADMIN_ID,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.flush()
        
        slabs_data = [
            (FARE_SLAB_IDS[0], 0.0, 2.0, 10.0),
            (FARE_SLAB_IDS[1], 2.0, 5.0, 15.0),
            (FARE_SLAB_IDS[2], 5.0, None, 20.0),
        ]
        
        for sid, min_dist, max_dist, amt in slabs_data:
            if db.get(FareSlab, sid) is None:
                db.add(
                    FareSlab(
                        id=sid,
                        fare_configuration_id=FARE_CONFIG_ID,
                        min_distance_km=min_dist,
                        max_distance_km=max_dist,
                        fare_amount=amt,
                    )
                )
        db.flush()
        fares_created += 1
    counts["fare_configurations"] = fares_created

    # ── Services ─────────────────────────────────────────────────────
    svcs_created = 0
    if db.get(Service, SVC_AC4B_ID) is None:
        db.add(
            Service(
                id=SVC_AC4B_ID,
                organization_id=ORG_ID,
                route_id=ROUTE_R1_ID,
                fare_configuration_id=FARE_CONFIG_ID,
                service_code="AC4B",
                service_name="AC4B City Center Express",
                status=ServiceStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        svcs_created += 1

    if db.get(Service, SVC_SD5_ID) is None:
        db.add(
            Service(
                id=SVC_SD5_ID,
                organization_id=ORG_ID,
                route_id=ROUTE_R2_ID,
                fare_configuration_id=FARE_CONFIG_ID,
                service_code="SD5",
                service_name="SD5 Airport Shuttle",
                status=ServiceStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        svcs_created += 1
    db.flush()
    counts["services"] = svcs_created



    # ── Service Schedule ─────────────────────────────────────────────
    scheds_created = 0
    if db.get(ServiceSchedule, SCHED_SVC_ID) is None:
        db.add(
            ServiceSchedule(
                id=SCHED_SVC_ID,
                service_id=SVC_AC4B_ID,
                direction=Direction.A_TO_B,
                start_time=time(0, 0),
                end_time=time(23, 59),
                typical_interval_minutes=15,
                days_of_week=[1, 2, 3, 4, 5, 6],
                effective_from=date(2026, 1, 1),
                status="ACTIVE",
                updated_at=NOW,
            )
        )
        scheds_created += 1
    counts["service_schedules"] = scheds_created

    # ── Depot Schedule ───────────────────────────────────────────────
    depot_created = 0
    if db.get(DepotSchedule, SCHED_DEPOT_ID) is None:
        db.add(
            DepotSchedule(
                id=SCHED_DEPOT_ID,
                vehicle_id=VEH_IDS["PNB005234"],
                service_id=SVC_AC4B_ID,
                direction=Direction.A_TO_B,
                operating_date=date(2026, 8, 26),
                planned_departure=datetime(2026, 8, 26, 6, 30, tzinfo=timezone.utc),
                status="PLANNED",
                source="MANUAL",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        depot_created += 1
    db.flush()
    counts["depot_schedules"] = depot_created

    # ── Trips ────────────────────────────────────────────────────────
    trips_created = 0
    if db.get(Trip, TRIP_PLANNED_ID) is None:
        db.add(
            Trip(
                id=TRIP_PLANNED_ID,
                organization_id=ORG_ID,
                service_id=SVC_AC4B_ID,
                vehicle_id=VEH_IDS["PNB005234"],
                route_id=ROUTE_R1_ID,
                direction=Direction.A_TO_B,
                operating_date=date(2026, 8, 26),
                planned_start_at=datetime(2026, 8, 26, 7, 0, tzinfo=timezone.utc),
                status=TripStatus.PLANNED,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        trips_created += 1

    if db.get(Trip, TRIP_COMPLETED_ID) is None:
        db.add(
            Trip(
                id=TRIP_COMPLETED_ID,
                organization_id=ORG_ID,
                service_id=SVC_AC4B_ID,
                vehicle_id=VEH_IDS["PNB005781"],
                route_id=ROUTE_R1_ID,
                direction=Direction.B_TO_A,
                operating_date=date(2026, 8, 25),
                planned_start_at=datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc),
                actual_start_at=datetime(2026, 8, 25, 14, 5, tzinfo=timezone.utc),
                actual_end_at=datetime(2026, 8, 25, 14, 45, tzinfo=timezone.utc),
                status=TripStatus.COMPLETED,
                start_source="MANUAL",
                end_source="MANUAL",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        trips_created += 1
    db.flush()
    counts["trips"] = trips_created

    # ── Trip Assignments ─────────────────────────────────────────────
    assigns_created = 0
    if db.get(TripAssignment, ASSIGN_DRIVER_ID) is None:
        db.add(
            TripAssignment(
                id=ASSIGN_DRIVER_ID,
                trip_id=TRIP_PLANNED_ID,
                user_id=USER_DRIVER_ID,
                device_id=DEV_DRIVER_ID,
                role="DRIVER",
                assigned_at=NOW,
                status=AssignmentStatus.ASSIGNED,
            )
        )
        assigns_created += 1
    if db.get(TripAssignment, ASSIGN_CONDUCTOR_ID) is None:
        db.add(
            TripAssignment(
                id=ASSIGN_CONDUCTOR_ID,
                trip_id=TRIP_PLANNED_ID,
                user_id=USER_CONDUCTOR_ID,
                device_id=DEV_CONDUCTOR_ID,
                role="CONDUCTOR",
                assigned_at=NOW,
                status=AssignmentStatus.ASSIGNED,
            )
        )
        assigns_created += 1
    db.flush()
    counts["trip_assignments"] = assigns_created

    # ── Trip State History ───────────────────────────────────────────
    tsh_created = 0
    if db.get(TripStateHistory, TSH_PLANNED_ID) is None:
        db.add(
            TripStateHistory(
                id=TSH_PLANNED_ID,
                trip_id=TRIP_PLANNED_ID,
                previous_state=None,
                new_state="PLANNED",
                reason="Seed data creation",
                source="SEED",
                created_at=NOW,
            )
        )
        tsh_created += 1
    if db.get(TripStateHistory, TSH_COMPLETED_ID) is None:
        db.add(
            TripStateHistory(
                id=TSH_COMPLETED_ID,
                trip_id=TRIP_COMPLETED_ID,
                previous_state="ACTIVE",
                new_state="COMPLETED",
                reason="Seed data — trip completed",
                source="SEED",
                created_at=NOW,
            )
        )
        tsh_created += 1
    db.flush()
    counts["trip_state_history"] = tsh_created

    # (Fares moved up before services)

    db.commit()
    return counts
