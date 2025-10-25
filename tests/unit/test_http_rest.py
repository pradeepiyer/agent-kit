"""Test REST API endpoints for HTTP server."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(test_app: Any) -> TestClient:
    """Create test client for FastAPI app."""
    return TestClient(test_app)


def test_health_and_info_endpoints(client: TestClient) -> None:
    """Health and info endpoints return correct responses."""
    # Test health endpoint
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data

    # Test info endpoint
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["api_version"] == "v1"
    # Check that hello agent is in the agents list
    agent_names = [agent["name"] for agent in data["agents"]]
    assert "hello" in agent_names


def test_session_lifecycle(client: TestClient) -> None:
    """Session create, get, and delete work correctly."""
    # Create session
    response = client.post("/api/v1/sessions")
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    session_id = data["session_id"]

    # Get session info
    response = client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "created_at" in data
    assert "last_accessed" in data
    assert isinstance(data["active_agents"], list)

    # Delete session
    response = client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 204

    # Verify session no longer exists
    response = client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 404


def test_nonexistent_session_returns_404(client: TestClient) -> None:
    """Getting nonexistent session returns 404."""
    response = client.get("/api/v1/sessions/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_agent_execution_endpoint_exists(client: TestClient) -> None:
    """Agent execution endpoint is registered."""
    # The /hello endpoint should exist (even if validation fails without proper request)
    # This test verifies the dynamic route registration works
    # Full streaming test would require more complex mocking of the agent and SSE

    # Verify endpoint exists by checking it's in the routes
    routes = [route.path for route in client.app.routes]  # type: ignore
    assert "/api/v1/hello" in routes


def test_invalid_agent_name_returns_404(client: TestClient) -> None:
    """Requesting invalid agent returns 404."""
    response = client.post("/api/v1/invalid_agent", json={"query": "test"})
    assert response.status_code == 404
