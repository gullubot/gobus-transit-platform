"""Add ETA to BusCurrentState

Revision ID: b37299935d4c
Revises: 128fd62846cc
Create Date: 2026-08-30 22:04:06.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = "b37299935d4c"
down_revision: Union[str, None] = "128fd62846cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bus_current_state", sa.Column("eta_seconds", sa.Integer(), nullable=True))
    op.add_column("bus_current_state", sa.Column("eta_status", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("bus_current_state", "eta_status")
    op.drop_column("bus_current_state", "eta_seconds")
