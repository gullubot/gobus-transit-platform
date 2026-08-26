"""BUILD 1: Domain foundation — 20 domain tables, enums, constraints, indexes.

Revision ID: 0001
Revises:
Create Date: 2026-08-26

Creates all domain tables for the Intelligent Transit Platform:
  organizations, users, operator_profiles, devices,
  services, routes, route_stops, stops, vehicles,
  service_schedules, depot_schedules,
  trips, trip_assignments,
  tracking_sessions, tracking_events, trip_state_history,
  bus_current_state, eta_predictions,
  service_alerts, audit_logs

CRITICAL INTEGRITY:
  - services(organization_id, route_id) -> routes(organization_id, id)
  - trips(service_id, route_id) -> services(id, route_id)
  - trips(organization_id, vehicle_id) -> vehicles(organization_id, id)
  - trips(organization_id, service_id) -> services(organization_id, id)
  - Alert scope/target CHECK constraints
"""

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

from alembic import op

# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# ── PostgreSQL ENUM type definitions ─────────────────────────────────
# All defined with create_type=False so they don't auto-create on table
# create events. We explicitly create/drop them in upgrade/downgrade.
_enums = {
    "organizationtype": PG_ENUM(
        "GOVERNMENT", "PRIVATE", "MUNICIPAL", "OTHER", name="organizationtype", create_type=False
    ),
    "organizationstatus": PG_ENUM(
        "ACTIVE", "SUSPENDED", "INACTIVE", name="organizationstatus", create_type=False
    ),
    "userrole": PG_ENUM(
        "DRIVER", "CONDUCTOR", "FLEET_ADMIN", "DEPOT_ADMIN", name="userrole", create_type=False
    ),
    "verificationstatus": PG_ENUM(
        "PENDING", "VERIFIED", "REJECTED", name="verificationstatus", create_type=False
    ),
    "devicestatus": PG_ENUM(
        "PENDING", "ACTIVE", "SUSPENDED", "REVOKED", name="devicestatus", create_type=False
    ),
    "routestatus": PG_ENUM("ACTIVE", "INACTIVE", name="routestatus", create_type=False),
    "stopstatus": PG_ENUM("ACTIVE", "CLOSED", "INACTIVE", name="stopstatus", create_type=False),
    "servicestatus": PG_ENUM(
        "ACTIVE", "SUSPENDED", "INACTIVE", name="servicestatus", create_type=False
    ),
    "vehiclestatus": PG_ENUM(
        "ACTIVE",
        "MAINTENANCE",
        "DECOMMISSIONED",
        "INACTIVE",
        name="vehiclestatus",
        create_type=False,
    ),
    "direction": PG_ENUM("A_TO_B", "B_TO_A", name="direction", create_type=False),
    "tripstatus": PG_ENUM(
        "PLANNED",
        "SUSPECTED_START",
        "ACTIVE",
        "COMPLETED",
        "CANCELLED",
        "ABANDONED",
        name="tripstatus",
        create_type=False,
    ),
    "assignmentstatus": PG_ENUM(
        "ASSIGNED", "ACTIVE", "ENDED", "CANCELLED", name="assignmentstatus", create_type=False
    ),
    "trackingsessionstatus": PG_ENUM(
        "READY",
        "STARTING",
        "ACTIVE",
        "OFFLINE",
        "SYNCING",
        "ENDING",
        "ENDED",
        name="trackingsessionstatus",
        create_type=False,
    ),
    "validationstatus": PG_ENUM(
        "VALID", "SUSPICIOUS", "REJECTED", name="validationstatus", create_type=False
    ),
    "confidence": PG_ENUM("HIGH", "MEDIUM", "LOW", name="confidence", create_type=False),
    "alertscope": PG_ENUM("SERVICE", "ROUTE", "STOP", "TRIP", name="alertscope", create_type=False),
}


def upgrade() -> None:
    # ── Ensure PostGIS extension ─────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ── Create PostgreSQL enum types explicitly ──────────────────────
    bind = op.get_bind()
    for enum_obj in _enums.values():
        enum_obj.create(bind, checkfirst=True)

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: organizations
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", _enums["organizationtype"], nullable=False, server_default="OTHER"),
        sa.Column("status", _enums["organizationstatus"], nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_organizations_name"),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: users
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", _enums["userrole"], nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_users_id_org"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_phone", "users", ["phone"])
    op.create_index("ix_users_email", "users", ["email"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: operator_profiles
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "operator_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True
        ),
        sa.Column("employee_code", sa.String(50), nullable=False),
        sa.Column("operator_type", sa.String(20), nullable=False),
        sa.Column(
            "verification_status",
            _enums["verificationstatus"],
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_operator_profiles_employee_code", "operator_profiles", ["employee_code"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: devices
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "devices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("device_name", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("app_version", sa.String(50), nullable=True),
        sa.Column("status", _enums["devicestatus"], nullable=False, server_default="PENDING"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("gps_permission_status", sa.String(20), nullable=True),
        sa.Column("network_status", sa.String(20), nullable=True),
        sa.Column("battery_level", sa.Float(), nullable=True),
        sa.Column("paired_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_devices_id_org"),
    )
    op.create_index("ix_devices_organization_id", "devices", ["organization_id"])
    op.create_index("ix_devices_status", "devices", ["status"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: routes (with PostGIS geometry)
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "routes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("route_code", sa.String(50), nullable=False),
        sa.Column("route_name", sa.String(255), nullable=False),
        sa.Column(
            "geometry",
            Geometry(
                geometry_type="LINESTRING", srid=4326, from_text="ST_GeomFromEWKT", name="geometry"
            ),
            nullable=False,
        ),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("status", _enums["routestatus"], nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "route_code", name="uq_routes_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_routes_id_org"),
    )
    op.create_index("ix_routes_organization_id", "routes", ["organization_id"])
    op.create_index("ix_routes_route_code", "routes", ["route_code"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: stops (with PostGIS geometry)
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "stops",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("stop_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location",
            Geometry(
                geometry_type="POINT", srid=4326, from_text="ST_GeomFromEWKT", name="geometry"
            ),
            nullable=False,
        ),
        sa.Column("status", _enums["stopstatus"], nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "stop_code", name="uq_stops_org_code"),
    )
    op.create_index("ix_stops_organization_id", "stops", ["organization_id"])
    op.create_index("ix_stops_stop_code", "stops", ["stop_code"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: route_stops
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "route_stops",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("routes.id"), nullable=False),
        sa.Column("stop_id", UUID(as_uuid=True), sa.ForeignKey("stops.id"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("distance_from_start", sa.Numeric(), nullable=True),
        sa.Column("nominal_travel_time_seconds", sa.Integer(), nullable=True),
        sa.UniqueConstraint("route_id", "sequence_number", name="uq_route_stops_route_seq"),
        sa.UniqueConstraint("route_id", "stop_id", name="uq_route_stops_route_stop"),
        sa.CheckConstraint("sequence_number > 0", name="ck_route_stops_seq_positive"),
    )
    op.create_index("ix_route_stops_route_seq", "route_stops", ["route_id", "sequence_number"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: vehicles
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "vehicles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("vehicle_number", sa.String(50), nullable=False),
        sa.Column("registration_number", sa.String(50), nullable=True),
        sa.Column("vehicle_type", sa.String(50), nullable=False),
        sa.Column("status", _enums["vehiclestatus"], nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "vehicle_number", name="uq_vehicles_org_number"),
        sa.UniqueConstraint("id", "organization_id", name="uq_vehicles_id_org"),
    )
    op.create_index("ix_vehicles_organization_id", "vehicles", ["organization_id"])
    op.create_index("ix_vehicles_vehicle_number", "vehicles", ["vehicle_number"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: services
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("route_id", UUID(as_uuid=True), nullable=False),
        sa.Column("service_code", sa.String(50), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("status", _enums["servicestatus"], nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "service_code", name="uq_services_org_code"),
        sa.UniqueConstraint("id", "route_id", name="uq_services_id_route"),
        sa.UniqueConstraint("id", "organization_id", name="uq_services_id_org"),
        # CRITICAL: service.route must belong to same organization
        sa.ForeignKeyConstraint(
            ["organization_id", "route_id"],
            ["routes.organization_id", "routes.id"],
            name="fk_services_org_route",
        ),
    )
    op.create_index("ix_services_organization_id", "services", ["organization_id"])
    op.create_index("ix_services_service_code", "services", ["service_code"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: service_schedules
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "service_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("direction", _enums["direction"], nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("typical_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("days_of_week", ARRAY(sa.Integer()), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "typical_interval_minutes > 0", name="ck_service_schedules_interval_positive"
        ),
    )
    op.create_index("ix_service_schedules_service_id", "service_schedules", ["service_id"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: depot_schedules
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "depot_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("direction", _enums["direction"], nullable=False),
        sa.Column("operating_date", sa.Date(), nullable=False),
        sa.Column("planned_departure", sa.DateTime(), nullable=False),
        sa.Column("planned_arrival", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PLANNED"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_depot_schedules_vehicle_id", "depot_schedules", ["vehicle_id"])
    op.create_index("ix_depot_schedules_service_id", "depot_schedules", ["service_id"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: trips
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "trips",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), nullable=False),
        sa.Column("direction", _enums["direction"], nullable=False),
        sa.Column("operating_date", sa.Date(), nullable=False),
        sa.Column("planned_start_at", sa.DateTime(), nullable=False),
        sa.Column("actual_start_at", sa.DateTime(), nullable=True),
        sa.Column("actual_end_at", sa.DateTime(), nullable=True),
        sa.Column("expected_end_at", sa.DateTime(), nullable=True),
        sa.Column("status", _enums["tripstatus"], nullable=False, server_default="PLANNED"),
        sa.Column("start_source", sa.String(50), nullable=True),
        sa.Column("end_source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # CRITICAL: trip.route_id must match service.route_id
        sa.ForeignKeyConstraint(
            ["service_id", "route_id"],
            ["services.id", "services.route_id"],
            name="fk_trips_service_route",
        ),
        # Organization integrity: vehicle same org
        sa.ForeignKeyConstraint(
            ["organization_id", "vehicle_id"],
            ["vehicles.organization_id", "vehicles.id"],
            name="fk_trips_org_vehicle",
        ),
        # Organization integrity: service same org
        sa.ForeignKeyConstraint(
            ["organization_id", "service_id"],
            ["services.organization_id", "services.id"],
            name="fk_trips_org_service",
        ),
    )
    op.create_index("ix_trips_service_id", "trips", ["service_id"])
    op.create_index("ix_trips_vehicle_id", "trips", ["vehicle_id"])
    op.create_index("ix_trips_operating_date", "trips", ["operating_date"])
    op.create_index("ix_trips_status", "trips", ["status"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: trip_assignments
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "trip_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(), nullable=True),
        sa.Column("status", _enums["assignmentstatus"], nullable=False, server_default="ASSIGNED"),
    )
    op.create_index("ix_trip_assignments_trip_id", "trip_assignments", ["trip_id"])
    op.create_index("ix_trip_assignments_user_id", "trip_assignments", ["user_id"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: tracking_sessions
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "tracking_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status", _enums["trackingsessionstatus"], nullable=False, server_default="READY"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tracking_sessions_device_id", "tracking_sessions", ["device_id"])
    op.create_index("ix_tracking_sessions_trip_id", "tracking_sessions", ["trip_id"])
    op.create_index("ix_tracking_sessions_status", "tracking_sessions", ["status"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: tracking_events
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "tracking_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("packet_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column(
            "tracking_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tracking_sessions.id"),
            nullable=False,
        ),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=True),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("device_sequence", sa.Integer(), nullable=False),
        sa.Column("battery_level", sa.Float(), nullable=True),
        sa.Column("network_type", sa.String(20), nullable=True),
        sa.Column("gps_status", sa.String(20), nullable=True),
        sa.Column(
            "validation_status", _enums["validationstatus"], nullable=False, server_default="VALID"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "device_id",
            "tracking_session_id",
            "device_sequence",
            name="uq_tracking_events_device_session_seq",
        ),
    )
    op.create_index("ix_tracking_events_packet_id", "tracking_events", ["packet_id"], unique=True)
    op.create_index("ix_tracking_events_trip_id", "tracking_events", ["trip_id"])
    op.create_index("ix_tracking_events_device_id", "tracking_events", ["device_id"])
    op.create_index("ix_tracking_events_observed_at", "tracking_events", ["observed_at"])
    op.create_index(
        "ix_tracking_events_trip_observed", "tracking_events", ["trip_id", "observed_at"]
    )
    op.create_index("ix_tracking_events_session", "tracking_events", ["tracking_session_id"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: trip_state_history
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "trip_state_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("previous_state", sa.String(30), nullable=True),
        sa.Column("new_state", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_trip_state_history_trip_id", "trip_state_history", ["trip_id"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: bus_current_state
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "bus_current_state",
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), primary_key=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=True),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=True),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("routes.id"), nullable=True),
        sa.Column("direction", _enums["direction"], nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("route_progress", sa.Float(), nullable=True),
        sa.Column("current_stop_id", UUID(as_uuid=True), sa.ForeignKey("stops.id"), nullable=True),
        sa.Column("next_stop_id", UUID(as_uuid=True), sa.ForeignKey("stops.id"), nullable=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("state_reason", sa.String(255), nullable=True),
        sa.Column("confidence", _enums["confidence"], nullable=True),
        sa.Column("canonical_source", sa.String(50), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(), nullable=True),
        sa.Column("last_received_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bus_current_state_trip_id", "bus_current_state", ["trip_id"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: eta_predictions
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "eta_predictions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("stop_id", UUID(as_uuid=True), sa.ForeignKey("stops.id"), nullable=False),
        sa.Column("predicted_arrival_at", sa.DateTime(), nullable=False),
        sa.Column("predicted_minutes", sa.Integer(), nullable=False),
        sa.Column("confidence", _enums["confidence"], nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("based_on_observed_at", sa.DateTime(), nullable=False),
        sa.Column("algorithm_version", sa.String(50), nullable=False),
    )
    op.create_index(
        "ix_eta_predictions_trip_stop_computed",
        "eta_predictions",
        ["trip_id", "stop_id", "computed_at"],
    )

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: service_alerts
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "service_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=True),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("routes.id"), nullable=True),
        sa.Column("stop_id", UUID(as_uuid=True), sa.ForeignKey("stops.id"), nullable=True),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=True),
        sa.Column("scope", _enums["alertscope"], nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_until", sa.DateTime(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # Alert scope/target integrity CHECK constraints
        sa.CheckConstraint(
            "(scope != 'SERVICE' OR service_id IS NOT NULL)",
            name="ck_alerts_service_scope",
        ),
        sa.CheckConstraint(
            "(scope != 'ROUTE' OR route_id IS NOT NULL)",
            name="ck_alerts_route_scope",
        ),
        sa.CheckConstraint(
            "(scope != 'STOP' OR stop_id IS NOT NULL)",
            name="ck_alerts_stop_scope",
        ),
        sa.CheckConstraint(
            "(scope != 'TRIP' OR trip_id IS NOT NULL)",
            name="ck_alerts_trip_scope",
        ),
    )
    op.create_index("ix_service_alerts_organization_id", "service_alerts", ["organization_id"])
    op.create_index("ix_service_alerts_service_id", "service_alerts", ["service_id"])
    op.create_index("ix_service_alerts_route_id", "service_alerts", ["route_id"])
    op.create_index("ix_service_alerts_stop_id", "service_alerts", ["stop_id"])
    op.create_index("ix_service_alerts_trip_id", "service_alerts", ["trip_id"])

    # ═══════════════════════════════════════════════════════════════════
    # TABLE: audit_logs
    # ═══════════════════════════════════════════════════════════════════
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("audit_logs")
    op.drop_table("service_alerts")
    op.drop_table("eta_predictions")
    op.drop_table("bus_current_state")
    op.drop_table("trip_state_history")
    op.drop_table("tracking_events")
    op.drop_table("tracking_sessions")
    op.drop_table("trip_assignments")
    op.drop_table("trips")
    op.drop_table("depot_schedules")
    op.drop_table("service_schedules")
    op.drop_table("services")
    op.drop_table("vehicles")
    op.drop_table("route_stops")
    op.drop_table("stops")
    op.drop_table("routes")
    op.drop_table("devices")
    op.drop_table("operator_profiles")
    op.drop_table("users")
    op.drop_table("organizations")

    # Drop enum types
    bind = op.get_bind()
    for enum_obj in reversed(list(_enums.values())):
        enum_obj.drop(bind, checkfirst=True)
