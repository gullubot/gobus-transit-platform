"""
Tests for health check endpoints.

BUILD 0: Infrastructure-only tests.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    """GET /health returns status ok and correct service name."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "transit-backend"


def test_health_db_returns_response():
    """
    GET /health/db returns a response (connected or disconnected).

    This test verifies the endpoint works structurally.
    The actual database may or may not be available during unit tests.
    """
    response = client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["status"] in ("ok", "error")
