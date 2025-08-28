"""Integration tests for API endpoints."""

from unittest.mock import patch

import pytest


class TestChatEndpoints:
    """Test suite for chat API endpoints."""

    @pytest.mark.asyncio
    async def test_chat_completion_endpoint(
        self, async_http_client, sample_chat_request, auth_headers
    ):
        """Test POST /api/v1/chat/completions endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.post(
                "/api/v1/chat/completions", json=sample_chat_request, headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "choices" in data
            assert data["object"] == "chat.completion"

    @pytest.mark.asyncio
    async def test_streaming_chat_endpoint(
        self, async_http_client, sample_chat_request, auth_headers
    ):
        """Test streaming chat completion endpoint."""
        sample_chat_request["stream"] = True

        with patch("api.main.app") as mock_app:
            response = await async_http_client.post(
                "/api/v1/chat/completions", json=sample_chat_request, headers=auth_headers
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"

    @pytest.mark.asyncio
    async def test_chat_history_endpoint(self, async_http_client, auth_headers):
        """Test GET /api/v1/chat/history endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.get(
                "/api/v1/chat/history", headers=auth_headers, params={"limit": 10, "offset": 0}
            )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data

    @pytest.mark.asyncio
    async def test_delete_chat_endpoint(self, async_http_client, auth_headers):
        """Test DELETE /api/v1/chat/{chat_id} endpoint."""
        chat_id = "chat123"

        with patch("api.main.app") as mock_app:
            response = await async_http_client.delete(
                f"/api/v1/chat/{chat_id}", headers=auth_headers
            )

            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_model_switching_endpoint(self, async_http_client, auth_headers):
        """Test model switching in chat endpoint."""
        requests = [
            {"model": "gpt-4", "message": "Test with GPT-4"},
            {"model": "claude-3-opus", "message": "Test with Claude"},
            {"model": "llama-2-70b", "message": "Test with Llama"},
        ]

        with patch("api.main.app") as mock_app:
            for request_data in requests:
                response = await async_http_client.post(
                    "/api/v1/chat/completions", json=request_data, headers=auth_headers
                )

                assert response.status_code == 200


class TestWebSocketEndpoints:
    """Test suite for WebSocket endpoints."""

    @pytest.mark.asyncio
    async def test_websocket_connection(self, mock_websocket, auth_headers):
        """Test WebSocket connection establishment."""
        from fastapi.testclient import TestClient

        from api.main import app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/chat", headers=auth_headers) as websocket:
                websocket.send_json({"type": "ping"})
                data = websocket.receive_json()
                assert data["type"] == "pong"

    @pytest.mark.asyncio
    async def test_websocket_streaming(self, mock_websocket, sample_chat_request):
        """Test WebSocket message streaming."""
        from fastapi.testclient import TestClient

        from api.main import app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/chat") as websocket:
                websocket.send_json({"type": "chat", "data": sample_chat_request})

                chunks = []
                while True:
                    data = websocket.receive_json()
                    if data["type"] == "done":
                        break
                    chunks.append(data)

                assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, mock_websocket):
        """Test WebSocket error handling."""
        from fastapi.testclient import TestClient

        from api.main import app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/chat") as websocket:
                websocket.send_json({"type": "invalid", "data": {}})

                data = websocket.receive_json()
                assert data["type"] == "error"


class TestAuthenticationEndpoints:
    """Test suite for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_login_endpoint(self, async_http_client):
        """Test POST /api/v1/auth/login endpoint."""
        credentials = {"username": "testuser", "password": "testpass123"}

        with patch("api.main.app") as mock_app:
            response = await async_http_client.post("/api/v1/auth/login", json=credentials)

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_endpoint(self, async_http_client):
        """Test POST /api/v1/auth/refresh endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": "valid-refresh-token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data

    @pytest.mark.asyncio
    async def test_logout_endpoint(self, async_http_client, auth_headers):
        """Test POST /api/v1/auth/logout endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.post("/api/v1/auth/logout", headers=auth_headers)

            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_api_key_generation(self, async_http_client, auth_headers):
        """Test POST /api/v1/auth/api-keys endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.post(
                "/api/v1/auth/api-keys", json={"name": "Production Key"}, headers=auth_headers
            )

            assert response.status_code == 201
            data = response.json()
            assert "key" in data
            assert "id" in data


class TestTenantEndpoints:
    """Test suite for tenant management endpoints."""

    @pytest.mark.asyncio
    async def test_create_tenant(self, async_http_client, tenant_config, auth_headers):
        """Test POST /api/v1/tenants endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.post(
                "/api/v1/tenants", json=tenant_config, headers=auth_headers
            )

            assert response.status_code == 201
            data = response.json()
            assert data["tenant_id"] == tenant_config["tenant_id"]

    @pytest.mark.asyncio
    async def test_get_tenant(self, async_http_client, auth_headers):
        """Test GET /api/v1/tenants/{tenant_id} endpoint."""
        tenant_id = "tenant123"

        with patch("api.main.app") as mock_app:
            response = await async_http_client.get(
                f"/api/v1/tenants/{tenant_id}", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_update_tenant(self, async_http_client, auth_headers):
        """Test PUT /api/v1/tenants/{tenant_id} endpoint."""
        tenant_id = "tenant123"
        updates = {"tier": "enterprise", "status": "active"}

        with patch("api.main.app") as mock_app:
            response = await async_http_client.put(
                f"/api/v1/tenants/{tenant_id}", json=updates, headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["tier"] == "enterprise"

    @pytest.mark.asyncio
    async def test_tenant_usage(self, async_http_client, auth_headers):
        """Test GET /api/v1/tenants/{tenant_id}/usage endpoint."""
        tenant_id = "tenant123"

        with patch("api.main.app") as mock_app:
            response = await async_http_client.get(
                f"/api/v1/tenants/{tenant_id}/usage",
                headers=auth_headers,
                params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "total_requests" in data
            assert "total_tokens" in data


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_http_client):
        """Test GET /health endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_check(self, async_http_client):
        """Test GET /ready endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.get("/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["ready"] is True
            assert "database" in data["services"]
            assert "redis" in data["services"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, async_http_client):
        """Test GET /metrics endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.get("/metrics")

            assert response.status_code == 200
            assert "prometheus" in response.headers["content-type"]


class TestCacheEndpoints:
    """Test suite for cache management endpoints."""

    @pytest.mark.asyncio
    async def test_cache_stats(self, async_http_client, auth_headers):
        """Test GET /api/v1/cache/stats endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.get("/api/v1/cache/stats", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "hit_rate" in data
            assert "memory_usage_mb" in data

    @pytest.mark.asyncio
    async def test_cache_clear(self, async_http_client, auth_headers):
        """Test POST /api/v1/cache/clear endpoint."""
        with patch("api.main.app") as mock_app:
            response = await async_http_client.post("/api/v1/cache/clear", headers=auth_headers)

            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_cache_warmup(self, async_http_client, auth_headers):
        """Test POST /api/v1/cache/warmup endpoint."""
        warmup_data = [
            {"query": "What is AI?", "response": "AI is..."},
            {"query": "How does ML work?", "response": "ML works..."},
        ]

        with patch("api.main.app") as mock_app:
            response = await async_http_client.post(
                "/api/v1/cache/warmup", json=warmup_data, headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["warmed_entries"] == len(warmup_data)
