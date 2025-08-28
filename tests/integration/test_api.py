"""Integration tests for API endpoints."""
import pytest
from httpx import AsyncClient


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
