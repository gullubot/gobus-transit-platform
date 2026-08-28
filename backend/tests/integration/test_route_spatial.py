import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import ORG_ID
from app.repositories.route_spatial import get_candidate_segments_query


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session


def test_spatial_query_uses_meters_and_returns_segments(db: Session):
    # Setup test table or just use raw query execution with a mock routes table / CTE
    # Since we can't easily modify the real routes table without affecting other tests,
    # we'll execute the logic directly using PostGIS functions.
    # The prompt asked to test "radius = 50m does NOT behave as 50 degrees" against real DB.
    # We will test the core PostGIS concepts used in route_spatial.py.

    # 1 degree of latitude is ~111km.
    # 50 degrees would be ~5550km!
    # If the radius is evaluated in meters, a point 1 degree away (111km) should NOT match a 50 radius query.  # noqa: E501
    # If it was evaluated in degrees, a point 1 degree away WOULD match a 50 radius query.

    query = text("""
        SELECT ST_DWithin(
            ST_SetSRID(ST_MakePoint(77.0, 12.0), 4326)::geography,
            ST_SetSRID(ST_MakePoint(77.0, 13.0), 4326)::geography,
            50.0
        ) as is_within;
    """)
    result = db.execute(query).scalar()

    # It must be false! 1 degree is ~111,000 meters.
    # If radius was in degrees, 1 < 50, so it would be true.
    assert result is False, "ST_DWithin with ::geography is evaluating in degrees, not meters!"

    # Check that 50m actually works for something 40m away.
    # 1 degree lat = 111,320m. 40m = 40 / 111320 = 0.000359 degrees.
    query_close = text("""
        SELECT ST_DWithin(
            ST_SetSRID(ST_MakePoint(77.0, 12.0), 4326)::geography,
            ST_SetSRID(ST_MakePoint(77.0, 12.000359), 4326)::geography,
            50.0
        ) as is_within;
    """)
    result_close = db.execute(query_close).scalar()
    assert result_close is True, "50m radius should match a point 40m away!"

    # Now verify the actual get_candidate_segments_query mechanism.
    # We will wrap it in a transaction that inserts a temporary route and queries it.
    db.execute(text("SAVEPOINT test_route_spatial"))
    try:
        # Create a route with a 3-point linestring
        # Total length: (77.0, 12.0) to (77.0, 12.001) is ~111m.
        # (77.0, 12.001) to (77.0, 12.002) is another ~111m.
        db.execute(
            text(f"""
            INSERT INTO routes (id, organization_id, route_code,
            route_name, geometry, status, created_at, updated_at)
            VALUES (
                gen_random_uuid(),
                '{ORG_ID}',
                'TEST-SPATIAL',
                'Spatial Test Route',
                ST_GeomFromText('LINESTRING(77.0 12.0, 77.0 12.001, 77.0 12.002)', 4326),
                'ACTIVE', now(), now()
            ) RETURNING id
        """)
        ).scalar()

        # Execute the candidate query
        candidate_query = text(get_candidate_segments_query())

        # Test 1: Near the first segment, 50m radius.
        # Point at 12.0005, 77.0
        res = (
            db.execute(candidate_query, {"lon": 77.0, "lat": 12.0005, "search_radius_m": 50.0})
            .mappings()
            .all()
        )

        # Should return both segments because the point (12.0005) is ~55m from the ends of both segments,  # noqa: E501
        # but the distance to the LINESTRING segment itself is 0m!
        # Both segments touch the point, so distance to both is 0m. Wait, segment 0 ends at 12.001. Segment 1 starts at 12.001.  # noqa: E501
        # Point is at 12.0005. Distance to segment 0 is 0m.
        # Distance to segment 1 (starts at 12.001) is ~55m.
        # Wait, if search_radius is 50.0m, segment 1 is >50m away.

        assert len(res) == 1
        assert res[0]["segment_index"] == 0
        assert res[0]["start_lon"] == 77.0
        assert res[0]["start_lat"] == 12.0
        assert res[0]["end_lon"] == 77.0
        assert res[0]["end_lat"] == 12.001
        assert res[0]["segment_progress_start_m"] == 0.0

        # Test 2: Near the second segment.
        res2 = (
            db.execute(candidate_query, {"lon": 77.0, "lat": 12.0015, "search_radius_m": 50.0})
            .mappings()
            .all()
        )
        assert len(res2) == 1
        assert res2[0]["segment_index"] == 1
        # It's the second segment, so progress start is length of first segment (~111m)
        assert res2[0]["segment_progress_start_m"] > 110.0
        assert res2[0]["segment_progress_start_m"] < 112.0

    finally:
        db.execute(text("ROLLBACK TO SAVEPOINT test_route_spatial"))
