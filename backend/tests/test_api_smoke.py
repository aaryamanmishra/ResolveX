"""Smoke tests for FastAPI application and health endpoints."""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Verify /health returns 200 with demo mode configurations."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["service"] == "resolvex-api"
    assert data["demo_mode"] is True
    assert data["payment_provider"] == "simulator"
    assert data["model_provider"] == "stub"
    assert data["graph_engine"] == "memory"


def test_admin_model_health_endpoint() -> None:
    """Verify /api/v1/admin/model-health returns capability matrix."""
    response = client.get("/api/v1/admin/model-health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["provider"] == "stub"
    assert "text" in data["capabilities"]
    assert "image" in data["capabilities"]


def test_admin_graph_health_endpoint() -> None:
    """Verify /api/v1/admin/graph-health returns memory graph engine status."""
    response = client.get("/api/v1/admin/graph-health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["engine"] == "memory"


def test_openapi_schema_endpoint() -> None:
    """Verify OpenAPI documentation endpoint loads."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "ResolveX AI"
