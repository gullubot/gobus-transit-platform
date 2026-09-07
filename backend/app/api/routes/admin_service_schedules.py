import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.models.service import Service, ServiceSchedule
from app.models.user import User
from app.schemas.admin_network import (
    AdminServiceScheduleCreate,
    AdminServiceScheduleResponse,
    AdminServiceScheduleUpdate,
)

router = APIRouter()


def _get_service_or_404(db: Session, org_id: uuid.UUID, service_id: uuid.UUID) -> Service:
    service = db.scalars(
        select(Service).where(
            Service.id == service_id,
            Service.organization_id == org_id,
        )
    ).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service not found or unauthorized."
        )
    return service


def _get_schedule_or_404(
    db: Session, org_id: uuid.UUID, service_id: uuid.UUID, schedule_id: uuid.UUID
) -> ServiceSchedule:
    # First ensure the service belongs to the org
    _get_service_or_404(db, org_id, service_id)

    schedule = db.scalars(
        select(ServiceSchedule).where(
            ServiceSchedule.id == schedule_id,
            ServiceSchedule.service_id == service_id,
        )
    ).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found or unauthorized."
        )
    return schedule


@router.get("/{service_id}/schedules", response_model=List[AdminServiceScheduleResponse])
def get_service_schedules(
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    List all schedules for a specific service.
    """
    _get_service_or_404(db, current_admin.organization_id, service_id)
    schedules = db.scalars(
        select(ServiceSchedule)
        .where(ServiceSchedule.service_id == service_id)
        .order_by(ServiceSchedule.direction, ServiceSchedule.start_time)
    ).all()
    return schedules


@router.post(
    "/{service_id}/schedules",
    response_model=AdminServiceScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_schedule(
    service_id: uuid.UUID,
    schedule_in: AdminServiceScheduleCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    Create a new service schedule.
    """
    _get_service_or_404(db, current_admin.organization_id, service_id)
    
    # We could add more complex overlapping validation here, but for MVP
    # we just trust the admin or rely on DB constraints if any.

    schedule = ServiceSchedule(
        service_id=service_id,
        direction=schedule_in.direction,
        start_time=schedule_in.start_time,
        end_time=schedule_in.end_time,
        typical_interval_minutes=schedule_in.typical_interval_minutes,
        days_of_week=schedule_in.days_of_week,
        effective_from=schedule_in.effective_from,
        effective_until=schedule_in.effective_until,
        status=schedule_in.status,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/{service_id}/schedules/{schedule_id}", response_model=AdminServiceScheduleResponse)
def get_service_schedule(
    service_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    Get a specific service schedule by ID.
    """
    return _get_schedule_or_404(db, current_admin.organization_id, service_id, schedule_id)


@router.put("/{service_id}/schedules/{schedule_id}", response_model=AdminServiceScheduleResponse)
def update_service_schedule(
    service_id: uuid.UUID,
    schedule_id: uuid.UUID,
    schedule_in: AdminServiceScheduleUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Any:
    """
    Update a service schedule.
    """
    schedule = _get_schedule_or_404(db, current_admin.organization_id, service_id, schedule_id)

    update_data = schedule_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{service_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_service_schedule(
    service_id: uuid.UUID,
    schedule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Delete a service schedule.
    """
    schedule = _get_schedule_or_404(db, current_admin.organization_id, service_id, schedule_id)
    db.delete(schedule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
