"""
Transit Platform — Real Route Loader API Client.

Retrieves actual route topology and ordered stops from GET /api/passenger/services/{service_id}.
Constructs an immutable simulation RouteModel without modifying backend data.
"""

from typing import Any, Dict, List
from simulator.api.client import GoBusHttpClient
from simulator.core.exceptions import SimulatorError
from simulator.core.route import RouteModel, SimulatedStop
from simulator.utils.logging import get_logger

logger = get_logger("route_loader")


def fetch_service_route(
    client: GoBusHttpClient,
    service_id: str,
    organization_id: str,
    direction: str = "A_TO_B",
) -> RouteModel:
    """
    Fetches route topology and stops for a service from the real GoBus passenger API.
    Reverses stop sequence if direction is B_TO_A.
    """
    if not service_id:
        raise ValueError("Cannot fetch route: service_id is required")
    if not organization_id:
        raise ValueError("Cannot fetch route: organization_id is required")

    url = f"/api/passenger/services/{service_id}"
    logger.info(f"Fetching route for Service {service_id[:8]}... (Org: {organization_id[:8]}...)")
    
    try:
        data = client.get(url, params={"organization_id": organization_id})
    except Exception as e:
        logger.error(f"Failed to fetch service route details: {e}")
        raise

    raw_stops = data.get("stops", [])
    if not raw_stops or len(raw_stops) < 2:
        raise SimulatorError(
            f"Service {service_id} has insufficient stops ({len(raw_stops)}). At least 2 stops are required for simulation."
        )

    # Sort stops ascending by sequence_number
    sorted_stops = sorted(raw_stops, key=lambda s: int(s.get("sequence_number", 0)))

    # Parse into SimulatedStop objects
    parsed_stops: List[SimulatedStop] = []
    for s in sorted_stops:
        lat = s.get("latitude")
        lon = s.get("longitude")
        if lat is None or lon is None:
            logger.warning(f"Skipping stop {s.get('stop_name')} with missing coordinates")
            continue

        parsed_stops.append(
            SimulatedStop(
                stop_id=str(s["stop_id"]),
                stop_name=str(s.get("stop_name", "Unknown Stop")),
                sequence_number=int(s["sequence_number"]),
                latitude=float(lat),
                longitude=float(lon),
                distance_from_start_km=float(s["distance_from_start"]) if s.get("distance_from_start") is not None else None,
            )
        )

    if len(parsed_stops) < 2:
        raise SimulatorError(f"Route for service {service_id} has fewer than 2 stops with valid GPS coordinates.")

    # If duty direction is B_TO_A, reverse the stop order for reverse traversal
    normalized_direction = direction.upper()
    if normalized_direction == "B_TO_A":
        logger.info(f"Reversing stop sequence for B_TO_A trip traversal ({len(parsed_stops)} stops)")
        parsed_stops = list(reversed(parsed_stops))

    route_model = RouteModel(
        route_id=str(data.get("route_id", "")),
        route_code=str(data.get("route_code", "UNKNOWN")),
        route_name=str(data.get("route_name", "Unknown Route")),
        stops=parsed_stops,
        direction=normalized_direction,
    )

    logger.info(
        f"Route loaded successfully: {route_model.route_code} ({route_model.route_name}) — "
        f"{route_model.stop_count} stops, {route_model.total_distance_m / 1000.0:.2f} km total distance."
    )
    return route_model
