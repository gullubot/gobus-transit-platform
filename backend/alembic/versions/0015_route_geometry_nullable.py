"""route_geometry_nullable

Revision ID: 0015_route_geometry_nullable
Revises: 0014_add_city_and_stop_aliases
Create Date: 2026-09-04 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = '0015_route_geometry_nullable'
down_revision: Union[str, None] = '0014_add_city_and_stop_aliases'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('routes', 'geometry', nullable=True)


def downgrade() -> None:
    op.alter_column('routes', 'geometry', nullable=False)
