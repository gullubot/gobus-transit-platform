import os
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.user import User
from app.models.enums import UserRole
from app.services.operator_service import get_operator_assignment

# READ-ONLY connection to live database
engine = create_engine("postgresql://transit:transit_dev_password@db:5432/transit_platform")

with Session(engine) as session:
    users = session.execute(select(User).options(selectinload(User.operator_profile)).where(User.role.in_([UserRole.DRIVER, UserRole.CONDUCTOR]))).scalars().all()
    print("Found operators:", [(u.name, u.operator_profile.employee_code if u.operator_profile else None, u.role.value) for u in users])
    for u in users:
        emp_code = u.operator_profile.employee_code if u.operator_profile else "N/A"
        try:
            duty = get_operator_assignment(session, u)
            print(f"Operator {u.name} ({emp_code}) Assignment:")
            print(f"  Service: {duty.service_code} ({duty.service_name})")
            print(f"  Route: {duty.route_code} ({duty.route_name})")
            print(f"  Direction: {duty.direction}")
            print(f"  Vehicle: {duty.vehicle_number}")
            print(f"  Planned Start: {duty.planned_start_at}")
            print(f"  Status: {duty.assignment_status} / Trip: {duty.trip_status}")
        except Exception as e:
            print(f"Operator {u.name} ({emp_code}) has no duty: {e}")
