"""historical tenant isolation

Revision ID: 4fb7c61b0007
Revises: 487cf68e2564
Create Date: 2026-08-29 01:22:53.538633
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4fb7c61b0007"
down_revision: Union[str, None] = "487cf68e2564"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add composite unique constraint to stops
    op.create_unique_constraint("uq_stops_id_org", "stops", ["id", "organization_id"])

    # 2. Drop weak historical FKs
    op.drop_constraint(
        "historical_route_travel_route_id_fkey",
        "historical_route_travel",
        type_="foreignkey",
    )
    op.drop_constraint(
        "historical_segment_travel_route_id_fkey",
        "historical_segment_travel",
        type_="foreignkey",
    )
    op.drop_constraint(
        "historical_segment_travel_from_stop_id_fkey",
        "historical_segment_travel",
        type_="foreignkey",
    )
    op.drop_constraint(
        "historical_segment_travel_to_stop_id_fkey",
        "historical_segment_travel",
        type_="foreignkey",
    )

    # 3. Add organization-aware composite historical FKs
    op.create_foreign_key(
        "fk_hist_route_org_route",
        "historical_route_travel",
        "routes",
        ["organization_id", "route_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_hist_segment_org_route",
        "historical_segment_travel",
        "routes",
        ["organization_id", "route_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_hist_segment_org_from_stop",
        "historical_segment_travel",
        "stops",
        ["organization_id", "from_stop_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_hist_segment_org_to_stop",
        "historical_segment_travel",
        "stops",
        ["organization_id", "to_stop_id"],
        ["organization_id", "id"],
    )


def downgrade() -> None:
    # 1. Drop organization-aware composite historical FKs
    op.drop_constraint(
        "fk_hist_segment_org_to_stop",
        "historical_segment_travel",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_hist_segment_org_from_stop",
        "historical_segment_travel",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_hist_segment_org_route",
        "historical_segment_travel",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_hist_route_org_route",
        "historical_route_travel",
        type_="foreignkey",
    )

    # 2. Re-add weak historical FKs
    op.create_foreign_key(
        "historical_segment_travel_to_stop_id_fkey",
        "historical_segment_travel",
        "stops",
        ["to_stop_id"],
        ["id"],
    )
    op.create_foreign_key(
        "historical_segment_travel_from_stop_id_fkey",
        "historical_segment_travel",
        "stops",
        ["from_stop_id"],
        ["id"],
    )
    op.create_foreign_key(
        "historical_segment_travel_route_id_fkey",
        "historical_segment_travel",
        "routes",
        ["route_id"],
        ["id"],
    )
    op.create_foreign_key(
        "historical_route_travel_route_id_fkey",
        "historical_route_travel",
        "routes",
        ["route_id"],
        ["id"],
    )

    # 3. Drop composite unique constraint from stops
    op.drop_constraint("uq_stops_id_org", "stops", type_="unique")
