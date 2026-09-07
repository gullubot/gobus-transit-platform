import uuid
import json
from datetime import date, datetime, time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from geoalchemy2.elements import WKTElement

from app.api.deps import get_db, get_current_admin
from app.models.user import User
from app.models.route import Stop, StopAlias, Route, RouteStop
from app.models.fare import FareConfiguration, FareSlab
from app.services.fare_service import FareCalculationService
from app.models.service import Service, ServiceSchedule
from app.schemas.admin_network import (
    AdminStopCreate, AdminStopUpdate, AdminStopResponse,
    AdminRouteCreate, AdminRouteUpdate, AdminRouteResponse, AdminRouteCreateWithStops,
    AdminRouteStopCreate, AdminRouteStopUpdate, AdminRouteStopResponse, AdminRouteStopBulkUpdate,
    AdminServiceCreate, AdminServiceUpdate, AdminServiceResponse,
    RouteDuplicateCheckRequest, RouteDuplicateCheckResponse,
    RoutePreviewRequest, RoutePreviewResponse, RoutePreviewStopItem
)
from app.services.routing_service import (
    routing_service,
    RoutingException,
    RoutingServiceUnavailableException,
    NoRouteFoundException,
    InvalidCoordinatesException
)


router = APIRouter()

# -------------------------------------------------------------------------
# STOPS
# -------------------------------------------------------------------------

def _format_stop_response(stop: Stop) -> AdminStopResponse:
    aliases_list = [a.alias_name for a in stop.aliases] if hasattr(stop, "aliases") and stop.aliases else []
    return AdminStopResponse(
        id=stop.id,
        organization_id=stop.organization_id,
        stop_code=stop.stop_code,
        name=stop.name,
        latitude=stop.latitude,
        longitude=stop.longitude,
        status=stop.status,
        aliases=aliases_list,
        created_at=stop.created_at,
        updated_at=stop.updated_at,
    )


@router.get("/stops", response_model=list[AdminStopResponse])
def get_stops(
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    stmt = (
        select(Stop)
        .options(selectinload(Stop.aliases))
        .where(Stop.organization_id == current_admin.organization_id)
        .order_by(Stop.stop_code)
    )
    stops = db.execute(stmt).scalars().all()
    return [_format_stop_response(s) for s in stops]


@router.get("/stops/{stop_id}", response_model=AdminStopResponse)
def get_stop(
    stop_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    stop = db.execute(
        select(Stop)
        .options(selectinload(Stop.aliases))
        .where(Stop.id == stop_id, Stop.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    return _format_stop_response(stop)


@router.post("/stops", response_model=AdminStopResponse, status_code=status.HTTP_201_CREATED)
def create_stop(
    stop_in: AdminStopCreate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # A. Validate stop_code against same organization
    existing_code = db.execute(
        select(Stop).where(
            Stop.organization_id == current_admin.organization_id,
            Stop.stop_code == stop_in.stop_code
        )
    ).scalar_one_or_none()
    if existing_code:
        raise HTTPException(
            status_code=409,
            detail=f"Stop code '{stop_in.stop_code}' already exists in this organization."
        )

    # B. Check for coordinate collision (Data quality warning, NOT a rejection)
    existing_coord = db.execute(
        select(Stop).where(
            Stop.organization_id == current_admin.organization_id,
            func.abs(Stop.latitude - stop_in.latitude) < 0.00001,
            func.abs(Stop.longitude - stop_in.longitude) < 0.00001
        )
    ).scalars().first()
    if existing_coord:
        warning_msg = (
            f"Another Stop ({existing_coord.stop_code} - {existing_coord.name}) exists at this location. "
            "Review before continuing."
        )
        response.headers["X-Data-Quality-Warning"] = warning_msg

    location_wkt = f"SRID=4326;POINT({stop_in.longitude} {stop_in.latitude})"
    stop = Stop(
        organization_id=current_admin.organization_id,
        stop_code=stop_in.stop_code,
        name=stop_in.name,
        latitude=stop_in.latitude,
        longitude=stop_in.longitude,
        location=WKTElement(location_wkt, srid=4326),
        status=stop_in.status
    )
    db.add(stop)
    db.flush()

    for alias_str in stop_in.aliases:
        clean = alias_str.strip()
        if clean:
            alias = StopAlias(
                stop_id=stop.id,
                organization_id=current_admin.organization_id,
                alias_name=clean,
                alias_type="LOCAL_NAME"
            )
            db.add(alias)

    try:
        db.commit()
        db.refresh(stop)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Stop code '{stop_in.stop_code}' already exists in this organization."
        )

    return _format_stop_response(stop)


@router.put("/stops/{stop_id}", response_model=AdminStopResponse)
def update_stop(
    stop_id: uuid.UUID,
    stop_in: AdminStopUpdate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    stop = db.execute(
        select(Stop)
        .options(selectinload(Stop.aliases))
        .where(Stop.id == stop_id, Stop.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    update_data = stop_in.model_dump(exclude_unset=True)

    # Protect same-organization stop_code uniqueness
    if "stop_code" in update_data and update_data["stop_code"] != stop.stop_code:
        conflict = db.execute(
            select(Stop).where(
                Stop.organization_id == current_admin.organization_id,
                Stop.stop_code == update_data["stop_code"],
                Stop.id != stop_id
            )
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Stop code '{update_data['stop_code']}' already exists in this organization."
            )
        stop.stop_code = update_data["stop_code"]

    if "name" in update_data:
        stop.name = update_data["name"]
    if "status" in update_data and update_data["status"] is not None:
        stop.status = update_data["status"]

    new_lat = update_data.get("latitude", stop.latitude)
    new_lon = update_data.get("longitude", stop.longitude)

    if ("latitude" in update_data or "longitude" in update_data) and (new_lat != stop.latitude or new_lon != stop.longitude):
        stop.latitude = new_lat
        stop.longitude = new_lon
        if new_lat is not None and new_lon is not None:
            stop.location = WKTElement(f"SRID=4326;POINT({new_lon} {new_lat})", srid=4326)
            existing_coord = db.execute(
                select(Stop).where(
                    Stop.organization_id == current_admin.organization_id,
                    func.abs(Stop.latitude - new_lat) < 0.00001,
                    func.abs(Stop.longitude - new_lon) < 0.00001,
                    Stop.id != stop_id
                )
            ).scalars().first()
            if existing_coord:
                response.headers["X-Data-Quality-Warning"] = (
                    f"Another Stop ({existing_coord.stop_code} - {existing_coord.name}) exists at this location. "
                    "Review before continuing."
                )

    if stop_in.aliases is not None:
        db.execute(StopAlias.__table__.delete().where(StopAlias.stop_id == stop_id))
        for alias_str in stop_in.aliases:
            clean = alias_str.strip()
            if clean:
                alias = StopAlias(
                    stop_id=stop.id,
                    organization_id=current_admin.organization_id,
                    alias_name=clean,
                    alias_type="LOCAL_NAME"
                )
                db.add(alias)

    try:
        db.commit()
        db.refresh(stop)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Invalid update, possible duplicate stop code"
        )

    return _format_stop_response(stop)


@router.delete("/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stop(
    stop_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    stop = db.execute(
        select(Stop).where(Stop.id == stop_id, Stop.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
        
    try:
        db.delete(stop)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete stop because it is referenced by routes")

@router.get("/stops/{stop_id}/routes", response_model=list[AdminRouteResponse])
def get_routes_for_stop(
    stop_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # Verify stop belongs to org
    stop = db.execute(
        select(Stop).where(Stop.id == stop_id, Stop.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
        
    stmt = (
        select(Route)
        .join(RouteStop, Route.id == RouteStop.route_id)
        .where(RouteStop.stop_id == stop_id)
    )
    routes = db.execute(stmt).scalars().all()
    
    return [
        AdminRouteResponse(
            id=r.id,
            organization_id=r.organization_id,
            route_code=r.route_code,
            route_name=r.route_name,
            distance_km=r.distance_km,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            geometry=None
        ) for r in routes
    ]


# -------------------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------------------

def _parse_geojson_linestring(geojson_dict: dict) -> str:
    if geojson_dict.get("type") != "LineString":
        raise HTTPException(status_code=400, detail="Geometry must be a GeoJSON LineString")
    coords = geojson_dict.get("coordinates")
    if not coords or not isinstance(coords, list):
        raise HTTPException(status_code=400, detail="Invalid LineString coordinates")
    
    # Explicitly reject artificial placeholder coordinates
    if coords == [[0, 0], [1, 1]] or coords == [[0.0, 0.0], [1.0, 1.0]]:
        raise HTTPException(status_code=400, detail="Artificial placeholder geometry [[0,0], [1,1]] is not permitted")

    coord_strs = []
    for c in coords:
        if not isinstance(c, list) or len(c) < 2:
            raise HTTPException(status_code=400, detail="Invalid coordinate pair")
        coord_strs.append(f"{c[0]} {c[1]}")
    
    return f"SRID=4326;LINESTRING({', '.join(coord_strs)})"


def _validate_and_order_stops(
    db: Session,
    current_admin: User,
    start_stop_id: uuid.UUID,
    end_stop_id: uuid.UUID,
    intermediate_stop_ids: Optional[list[uuid.UUID]] = None
) -> list[Stop]:
    """
    Validates the start stop, end stop, and intermediate stops sequence.
    Ensures:
      - Start and end stops exist and are not identical.
      - Start and end stops are not repeated in intermediate stops.
      - No duplicate stops anywhere in the sequence.
      - Total stops >= 2.
      - All stops belong to current_admin.organization_id.
      - All stops have valid coordinates (rejects missing coordinates).
      - Preserves exact specified order: [start] + intermediate + [end].
    """
    if start_stop_id == end_stop_id:
        raise HTTPException(status_code=400, detail="Start stop and end stop cannot be the same.")

    intermediates = intermediate_stop_ids or []
    if start_stop_id in intermediates:
        raise HTTPException(status_code=400, detail="Start stop cannot be repeated in intermediate stops.")
    if end_stop_id in intermediates:
        raise HTTPException(status_code=400, detail="End stop cannot be repeated in intermediate stops.")

    if len(intermediates) != len(set(intermediates)):
        raise HTTPException(status_code=400, detail="Duplicate stops inside route sequence are not permitted.")

    ordered_ids = [start_stop_id] + list(intermediates) + [end_stop_id]
    if len(ordered_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 stops are required to create a route.")

    # Fetch all stops
    stops = db.execute(select(Stop).where(Stop.id.in_(ordered_ids))).scalars().all()
    stop_map = {s.id: s for s in stops}

    ordered_stops: list[Stop] = []
    for s_id in ordered_ids:
        if s_id not in stop_map:
            raise HTTPException(status_code=404, detail=f"Stop with ID '{s_id}' does not exist.")
        stop = stop_map[s_id]
        if stop.organization_id != current_admin.organization_id:
            raise HTTPException(status_code=400, detail=f"Stop '{stop.stop_code}' does not belong to your organization.")
        if stop.latitude is None or stop.longitude is None:
            raise HTTPException(
                status_code=400,
                detail=f"Route distance cannot be calculated because Stop '{stop.stop_code} - {stop.name}' has no coordinates."
            )
        if not (-90.0 <= stop.latitude <= 90.0 and -180.0 <= stop.longitude <= 180.0):
            raise HTTPException(
                status_code=400,
                detail=f"Stop '{stop.stop_code} - {stop.name}' has invalid coordinates."
            )
        ordered_stops.append(stop)

    return ordered_stops


def _check_duplicate_route_sequence(
    db: Session,
    org_id: uuid.UUID,
    stop_ids: list[uuid.UUID],
    exclude_route_id: Optional[uuid.UUID] = None
) -> Optional[RouteDuplicateCheckResponse]:
    """
    Checks if another route in the same organization has the exact same ordered Stop UUID sequence.
    """
    query = select(Route).where(Route.organization_id == org_id)
    if exclude_route_id:
        query = query.where(Route.id != exclude_route_id)
    other_routes = db.execute(query).scalars().all()

    for r in other_routes:
        r_stops = db.execute(
            select(RouteStop.stop_id)
            .where(RouteStop.route_id == r.id)
            .order_by(RouteStop.sequence_number.asc())
        ).scalars().all()

        if list(r_stops) == list(stop_ids):
            stop_names = []
            for s_id in stop_ids:
                st = db.get(Stop, s_id)
                stop_names.append(f"{st.stop_code} - {st.name}" if st else str(s_id))

            return RouteDuplicateCheckResponse(
                is_duplicate=True,
                existing_route_id=r.id,
                route_code=r.route_code,
                route_name=r.route_name,
                matching_stops=stop_names
            )
    return None


@router.post("/routes/preview", response_model=RoutePreviewResponse)
def preview_route(
    preview_in: RoutePreviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    ordered_stops = _validate_and_order_stops(
        db=db,
        current_admin=current_admin,
        start_stop_id=preview_in.start_stop_id,
        end_stop_id=preview_in.end_stop_id,
        intermediate_stop_ids=preview_in.intermediate_stop_ids
    )

    all_stop_ids = [s.id for s in ordered_stops]
    duplicate_match = _check_duplicate_route_sequence(
        db, current_admin.organization_id, all_stop_ids, exclude_route_id=preview_in.exclude_route_id
    )

    try:
        result, stop_metrics = routing_service.calculate_route_for_stops(ordered_stops)
    except RoutingServiceUnavailableException as exc:
        raise HTTPException(status_code=503, detail="Unable to calculate road distance right now. Please try again.") from exc
    except NoRouteFoundException as exc:
        raise HTTPException(status_code=400, detail="No drivable route could be calculated through the selected Stops.") from exc
    except (InvalidCoordinatesException, RoutingException) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preview_stops = []
    for s, m in zip(ordered_stops, stop_metrics):
        preview_stops.append(RoutePreviewStopItem(
            stop_id=s.id,
            stop_code=s.stop_code,
            stop_name=s.name,
            sequence_number=m["sequence_number"],
            distance_from_start=m["distance_from_start"],
            nominal_travel_time_seconds=m["nominal_travel_time_seconds"]
        ))

    return RoutePreviewResponse(
        distance_km=result.distance_km,
        duration_seconds=result.duration_seconds,
        geometry=result.geometry,
        stops=preview_stops,
        duplicate_match=duplicate_match
    )


@router.get("/routes", response_model=list[AdminRouteResponse])
def get_routes(
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # Base route info without loading huge geometries for list view
    stmt = select(Route).where(Route.organization_id == current_admin.organization_id)
    routes = db.execute(stmt).scalars().all()
    # Return without geometry for the list endpoint to save bandwidth
    return [
        AdminRouteResponse(
            id=r.id,
            organization_id=r.organization_id,
            route_code=r.route_code,
            route_name=r.route_name,
            distance_km=r.distance_km,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            geometry=None
        ) for r in routes
    ]

@router.get("/routes/{route_id}", response_model=AdminRouteResponse)
def get_route(
    route_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    route = db.execute(
        select(Route).where(Route.id == route_id, Route.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    geojson_str = db.execute(
        select(func.ST_AsGeoJSON(Route.geometry)).where(Route.id == route_id)
    ).scalar()
    
    geometry_dict = json.loads(geojson_str) if geojson_str else None
    
    response = AdminRouteResponse(
        id=route.id,
        organization_id=route.organization_id,
        route_code=route.route_code,
        route_name=route.route_name,
        distance_km=route.distance_km,
        status=route.status,
        created_at=route.created_at,
        updated_at=route.updated_at,
        geometry=geometry_dict
    )
    return response


@router.post("/routes", response_model=AdminRouteResponse, status_code=status.HTTP_200_OK)
def create_route(
    route_in: AdminRouteCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # Check duplicate route_code within organization
    existing_code = db.execute(
        select(Route).where(
            Route.organization_id == current_admin.organization_id,
            Route.route_code == route_in.route_code
        )
    ).scalar_one_or_none()
    if existing_code:
        raise HTTPException(status_code=400, detail="Route code already exists for this organization")

    # If start_stop_id and end_stop_id are provided: authentic road routing flow
    if route_in.start_stop_id and route_in.end_stop_id:
        ordered_stops = _validate_and_order_stops(
            db=db,
            current_admin=current_admin,
            start_stop_id=route_in.start_stop_id,
            end_stop_id=route_in.end_stop_id,
            intermediate_stop_ids=route_in.intermediate_stop_ids
        )

        try:
            result, stop_metrics = routing_service.calculate_route_for_stops(ordered_stops)
        except RoutingServiceUnavailableException as exc:
            raise HTTPException(status_code=503, detail="Unable to calculate road distance right now. Please try again.") from exc
        except NoRouteFoundException as exc:
            raise HTTPException(status_code=400, detail="No drivable route could be calculated through the selected Stops.") from exc
        except (InvalidCoordinatesException, RoutingException) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        wkt = _parse_geojson_linestring(result.geometry)
        route = Route(
            organization_id=current_admin.organization_id,
            route_code=route_in.route_code,
            route_name=route_in.route_name,
            distance_km=result.distance_km,
            geometry=WKTElement(wkt, srid=4326),
            status=route_in.status
        )
        db.add(route)
        db.flush()

        for m in stop_metrics:
            rs = RouteStop(
                route_id=route.id,
                stop_id=m["stop_id"],
                sequence_number=m["sequence_number"],
                distance_from_start=m["distance_from_start"],
                nominal_travel_time_seconds=m["nominal_travel_time_seconds"]
            )
            db.add(rs)

        db.commit()
        db.refresh(route)

        return AdminRouteResponse(
            id=route.id,
            organization_id=route.organization_id,
            route_code=route.route_code,
            route_name=route.route_name,
            distance_km=route.distance_km,
            status=route.status,
            created_at=route.created_at,
            updated_at=route.updated_at,
            geometry=result.geometry
        )

    # Legacy creation path (e.g. for existing test suites that pass manual geometry/distance)
    wkt = _parse_geojson_linestring(route_in.geometry) if route_in.geometry else None
    route = Route(
        organization_id=current_admin.organization_id,
        route_code=route_in.route_code,
        route_name=route_in.route_name,
        distance_km=route_in.distance_km,
        geometry=WKTElement(wkt, srid=4326) if wkt else None,
        status=route_in.status
    )
    db.add(route)
    try:
        db.commit()
        db.refresh(route)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Route code already exists for this organization")
    
    response = AdminRouteResponse(
        id=route.id,
        organization_id=route.organization_id,
        route_code=route.route_code,
        route_name=route.route_name,
        distance_km=route.distance_km,
        status=route.status,
        created_at=route.created_at,
        updated_at=route.updated_at,
        geometry=route_in.geometry
    )
    return response


@router.put("/routes/{route_id}", response_model=AdminRouteResponse)
def update_route(
    route_id: uuid.UUID,
    route_in: AdminRouteUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    route = db.execute(
        select(Route).where(Route.id == route_id, Route.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    update_data = route_in.model_dump(exclude_unset=True)

    # If stop sequence is provided: atomic topology recalculation and route_stops update
    if route_in.start_stop_id and route_in.end_stop_id:
        ordered_stops = _validate_and_order_stops(
            db=db,
            current_admin=current_admin,
            start_stop_id=route_in.start_stop_id,
            end_stop_id=route_in.end_stop_id,
            intermediate_stop_ids=route_in.intermediate_stop_ids or []
        )

        try:
            result, stop_metrics = routing_service.calculate_route_for_stops(ordered_stops)
        except RoutingServiceUnavailableException as exc:
            raise HTTPException(status_code=503, detail="Unable to calculate road distance right now. Please try again.") from exc
        except NoRouteFoundException as exc:
            raise HTTPException(status_code=400, detail="No drivable route could be calculated through the selected Stops.") from exc
        except (InvalidCoordinatesException, RoutingException) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        wkt = _parse_geojson_linestring(result.geometry)
        route.geometry = WKTElement(wkt, srid=4326)
        route.distance_km = result.distance_km

        # Replace RouteStop rows for this route
        db.execute(RouteStop.__table__.delete().where(RouteStop.route_id == route_id))
        for m in stop_metrics:
            rs = RouteStop(
                route_id=route_id,
                stop_id=m["stop_id"],
                sequence_number=m["sequence_number"],
                distance_from_start=m["distance_from_start"],
                nominal_travel_time_seconds=m["nominal_travel_time_seconds"]
            )
            db.add(rs)

    # Clean up stop fields from update_data before setting route attributes
    for stop_field in ("start_stop_id", "end_stop_id", "intermediate_stop_ids"):
        update_data.pop(stop_field, None)

    if "geometry" in update_data:
        if update_data["geometry"] is not None:
            wkt = _parse_geojson_linestring(update_data["geometry"])
            route.geometry = WKTElement(wkt, srid=4326)
        else:
            route.geometry = None
        del update_data["geometry"]

    for field, value in update_data.items():
        setattr(route, field, value)

    try:
        db.commit()
        db.refresh(route)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid update, possible duplicate route code")
        
    geojson_str = db.execute(
        select(func.ST_AsGeoJSON(Route.geometry)).where(Route.id == route_id)
    ).scalar()
    
    response = AdminRouteResponse(
        id=route.id,
        organization_id=route.organization_id,
        route_code=route.route_code,
        route_name=route.route_name,
        distance_km=route.distance_km,
        status=route.status,
        created_at=route.created_at,
        updated_at=route.updated_at,
        geometry=json.loads(geojson_str) if geojson_str else None
    )
    return response


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    route = db.execute(
        select(Route).where(Route.id == route_id, Route.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    try:
        db.delete(route)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete route because it is referenced by services or stops")


# -------------------------------------------------------------------------
# ROUTE STOPS
# -------------------------------------------------------------------------

@router.get("/routes/{route_id}/stops", response_model=list[AdminRouteStopResponse])
def get_route_stops(
    route_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # Verify route ownership
    route = db.execute(
        select(Route).where(Route.id == route_id, Route.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    stmt = select(RouteStop).where(RouteStop.route_id == route_id).order_by(RouteStop.sequence_number)
    route_stops = db.execute(stmt).scalars().all()
    
    responses = []
    for rs in route_stops:
        stop = db.get(Stop, rs.stop_id)
        resp = AdminRouteStopResponse.model_validate(rs)
        if stop:
            resp.stop_code = stop.stop_code
            resp.stop_name = stop.name
        responses.append(resp)
        
    return responses


@router.post("/routes/{route_id}/check-duplicate-stops", response_model=RouteDuplicateCheckResponse)
def check_route_duplicate_stops(
    route_id: uuid.UUID,
    check_req: RouteDuplicateCheckRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    """
    Checks whether another route in the same organization has the exact same ordered Stop UUID sequence.
    Returns existing route details if found, so Admin can choose [Use Existing Route] or [Continue as New Route].
    """
    target_sequence = check_req.stops
    if not target_sequence:
        return RouteDuplicateCheckResponse(is_duplicate=False)

    other_routes = db.execute(
        select(Route).where(
            Route.organization_id == current_admin.organization_id,
            Route.id != route_id
        )
    ).scalars().all()

    for r in other_routes:
        r_stops = db.execute(
            select(RouteStop.stop_id)
            .where(RouteStop.route_id == r.id)
            .order_by(RouteStop.sequence_number.asc())
        ).scalars().all()

        if list(r_stops) == list(target_sequence):
            stop_names = []
            for s_id in target_sequence:
                st = db.get(Stop, s_id)
                stop_names.append(st.name if st else str(s_id))

            return RouteDuplicateCheckResponse(
                is_duplicate=True,
                existing_route_id=r.id,
                route_code=r.route_code,
                route_name=r.route_name,
                matching_stops=stop_names
            )

    return RouteDuplicateCheckResponse(is_duplicate=False)


@router.post("/routes/{route_id}/stops", response_model=list[AdminRouteStopResponse])
def update_route_stops_bulk(
    route_id: uuid.UUID,
    bulk_in: AdminRouteStopBulkUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    """Replaces the entire set of route stops for the route and recalculates road distance & geometry."""
    # Verify route ownership
    route = db.execute(
        select(Route).where(Route.id == route_id, Route.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stop_ids = [s.stop_id for s in bulk_in.stops]
    if stop_ids:
        # Check duplicate stops in sequence
        if len(stop_ids) != len(set(stop_ids)):
            raise HTTPException(status_code=400, detail="Duplicate stops inside route sequence are not permitted.")

        valid_stops = db.execute(
            select(Stop).where(Stop.id.in_(stop_ids), Stop.organization_id == current_admin.organization_id)
        ).scalars().all()
        if len(valid_stops) != len(stop_ids):
            raise HTTPException(status_code=400, detail="One or more stops do not belong to your organization")

        stop_map = {s.id: s for s in valid_stops}
        ordered_items = sorted(bulk_in.stops, key=lambda x: x.sequence_number)
        ordered_stops = [stop_map[item.stop_id] for item in ordered_items]

        # If 2 or more stops, recalculate authentic road distance and geometry
        if len(ordered_stops) >= 2:
            try:
                result, stop_metrics = routing_service.calculate_route_for_stops(ordered_stops)
            except RoutingServiceUnavailableException as exc:
                raise HTTPException(status_code=503, detail="Unable to calculate road distance right now. Please try again.") from exc
            except NoRouteFoundException as exc:
                raise HTTPException(status_code=400, detail="No drivable route could be calculated through the selected Stops.") from exc
            except (InvalidCoordinatesException, RoutingException) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            wkt = _parse_geojson_linestring(result.geometry)
            route.geometry = WKTElement(wkt, srid=4326)
            route.distance_km = result.distance_km

            # Delete existing stops for this route
            db.execute(RouteStop.__table__.delete().where(RouteStop.route_id == route_id))

            # Insert new stops with routing-derived distances and times
            for m in stop_metrics:
                rs = RouteStop(
                    route_id=route_id,
                    stop_id=m["stop_id"],
                    sequence_number=m["sequence_number"],
                    distance_from_start=m["distance_from_start"],
                    nominal_travel_time_seconds=m["nominal_travel_time_seconds"]
                )
                db.add(rs)

            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(status_code=400, detail="Invalid sequence or duplicate stops")

            return get_route_stops(route_id, db, current_admin)

    # If fewer than 2 stops
    db.execute(RouteStop.__table__.delete().where(RouteStop.route_id == route_id))
    for s in bulk_in.stops:
        rs = RouteStop(
            route_id=route_id,
            stop_id=s.stop_id,
            sequence_number=s.sequence_number,
            distance_from_start=s.distance_from_start,
            nominal_travel_time_seconds=s.nominal_travel_time_seconds
        )
        db.add(rs)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid sequence or duplicate stops")

    return get_route_stops(route_id, db, current_admin)


# -------------------------------------------------------------------------
# SERVICES
# -------------------------------------------------------------------------

def _enrich_service_response(service: Service, db: Session) -> AdminServiceResponse:
    resp = AdminServiceResponse.model_validate(service)
    route = db.get(Route, service.route_id)
    if route:
        resp.route_code = route.route_code
        resp.route_name = route.route_name
    if service.fare_configuration_id:
        fare_config = db.execute(
            select(FareConfiguration)
            .options(selectinload(FareConfiguration.slabs))
            .where(FareConfiguration.id == service.fare_configuration_id)
        ).scalar_one_or_none()
        if fare_config:
            resp.fare_configuration_name = fare_config.name
            resp.fare_is_active = fare_config.is_active
            resp.fare_currency = fare_config.currency
            resp.fare_slabs_count = len(fare_config.slabs)
    return resp


@router.get("/services", response_model=list[AdminServiceResponse])
def get_services(
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    stmt = (
        select(Service)
        .where(Service.organization_id == current_admin.organization_id)
        .order_by(Service.created_at.desc())
    )
    services = db.execute(stmt).scalars().all()
    return [_enrich_service_response(s, db) for s in services]


@router.get("/services/{service_id}", response_model=AdminServiceResponse)
def get_service(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    service = db.execute(
        select(Service).where(Service.id == service_id, Service.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
        
    return _enrich_service_response(service, db)


@router.post("/services", response_model=AdminServiceResponse)
def create_service(
    service_in: AdminServiceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    # Cannot supply both existing fare_configuration_id and initial_fare_slabs
    if service_in.fare_configuration_id and service_in.initial_fare_slabs:
        raise HTTPException(
            status_code=400,
            detail="Cannot provide both fare_configuration_id and initial_fare_slabs"
        )

    # Verify route ownership
    route = db.execute(
        select(Route).where(Route.id == service_in.route_id, Route.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=400, detail="Route not found or does not belong to your organization")

    # Check for duplicate service_code within organization
    existing_svc = db.execute(
        select(Service).where(
            Service.organization_id == current_admin.organization_id,
            Service.service_code == service_in.service_code.strip()
        )
    ).scalar_one_or_none()
    if existing_svc:
        raise HTTPException(status_code=400, detail=f"Service code '{service_in.service_code.strip()}' already exists for this organization")

    fare_config_id = service_in.fare_configuration_id

    # If existing fare configuration is specified, verify ownership
    if fare_config_id:
        fare_config = db.execute(
            select(FareConfiguration).where(
                FareConfiguration.id == fare_config_id,
                FareConfiguration.organization_id == current_admin.organization_id
            )
        ).scalar_one_or_none()
        if not fare_config:
            raise HTTPException(status_code=400, detail="Fare configuration not found or does not belong to your organization")

    # If initial_fare_slabs is provided, validate and atomically create FareConfiguration + FareSlabs
    elif service_in.initial_fare_slabs:
        try:
            FareCalculationService.validate_slabs([slab.model_dump() for slab in service_in.initial_fare_slabs])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        new_fare_config = FareConfiguration(
            organization_id=current_admin.organization_id,
            name=f"Fare - {service_in.service_name.strip()} ({service_in.service_code.strip()})",
            currency="INR",
            effective_from=date.today(),
            created_by=current_admin.id,
            is_active=True
        )
        db.add(new_fare_config)
        db.flush()

        for slab_in in service_in.initial_fare_slabs:
            db_slab = FareSlab(
                fare_configuration_id=new_fare_config.id,
                min_distance_km=slab_in.min_distance_km,
                max_distance_km=slab_in.max_distance_km,
                fare_amount=slab_in.fare_amount
            )
            db.add(db_slab)
        
        fare_config_id = new_fare_config.id

    service = Service(
        organization_id=current_admin.organization_id,
        route_id=service_in.route_id,
        fare_configuration_id=fare_config_id,
        service_code=service_in.service_code.strip(),
        service_name=service_in.service_name.strip(),
        status=service_in.status
    )
    db.add(service)
    try:
        db.commit()
        db.refresh(service)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Service code already exists for this organization")
    
    return _enrich_service_response(service, db)


@router.put("/services/{service_id}", response_model=AdminServiceResponse)
def update_service(
    service_id: uuid.UUID,
    service_in: AdminServiceUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    service = db.execute(
        select(Service).where(Service.id == service_id, Service.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service_in.service_code is not None and service_in.service_code.strip() != service.service_code:
        dup = db.execute(
            select(Service).where(
                Service.organization_id == current_admin.organization_id,
                Service.service_code == service_in.service_code.strip(),
                Service.id != service.id
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=400, detail=f"Service code '{service_in.service_code.strip()}' already exists for this organization")

    if service_in.route_id:
        route = db.execute(
            select(Route).where(Route.id == service_in.route_id, Route.organization_id == current_admin.organization_id)
        ).scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=400, detail="Route not found or does not belong to your organization")

    if service_in.fare_configuration_id is not None:
        fare_config = db.execute(
            select(FareConfiguration).where(
                FareConfiguration.id == service_in.fare_configuration_id,
                FareConfiguration.organization_id == current_admin.organization_id
            )
        ).scalar_one_or_none()
        if not fare_config:
            raise HTTPException(status_code=400, detail="Fare configuration not found or does not belong to your organization")

    update_data = service_in.model_dump(exclude_unset=True)
    if "service_code" in update_data and update_data["service_code"]:
        update_data["service_code"] = update_data["service_code"].strip()
    if "service_name" in update_data and update_data["service_name"]:
        update_data["service_name"] = update_data["service_name"].strip()

    for field, value in update_data.items():
        setattr(service, field, value)

    try:
        db.commit()
        db.refresh(service)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid update, possible duplicate service code")
        
    return _enrich_service_response(service, db)


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: User = Depends(get_current_admin)
):
    service = db.execute(
        select(Service).where(Service.id == service_id, Service.organization_id == current_admin.organization_id)
    ).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
        
    try:
        db.delete(service)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete service because it is referenced by trips or schedules")
