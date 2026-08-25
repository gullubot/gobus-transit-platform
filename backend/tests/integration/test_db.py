"""
Integration test for database connectivity.

Requires a running PostgreSQL instance.
Skipped if the database is not available.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import engine


@pytest.fixture
def db_connection():
    """Attempt to connect to the database, skip if unavailable."""
    try:
        conn = engine.connect()
        yield conn
        conn.close()
    except SQLAlchemyError:
        pytest.skip("Database not available — skipping integration test")


def test_database_connection(db_connection):
    """Verify that SQLAlchemy can execute a simple query."""
    result = db_connection.execute(text("SELECT 1 AS test"))
    row = result.fetchone()
    assert row is not None
    assert row[0] == 1


def test_postgis_extension(db_connection):
    """Verify that the PostGIS extension is enabled."""
    result = db_connection.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
    )
    row = result.fetchone()
    assert row is not None, "PostGIS extension is not enabled"
    assert row[0] == "postgis"
