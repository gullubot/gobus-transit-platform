"""API clients package for GoBus Simulator."""
from simulator.api.client import GoBusHttpClient
from simulator.api.auth import operator_login, operator_logout
from simulator.api.assignment import fetch_operator_assignment
from simulator.api.route import fetch_service_route
from simulator.api.trip import start_trip_tracking, end_trip_tracking
from simulator.api.telemetry import create_telemetry_packet, send_telemetry_batch, BatchAckResult, RejectedPacket
from simulator.api.heartbeat import send_device_heartbeat
from simulator.api.crowding import submit_crowding_report, VALID_CROWDING_STATES

__all__ = [
    "GoBusHttpClient",
    "operator_login",
    "operator_logout",
    "fetch_operator_assignment",
    "fetch_service_route",
    "start_trip_tracking",
    "end_trip_tracking",
    "create_telemetry_packet",
    "send_telemetry_batch",
    "BatchAckResult",
    "RejectedPacket",
    "send_device_heartbeat",
    "submit_crowding_report",
    "VALID_CROWDING_STATES",
]
