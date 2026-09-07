"""add_passenger_role

Revision ID: 7d0c318fee6a
Revises: b37299935d4c
Create Date: 2026-08-30 22:35:25.123456

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7d0c318fee6a"
down_revision = "b37299935d4c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adding a value to a Postgres enum requires disabling transactions in Alembic
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'PASSENGER'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type easily.
    # We leave this blank (or could rename type, recreate, etc., but not worth it for minimal migration).
    pass
