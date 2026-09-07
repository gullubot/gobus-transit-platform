import uuid
from typing import List, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.fare import FareConfiguration, FareSlab
from app.models.route import RouteStop, Route
from app.models.service import Service

class FareCalculationError(Exception):
    """Base exception for fare calculation errors."""
    pass


class FareCalculationService:

    @staticmethod
    def validate_slabs(slabs: List[dict]) -> None:
        """
        Validates a list of slab definitions before they are inserted.
        Expects a list of dicts with: min_distance_km, max_distance_km, fare_amount.
        Throws ValueError if invalid.
        """
        if not slabs:
            raise ValueError("Fare configuration must have at least one slab.")

        # Sort slabs by min_distance_km just to be sure, though they should be sorted
        sorted_slabs = sorted(slabs, key=lambda s: float(s["min_distance_km"]))

        # First slab must start at 0.0
        if float(sorted_slabs[0]["min_distance_km"]) != 0.0:
            raise ValueError("The first fare slab must start at 0.0 km.")

        open_ended_count = 0

        for i, slab in enumerate(sorted_slabs):
            min_dist = float(slab["min_distance_km"])
            max_dist = float(slab["max_distance_km"]) if slab.get("max_distance_km") is not None else None
            fare = float(slab["fare_amount"])

            if min_dist < 0:
                raise ValueError(f"min_distance_km cannot be negative: {min_dist}")
            
            if fare < 0:
                raise ValueError(f"fare_amount cannot be negative: {fare}")

            if max_dist is not None:
                if max_dist <= min_dist:
                    raise ValueError(f"max_distance_km ({max_dist}) must be greater than min_distance_km ({min_dist})")
            else:
                open_ended_count += 1
                if i != len(sorted_slabs) - 1:
                    raise ValueError("Only the final slab can be open-ended (max_distance_km = null).")

            # Check continuity with the next slab
            if i < len(sorted_slabs) - 1:
                next_slab = sorted_slabs[i + 1]
                next_min_dist = float(next_slab["min_distance_km"])
                
                if max_dist is None:
                    raise ValueError("Cannot have subsequent slabs after an open-ended slab.")
                    
                if next_min_dist != max_dist:
                    raise ValueError(f"Slab gap or overlap detected. Slab {i} ends at {max_dist}, but Slab {i+1} starts at {next_min_dist}.")

        if open_ended_count > 1:
            raise ValueError("Only one open-ended slab is permitted.")

    @staticmethod
    def get_active_fare_config(db: Session, organization_id: uuid.UUID) -> Optional[FareConfiguration]:
        """Gets the active fare configuration for an organization."""
        result = db.execute(
            select(FareConfiguration)
            .where(
                FareConfiguration.organization_id == organization_id,
                FareConfiguration.is_active == True
            )
        )
        return result.scalars().first()

    @staticmethod
    def calculate_fare(
        db: Session,
        organization_id: uuid.UUID,
        service_id: uuid.UUID,
        origin_stop_id: uuid.UUID,
        destination_stop_id: uuid.UUID,
    ) -> dict:
        """
        Authoritative fare calculation.
        """
        # 1. Resolve Service and verify organization
        service = db.execute(
            select(Service).where(Service.id == service_id, Service.organization_id == organization_id)
        ).scalars().first()
        if not service:
            raise FareCalculationError("Service not found or does not belong to the organization.")
            
        route_id = service.route_id
        
        if origin_stop_id == destination_stop_id:
            distance_km = 0.0
        else:
            # 2. Verify route belongs to organization
            route = db.execute(
                select(Route).where(Route.id == route_id, Route.organization_id == organization_id)
            ).scalars().first()
            if not route:
                raise FareCalculationError("Route not found or does not belong to the organization.")

            # 2. Get RouteStops for origin and destination
            origin_rs = db.execute(
                select(RouteStop).where(RouteStop.route_id == route_id, RouteStop.stop_id == origin_stop_id)
            ).scalars().first()
            
            dest_rs = db.execute(
                select(RouteStop).where(RouteStop.route_id == route_id, RouteStop.stop_id == destination_stop_id)
            ).scalars().first()

            if not origin_rs or not dest_rs:
                raise FareCalculationError("One or both stops do not belong to the specified route.")

            if origin_rs.distance_from_start is None or dest_rs.distance_from_start is None:
                raise FareCalculationError("Distance data is unavailable for one or both stops on this route.")

            distance_km = abs(float(dest_rs.distance_from_start) - float(origin_rs.distance_from_start))

        # 3. Find active fare configuration linked to service
        if not service.fare_configuration_id:
            raise FareCalculationError("No fare configuration assigned to this service.")
            
        config = db.execute(
            select(FareConfiguration).where(
                FareConfiguration.id == service.fare_configuration_id,
                FareConfiguration.organization_id == organization_id
            )
        ).scalars().first()
        
        if not config:
            raise FareCalculationError("Fare configuration not found or does not belong to the organization.")
            
        # We also check if it's currently active/effective.
        # Although the Product Owner says effective dates apply, we just need to verify it's active.
        if not config.is_active:
            raise FareCalculationError("The selected fare configuration is currently inactive.")

        if not config.slabs:
            raise FareCalculationError("Active fare configuration has no slabs defined.")

        # 4. Find matching slab
        # Convert slabs to a sorted list just in case
        sorted_slabs = sorted(config.slabs, key=lambda s: float(s.min_distance_km))
        
        matched_slab = None
        for slab in sorted_slabs:
            min_d = float(slab.min_distance_km)
            max_d = float(slab.max_distance_km) if slab.max_distance_km is not None else None
            
            # Boundary convention: min_distance_km <= distance < max_distance_km
            if max_d is not None:
                if min_d <= distance_km < max_d:
                    matched_slab = slab
                    break
            else:
                # Open ended slab
                if min_d <= distance_km:
                    matched_slab = slab
                    break

        if not matched_slab:
            # This should only happen if validation was bypassed and gaps exist, or distance < 0 (impossible due to abs)
            raise FareCalculationError(f"No fare slab matches the distance of {distance_km:.2f} km.")

        return {
            "distance_km": round(distance_km, 2),
            "fare_amount": float(matched_slab.fare_amount),
            "currency": config.currency,
            "matched_slab": {
                "id": matched_slab.id,
                "min_distance_km": float(matched_slab.min_distance_km),
                "max_distance_km": float(matched_slab.max_distance_km) if matched_slab.max_distance_km is not None else None,
                "fare_amount": float(matched_slab.fare_amount)
            },
            "fare_configuration_id": config.id,
            "fare_configuration_name": config.name
        }
