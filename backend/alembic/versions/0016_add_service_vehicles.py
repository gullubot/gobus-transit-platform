"""add_service_vehicles

Revision ID: 0016_add_service_vehicles
Revises: 0015_route_geometry_nullable
Create Date: 2026-09-06 01:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '0016_add_service_vehicles'
down_revision: Union[str, None] = '0015_route_geometry_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_vehicles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("service_id", "vehicle_id", name="uq_service_vehicles_service_vehicle"),
        sa.ForeignKeyConstraint(
            ["organization_id", "service_id"],
            ["services.organization_id", "services.id"],
            name="fk_service_vehicles_org_service",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "vehicle_id"],
            ["vehicles.organization_id", "vehicles.id"],
            name="fk_service_vehicles_org_vehicle",
        ),
    )
    op.create_index("ix_service_vehicles_organization_id", "service_vehicles", ["organization_id"])
    op.create_index("ix_service_vehicles_service_id", "service_vehicles", ["service_id"])
    op.create_index("ix_service_vehicles_vehicle_id", "service_vehicles", ["vehicle_id"])


def downgrade() -> None:
    op.drop_index("ix_service_vehicles_vehicle_id", table_name="service_vehicles")
    op.drop_index("ix_service_vehicles_service_id", table_name="service_vehicles")
    op.drop_index("ix_service_vehicles_organization_id", table_name="service_vehicles")
    op.drop_table("service_vehicles")
