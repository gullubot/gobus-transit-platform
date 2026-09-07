import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_current_admin, get_fleet_admin
from app.models.fare import FareConfiguration, FareSlab
from app.models.service import Service
from app.models.user import User
from app.schemas.admin_fare import (
    FareConfigurationCreate,
    FareConfigurationUpdate,
    FareConfigurationResponse,
    FarePreviewRequest,
    FareCalculationResponse,
)
from app.services.fare_service import FareCalculationService, FareCalculationError

router = APIRouter()


def _enrich_fare_response(config: FareConfiguration, service: Service | None) -> FareConfigurationResponse:
    resp = FareConfigurationResponse.model_validate(config)
    if service:
        resp.service_id = service.id
        resp.service_code = service.service_code
        resp.service_name = service.service_name
    return resp


@router.get("/", response_model=List[FareConfigurationResponse])
def get_fare_configurations(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Get all fare configurations for the admin's organization."""
    configs = db.execute(
        select(FareConfiguration)
        .where(FareConfiguration.organization_id == current_admin.organization_id)
        .order_by(FareConfiguration.created_at.desc())
    ).scalars().all()

    services = db.execute(
        select(Service).where(
            Service.organization_id == current_admin.organization_id,
            Service.fare_configuration_id.is_not(None),
        )
    ).scalars().all()
    svc_by_fare = {s.fare_configuration_id: s for s in services}

    return [_enrich_fare_response(c, svc_by_fare.get(c.id)) for c in configs]


@router.post("/", response_model=FareConfigurationResponse)
def create_fare_configuration(
    config_in: FareConfigurationCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_fleet_admin),
):
    """Create a new fare configuration with slabs."""
    try:
        FareCalculationService.validate_slabs([slab.model_dump() for slab in config_in.slabs])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db_config = FareConfiguration(
        organization_id=current_admin.organization_id,
        name=config_in.name,
        currency=config_in.currency,
        effective_from=config_in.effective_from,
        effective_until=config_in.effective_until,
        created_by=current_admin.id,
    )
    db.add(db_config)
    db.flush()

    for slab_in in config_in.slabs:
        db_slab = FareSlab(
            fare_configuration_id=db_config.id,
            min_distance_km=slab_in.min_distance_km,
            max_distance_km=slab_in.max_distance_km,
            fare_amount=slab_in.fare_amount,
        )
        db.add(db_slab)

    db.commit()
    db.refresh(db_config)
    return _enrich_fare_response(db_config, None)


@router.get("/{config_id}", response_model=FareConfigurationResponse)
def get_fare_configuration(
    config_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Get a specific fare configuration."""
    config = db.execute(
        select(FareConfiguration)
        .where(
            FareConfiguration.id == config_id,
            FareConfiguration.organization_id == current_admin.organization_id
        )
    ).scalars().first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Fare configuration not found")

    svc = db.execute(
        select(Service).where(
            Service.organization_id == current_admin.organization_id,
            Service.fare_configuration_id == config.id,
        )
    ).scalars().first()
        
    return _enrich_fare_response(config, svc)


@router.put("/{config_id}", response_model=FareConfigurationResponse)
def update_fare_configuration(
    config_id: uuid.UUID,
    config_in: FareConfigurationUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_fleet_admin),
):
    """Update a fare configuration and its slabs."""
    config = db.execute(
        select(FareConfiguration)
        .where(
            FareConfiguration.id == config_id,
            FareConfiguration.organization_id == current_admin.organization_id
        )
    ).scalars().first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Fare configuration not found")

    update_data = config_in.model_dump(exclude_unset=True)
    
    if "slabs" in update_data:
        try:
            FareCalculationService.validate_slabs(update_data["slabs"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        # Delete existing slabs
        db.execute(
            FareSlab.__table__.delete().where(FareSlab.fare_configuration_id == config_id)
        )
        
        # Add new slabs
        for slab_in in update_data["slabs"]:
            db_slab = FareSlab(
                fare_configuration_id=config.id,
                min_distance_km=slab_in["min_distance_km"],
                max_distance_km=slab_in["max_distance_km"],
                fare_amount=slab_in["fare_amount"],
            )
            db.add(db_slab)
            
        del update_data["slabs"]

    for field, value in update_data.items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)

    svc = db.execute(
        select(Service).where(
            Service.organization_id == current_admin.organization_id,
            Service.fare_configuration_id == config.id,
        )
    ).scalars().first()

    return _enrich_fare_response(config, svc)


@router.post("/{config_id}/activate", response_model=FareConfigurationResponse)
def activate_fare_configuration(
    config_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_fleet_admin),
):
    """Activate a fare configuration."""
    config = db.execute(
        select(FareConfiguration)
        .where(
            FareConfiguration.id == config_id,
            FareConfiguration.organization_id == current_admin.organization_id
        )
    ).scalars().first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Fare configuration not found")

    config.is_active = True
    db.commit()
    db.refresh(config)

    svc = db.execute(
        select(Service).where(
            Service.organization_id == current_admin.organization_id,
            Service.fare_configuration_id == config.id,
        )
    ).scalars().first()

    return _enrich_fare_response(config, svc)


@router.post("/{config_id}/deactivate", response_model=FareConfigurationResponse)
def deactivate_fare_configuration(
    config_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_fleet_admin),
):
    """Deactivate a fare configuration."""
    config = db.execute(
        select(FareConfiguration)
        .where(
            FareConfiguration.id == config_id,
            FareConfiguration.organization_id == current_admin.organization_id
        )
    ).scalars().first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Fare configuration not found")

    config.is_active = False
    db.commit()
    db.refresh(config)

    svc = db.execute(
        select(Service).where(
            Service.organization_id == current_admin.organization_id,
            Service.fare_configuration_id == config.id,
        )
    ).scalars().first()

    return _enrich_fare_response(config, svc)


@router.post("/preview", response_model=FareCalculationResponse)
def preview_fare(
    request: FarePreviewRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Preview fare calculation between two stops using the active configuration."""
    try:
        result = FareCalculationService.calculate_fare(
            db=db,
            organization_id=current_admin.organization_id,
            service_id=request.service_id,
            origin_stop_id=request.origin_stop_id,
            destination_stop_id=request.destination_stop_id,
        )
        return result
    except FareCalculationError as e:
        raise HTTPException(status_code=400, detail=str(e))
