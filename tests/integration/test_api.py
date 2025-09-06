"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from chatbot_ai_system.server.main import app

client = TestClient(app)


class TestAPIEndpoints:
    """Test API endpoint integration."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: AsyncClient):
        """Test health check endpoint."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_create_chat_completion(self, async_client: AsyncClient, auth_headers):
        """Test chat completion endpoint."""
        response = await async_client.post(
            "/api/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "choices" in response.json()

    @pytest.mark.asyncio
    async def test_websocket_connection(self, async_client: AsyncClient):
        """Test WebSocket connection."""
        with async_client.websocket_connect("/api/v1/ws") as websocket:
            await websocket.send_json({"message": "test"})
            data = await websocket.receive_json()
            assert "response" in data


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_api_docs():
    """Test API documentation is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_schema():
    """Test OpenAPI schema is accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_invalid_endpoint():
    """Test invalid endpoint returns 404."""
    response = client.get("/invalid")
    assert response.status_code == 404