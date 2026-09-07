"""
Transit Platform — Road Routing Service Abstraction.

Provides automated road-network routing, distance calculation,
and authentic road-following GeoJSON geometry generation via OSRM.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.models.route import Stop

logger = logging.getLogger(__name__)


class RoutingException(Exception):
    """Base exception for routing failures."""
    pass


class RoutingServiceUnavailableException(RoutingException):
    """Raised when routing provider is unreachable, times out, or returns a 5xx error."""
    pass


class NoRouteFoundException(RoutingException):
    """Raised when no drivable road path exists between the supplied waypoints."""
    pass


class InvalidCoordinatesException(RoutingException):
    """Raised when stop coordinates are missing or geographically invalid."""
    pass


@dataclass
class RouteLeg:
    """Individual leg between two consecutive waypoints."""
    distance_km: float
    duration_seconds: int


@dataclass
class RouteCalculationResult:
    """Complete road-network routing calculation output."""
    distance_km: float
    duration_seconds: int
    geometry: Dict[str, Any]
    legs: List[RouteLeg] = field(default_factory=list)


class RoutingProvider(ABC):
    """Abstract interface for road routing providers."""

    @abstractmethod
    def calculate_route(
        self, waypoints: List[Tuple[float, float]]
    ) -> RouteCalculationResult:
        """
        Calculate road path through ordered waypoints.
        Waypoints format: [(longitude, latitude), ...]
        Preserves exact order.
        """
        pass


class OSRMRoutingProvider(RoutingProvider):
    """
    OSRM (Open Source Routing Machine) implementation of RoutingProvider.
    Uses OSRM v1 driving route API.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 12.0):
        self.base_url = (base_url or settings.osrm_base_url).rstrip("/")
        self.timeout = timeout

    def calculate_route(
        self, waypoints: List[Tuple[float, float]]
    ) -> RouteCalculationResult:
        if len(waypoints) < 2:
            raise InvalidCoordinatesException("At least 2 waypoints are required to calculate a route.")

        # OSRM coordinate format: {longitude},{latitude};{longitude},{latitude}
        coord_strings = [f"{lon:.6f},{lat:.6f}" for lon, lat in waypoints]
        coord_path = ";".join(coord_strings)
        url = f"{self.base_url}/route/v1/driving/{coord_path}?overview=full&geometries=geojson&steps=false"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
        except httpx.TimeoutException as exc:
            logger.error(f"OSRM routing timed out: {exc}")
            raise RoutingServiceUnavailableException(
                "Routing provider timed out. Unable to calculate road route right now."
            ) from exc
        except httpx.RequestError as exc:
            logger.error(f"OSRM connection failed: {exc}")
            raise RoutingServiceUnavailableException(
                f"Unable to reach routing provider: {exc}"
            ) from exc

        if response.status_code != 200:
            logger.warning(f"OSRM returned status {response.status_code}: {response.text}")
            try:
                error_body = response.json()
                if error_body.get("code") == "NoRoute":
                    raise NoRouteFoundException(
                        "No drivable route could be calculated through the selected Stops."
                    )
            except (ValueError, KeyError):
                pass
            raise RoutingServiceUnavailableException(
                f"Routing provider returned HTTP {response.status_code}. Check routing availability."
            )

        try:
            data = response.json()
        except Exception as exc:
            logger.error(f"OSRM malformed JSON: {response.text}")
            raise RoutingException("Malformed response received from routing provider.") from exc

        if data.get("code") != "Ok" or not data.get("routes"):
            if data.get("code") == "NoRoute":
                raise NoRouteFoundException(
                    "No drivable route could be calculated through the selected Stops."
                )
            raise RoutingException(
                f"Routing failed with code '{data.get('code', 'Unknown')}': {data.get('message', 'No route returned')}"
            )

        primary_route = data["routes"][0]
        distance_meters = primary_route.get("distance")
        duration_seconds = primary_route.get("duration")
        geometry = primary_route.get("geometry")

        if distance_meters is None or duration_seconds is None or not geometry:
            raise RoutingException("Routing provider response is missing essential route metrics or geometry.")

        # Reject artificial placeholder geometry [[0,0], [1,1]]
        coords = geometry.get("coordinates")
        if not coords or coords == [[0, 0], [1, 1]] or coords == [[0.0, 0.0], [1.0, 1.0]]:
            raise RoutingException("Routing provider returned empty or artificial placeholder geometry.")

        distance_km = round(distance_meters / 1000.0, 3)
        total_duration = int(round(duration_seconds))

        raw_legs = primary_route.get("legs", [])
        legs: List[RouteLeg] = []
        for rl in raw_legs:
            leg_dist = round(rl.get("distance", 0.0) / 1000.0, 3)
            leg_dur = int(round(rl.get("duration", 0.0)))
            legs.append(RouteLeg(distance_km=leg_dist, duration_seconds=leg_dur))

        return RouteCalculationResult(
            distance_km=distance_km,
            duration_seconds=total_duration,
            geometry=geometry,
            legs=legs,
        )


class RouteRoutingService:
    """
    High-level domain service orchestrating road routing for Stops.
    """

    def __init__(self, provider: Optional[RoutingProvider] = None):
        if provider:
            self.provider = provider
        elif settings.routing_provider == "osrm":
            self.provider = OSRMRoutingProvider(base_url=settings.osrm_base_url)
        else:
            raise ValueError(f"Unsupported routing provider: {settings.routing_provider}")

    def calculate_route_for_stops(
        self, ordered_stops: List[Stop]
    ) -> Tuple[RouteCalculationResult, List[Dict[str, Any]]]:
        """
        Calculates road route for an authoritative, ordered list of Stops.
        Returns:
            - RouteCalculationResult (distance_km, duration_seconds, geometry, legs)
            - List of per-stop metrics (sequence_number, distance_from_start, nominal_travel_time_seconds)
        """
        if len(ordered_stops) < 2:
            raise InvalidCoordinatesException("A route requires at least 2 existing stops.")

        waypoints: List[Tuple[float, float]] = []
        for stop in ordered_stops:
            if stop.latitude is None or stop.longitude is None:
                raise InvalidCoordinatesException(
                    f"Route distance cannot be calculated because Stop '{stop.stop_code} - {stop.name}' has no coordinates."
                )
            # Geo coordinates check
            if not (-90.0 <= stop.latitude <= 90.0 and -180.0 <= stop.longitude <= 180.0):
                raise InvalidCoordinatesException(
                    f"Stop '{stop.stop_code} - {stop.name}' has invalid coordinates ({stop.latitude}, {stop.longitude})."
                )
            waypoints.append((float(stop.longitude), float(stop.latitude)))

        result = self.provider.calculate_route(waypoints)

        # Compute cumulative distance and cumulative duration along the sequence
        stop_metrics: List[Dict[str, Any]] = []
        cumulative_dist = 0.0
        cumulative_time = 0

        for idx, stop in enumerate(ordered_stops):
            if idx == 0:
                stop_metrics.append({
                    "stop_id": stop.id,
                    "sequence_number": 1,
                    "distance_from_start": 0.0,
                    "nominal_travel_time_seconds": 0,
                })
            else:
                leg_idx = idx - 1
                if leg_idx < len(result.legs):
                    leg = result.legs[leg_idx]
                    cumulative_dist += leg.distance_km
                    cumulative_time += leg.duration_seconds
                else:
                    cumulative_dist = result.distance_km
                    cumulative_time = result.duration_seconds

                stop_metrics.append({
                    "stop_id": stop.id,
                    "sequence_number": idx + 1,
                    "distance_from_start": round(cumulative_dist, 3),
                    "nominal_travel_time_seconds": cumulative_time,
                })

        return result, stop_metrics


# Default singleton instance
routing_service = RouteRoutingService()
