"""API test suite."""
import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_health_check():
    """Test health endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_endpoint():
    """Test chat completion endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "Hello"}]},
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_websocket():
    """Test WebSocket connection."""
    # WebSocket testing requires different approach with httpx
    # Skipping for now as httpx doesn't directly support WebSocket testing
    pytest.skip("WebSocket testing requires starlette TestClient")
