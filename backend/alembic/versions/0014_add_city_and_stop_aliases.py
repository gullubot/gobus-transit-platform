"""add_city_and_stop_aliases

Revision ID: 0014_add_city_and_stop_aliases
Revises: 9282670f0330
Create Date: 2026-09-04 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0014_add_city_and_stop_aliases'
down_revision: Union[str, None] = '9282670f0330'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add city column to organizations
    op.add_column('organizations', sa.Column('city', sa.String(length=100), nullable=True))
    
    # Populate existing organization(s) with 'Kolkata'
    op.execute("UPDATE organizations SET city = 'Kolkata' WHERE city IS NULL")
    
    # Enforce NOT NULL without hardcoding a database-level server_default for all future orgs
    op.alter_column('organizations', 'city', nullable=False)
    op.create_index('ix_organizations_city', 'organizations', ['city'], unique=False)

    # 2. Create stop_aliases table
    op.create_table(
        'stop_aliases',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('stop_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('alias_name', sa.String(length=255), nullable=False),
        sa.Column('alias_type', sa.String(length=50), server_default='LOCAL_NAME', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stop_id'], ['stops.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_stop_aliases_stop_id', 'stop_aliases', ['stop_id'], unique=False)
    op.create_index('ix_stop_aliases_org_name', 'stop_aliases', ['organization_id', 'alias_name'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_stop_aliases_org_name', table_name='stop_aliases')
    op.drop_index('ix_stop_aliases_stop_id', table_name='stop_aliases')
    op.drop_table('stop_aliases')
    
    op.drop_index('ix_organizations_city', table_name='organizations')
    op.drop_column('organizations', 'city')
