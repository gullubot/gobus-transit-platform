"""add_fare_configuration_id_to_services

Revision ID: 9282670f0330
Revises: 6abc9ee3c967
Create Date: 2026-08-31 17:27:39.526685
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9282670f0330'
down_revision: Union[str, None] = '6abc9ee3c967'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the unique constraint that enforces only one active configuration per org
    # Note: Alembic creates this as an index in postgres with a WHERE clause
    op.drop_index('uq_fare_configs_org_active', table_name='fare_configurations', postgresql_where='(is_active = true)')
    
    # Add fare_configuration_id to services
    op.add_column('services', sa.Column('fare_configuration_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_services_fare_configuration_id'), 'services', ['fare_configuration_id'], unique=False)
    op.create_foreign_key('fk_services_fare_configuration_id', 'services', 'fare_configurations', ['fare_configuration_id'], ['id'])


def downgrade() -> None:
    # Remove the column and its constraints
    op.drop_constraint('fk_services_fare_configuration_id', 'services', type_='foreignkey')
    op.drop_index(op.f('ix_services_fare_configuration_id'), table_name='services')
    op.drop_column('services', 'fare_configuration_id')
    
    # Recreate the unique constraint
    op.create_index('uq_fare_configs_org_active', 'fare_configurations', ['organization_id'], unique=True, postgresql_where='(is_active = true)')
