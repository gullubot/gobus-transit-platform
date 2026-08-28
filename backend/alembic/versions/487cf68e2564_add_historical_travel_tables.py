"""Add historical travel tables

Revision ID: 487cf68e2564
Revises: 9b591141d0e9
Create Date: 2026-08-29 01:07:14.866624
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "487cf68e2564"
down_revision: Union[str, None] = "9b591141d0e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historical_route_travel",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("route_id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("time_of_day_bucket", sa.String(length=10), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("median_travel_seconds", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["routes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "route_id",
            "direction",
            "time_of_day_bucket",
            "day_of_week",
            name="uq_hist_route_org_route_dir_time_day",
        ),
    )
    op.create_index(
        "ix_hist_route_org_route",
        "historical_route_travel",
        ["organization_id", "route_id"],
        unique=False,
    )

    op.create_table(
        "historical_segment_travel",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("route_id", sa.UUID(), nullable=False),
        sa.Column("from_stop_id", sa.UUID(), nullable=False),
        sa.Column("to_stop_id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("time_of_day_bucket", sa.String(length=10), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("median_travel_seconds", sa.Integer(), nullable=False),
        sa.Column("median_destination_stop_dwell_seconds", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["from_stop_id"],
            ["stops.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["routes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_stop_id"],
            ["stops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "route_id",
            "direction",
            "from_stop_id",
            "to_stop_id",
            "time_of_day_bucket",
            "day_of_week",
            name="uq_hist_segment_org_route_dir_stops_time_day",
        ),
    )
    op.create_index(
        "ix_hist_seg_org_route_stops",
        "historical_segment_travel",
        ["organization_id", "route_id", "from_stop_id", "to_stop_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hist_seg_org_route_stops", table_name="historical_segment_travel")
    op.drop_table("historical_segment_travel")
    op.drop_index("ix_hist_route_org_route", table_name="historical_route_travel")
    op.drop_table("historical_route_travel")
