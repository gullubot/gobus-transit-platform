

def get_candidate_segments_query() -> str:
    """
    Returns the PostGIS SQL query to retrieve candidate route segments.
    This executes spatial candidate generation in the database using ST_DWithin
    and ST_DumpSegments, avoiding O(N) Python iteration over the entire route geometry.

    Expected Bind Parameters:
    - lon: float
    - lat: float
    - search_radius_m: float
    """
    return """
    WITH route_segments AS (
        SELECT
            id AS route_id,
            (ST_DumpSegments(geometry)).path[1] - 1 AS segment_index,
            (ST_DumpSegments(geometry)).geom AS geom
        FROM routes
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :search_radius_m
        )
    )
    SELECT
        route_id,
        segment_index,
        ST_Y(ST_StartPoint(geom)) AS start_lat,
        ST_X(ST_StartPoint(geom)) AS start_lon,
        ST_Y(ST_EndPoint(geom)) AS end_lat,
        ST_X(ST_EndPoint(geom)) AS end_lon,
        ST_Length(ST_LineSubstring(routes.geometry, 0,
        ST_LineLocatePoint(routes.geometry,
        ST_StartPoint(route_segments.geom)))::geography) AS segment_progress_start_m
    FROM route_segments
    JOIN routes ON routes.id = route_segments.route_id
    WHERE ST_DWithin(
        geom::geography,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :search_radius_m
    );
    """
