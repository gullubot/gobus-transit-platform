"""Add Step 8E Alert Status and Fingerprint

Revision ID: e78cf56eeed2
Revises: 7d0c318fee6a
Create Date: 2026-08-31 06:30:59.989335
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e78cf56eeed2'
down_revision: Union[str, None] = '7d0c318fee6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new Enum types if they don't exist (using a safe approach for postgres ENUMs)
    op.execute("CREATE TYPE alertstatus AS ENUM ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')")
    op.execute("CREATE TYPE alertseverity AS ENUM ('INFO', 'WARNING', 'CRITICAL')")

    # Add columns
    op.add_column('service_alerts', sa.Column('status', postgresql.ENUM('OPEN', 'ACKNOWLEDGED', 'RESOLVED', name='alertstatus', create_type=False), nullable=False, server_default='OPEN'))
    op.add_column('service_alerts', sa.Column('incident_fingerprint', sa.String(length=255), nullable=False, server_default='MIGRATED'))
    op.add_column('service_alerts', sa.Column('suggested_solution', sa.Text(), nullable=True))
    op.add_column('service_alerts', sa.Column('acknowledged_by', sa.UUID(), nullable=True))
    op.add_column('service_alerts', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))
    op.add_column('service_alerts', sa.Column('resolved_by', sa.UUID(), nullable=True))
    op.add_column('service_alerts', sa.Column('resolved_at', sa.DateTime(), nullable=True))

    # Convert existing severity (varchar) to Enum
    op.execute("ALTER TABLE service_alerts ALTER COLUMN severity TYPE alertseverity USING severity::alertseverity")

    # Create indices
    op.create_index(op.f('ix_service_alerts_incident_fingerprint'), 'service_alerts', ['incident_fingerprint'], unique=False)
    op.create_index(op.f('ix_service_alerts_status'), 'service_alerts', ['status'], unique=False)

    # Create Foreign Keys
    op.create_foreign_key('fk_service_alerts_acknowledged_by', 'service_alerts', 'users', ['acknowledged_by'], ['id'])
    op.create_foreign_key('fk_service_alerts_resolved_by', 'service_alerts', 'users', ['resolved_by'], ['id'])


def downgrade() -> None:
    # Drop Foreign Keys
    op.drop_constraint('fk_service_alerts_resolved_by', 'service_alerts', type_='foreignkey')
    op.drop_constraint('fk_service_alerts_acknowledged_by', 'service_alerts', type_='foreignkey')

    # Drop Indices
    op.drop_index(op.f('ix_service_alerts_status'), table_name='service_alerts')
    op.drop_index(op.f('ix_service_alerts_incident_fingerprint'), table_name='service_alerts')

    # Revert severity to varchar
    op.execute("ALTER TABLE service_alerts ALTER COLUMN severity TYPE VARCHAR(20) USING severity::VARCHAR")

    # Drop columns
    op.drop_column('service_alerts', 'resolved_at')
    op.drop_column('service_alerts', 'resolved_by')
    op.drop_column('service_alerts', 'acknowledged_at')
    op.drop_column('service_alerts', 'acknowledged_by')
    op.drop_column('service_alerts', 'suggested_solution')
    op.drop_column('service_alerts', 'incident_fingerprint')
    op.drop_column('service_alerts', 'status')

    # Drop Enum Types
    op.execute("DROP TYPE alertstatus")
    op.execute("DROP TYPE alertseverity")
