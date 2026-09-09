"""Integration tests for API endpoints (in-process, no network, no keys).

Uses the memory-cache fallback and ``fake_chat_provider`` so the app is fully healthy
under test. See docs/TEST_TRIAGE.md for why each test looks the way it does.
"""

import pytest

# Models that exist in the current catalogue (providers/catalog.py), one per provider.
CATALOGUE_MODELS = ["gpt-4o-mini", "claude-3-5-haiku-latest", "openai/gpt-oss-20b"]


class TestChatEndpoints:
    """Test suite for chat API endpoints."""

    @pytest.mark.asyncio
    async def test_chat_completion_endpoint(
        self, async_http_client, sample_chat_request, auth_headers, fake_chat_provider
    ):
        """Test POST /api/v1/chat/completions endpoint."""
        response = await async_http_client.post(
            "/api/v1/chat/completions", json=sample_chat_request, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "choices" in data
        assert data["object"] == "chat.completion"
        assert data["provider"] == "openai"  # the chain slot the fake provider was installed in
        assert data["attempts"][0]["outcome"] == "ok"
        assert data["telemetry"]["cache"]["status"] in ("miss", "hit")

    @pytest.mark.asyncio
    async def test_streaming_chat_endpoint(
        self, async_http_client, sample_chat_request, auth_headers, fake_chat_provider
    ):
        """stream=true answers as Server-Sent Events ending with a done event."""
        sample_chat_request["stream"] = True

        response = await async_http_client.post(
            "/api/v1/chat/completions", json=sample_chat_request, headers=auth_headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.startswith("event: meta")
        assert "event: delta" in response.text
        assert response.text.rstrip().split("\n\n")[-1].startswith("event: done")

    @pytest.mark.asyncio
    async def test_model_switching_endpoint(
        self, async_http_client, auth_headers, fake_chat_provider
    ):
        """Every catalogued provider's model is accepted and echoed back."""
        for model in CATALOGUE_MODELS:
            response = await async_http_client.post(
                "/api/v1/chat/completions",
                json={"model": model, "messages": [{"role": "user", "content": f"Test {model}"}]},
                headers=auth_headers,
            )

            assert response.status_code == 200, response.text
            assert response.json()["model"] == model


def _receive(websocket) -> dict:
    """Next application message, skipping server heartbeat pings (type 'ping')."""
    while True:
        data = websocket.receive_json()
        if data["type"] != "ping":
            return data


def _read_greetings(websocket) -> dict:
    """The server greets twice: WebSocketManager sends 'connection', the endpoint 'connected'.

    Returns the 'connected' message (it carries the connection_id).
    """
    first, second = _receive(websocket), _receive(websocket)
    assert {first["type"], second["type"]} == {"connection", "connected"}, (first, second)
    return first if first["type"] == "connected" else second


class TestWebSocketEndpoints:
    """Test suite for the /ws/chat protocol (see websocket/ws_handlers.py MessageType)."""

    def test_websocket_connection(self, auth_headers):
        """Server greets with 'connected', then answers ping with pong."""
        from chatbot_ai_system.main import app
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            with client.websocket_connect("/ws/chat", headers=auth_headers) as websocket:
                greeting = _read_greetings(websocket)
                assert "connection_id" in greeting

                websocket.send_json({"type": "ping"})
                data = _receive(websocket)
                assert data["type"] == "pong"

    def test_websocket_streaming(self, fake_chat_provider):
        """A chat message streams 'stream' chunks and ends with 'complete'."""
        from chatbot_ai_system.main import app
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            with client.websocket_connect("/ws/chat") as websocket:
                _read_greetings(websocket)
                websocket.send_json(
                    {
                        "type": "chat",
                        "data": {"message": "Hello", "model": "gpt-4o-mini", "stream": True},
                    }
                )

                chunks = []
                while True:
                    data = _receive(websocket)
                    if data["type"] in ("complete", "error"):
                        final = data
                        break
                    chunks.append(data)

                assert final["type"] == "complete", final
                # 'status' ("Request received") precedes the stream; only 'stream' carries text.
                assert all(c["type"] in ("stream", "status") for c in chunks), chunks
                stream_chunks = [c for c in chunks if c["type"] == "stream"]
                assert stream_chunks
                assert "".join(c["data"]["chunk"] for c in stream_chunks).strip() == (
                    fake_chat_provider.reply
                )
                assert final["data"]["full_response"].strip() == fake_chat_provider.reply

    def test_websocket_error_handling(self):
        """An unknown message type yields a typed error, not a dropped connection."""
        from chatbot_ai_system.main import app
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            with client.websocket_connect("/ws/chat") as websocket:
                _read_greetings(websocket)
                websocket.send_json({"type": "invalid", "data": {}})

                data = _receive(websocket)
                assert data["type"] == "error"


class TestAuthenticationEndpoints:
    """Test suite for authentication endpoints (mock auth service)."""

    CREDENTIALS = {"username": "testuser", "password": "testpass123"}

    @pytest.mark.asyncio
    async def test_login_endpoint(self, async_http_client):
        """Test POST /api/v1/auth/login endpoint."""
        response = await async_http_client.post("/api/v1/auth/login", json=self.CREDENTIALS)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.xfail(
        strict=True,
        reason="login builds a refresh_token but AuthResponse drops it; see TEST_TRIAGE escalation",
    )
    @pytest.mark.asyncio
    async def test_login_returns_refresh_token(self, async_http_client):
        response = await async_http_client.post("/api/v1/auth/login", json=self.CREDENTIALS)
        assert "refresh_token" in response.json()

    @pytest.mark.asyncio
    async def test_refresh_token_endpoint(self, async_http_client):
        """Refresh takes the bearer token from login, not a JSON body."""
        login = await async_http_client.post("/api/v1/auth/login", json=self.CREDENTIALS)
        token = login.json()["access_token"]

        response = await async_http_client.post(
            "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_logout_endpoint(self, async_http_client, auth_headers):
        """Test POST /api/v1/auth/logout endpoint."""
        response = await async_http_client.post("/api/v1/auth/logout", headers=auth_headers)

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_api_key_generation(self, async_http_client, auth_headers):
        """Test POST /api/v1/auth/api-keys endpoint."""
        response = await async_http_client.post(
            "/api/v1/auth/api-keys", json={"name": "Production Key"}, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["key"].startswith("sk-")
        assert "name" in data


class TestTenantEndpoints:
    """Test suite for tenant endpoints (in-memory stub: tenant-1 and tenant-2 exist)."""

    @pytest.mark.asyncio
    async def test_create_tenant(self, async_http_client, auth_headers):
        """POST /api/v1/tenants/ takes query parameters and returns 201."""
        response = await async_http_client.post(
            "/api/v1/tenants/",
            params={"name": "Acme", "rate_limit": 1000, "rate_period": 60},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Acme"
        assert data["rate_limit"] == 1000
        assert data["id"].startswith("tenant-")

    @pytest.mark.asyncio
    async def test_get_tenant(self, async_http_client, auth_headers):
        """Test GET /api/v1/tenants/{tenant_id} endpoint."""
        tenant_id = "tenant-1"

        response = await async_http_client.get(f"/api/v1/tenants/{tenant_id}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == tenant_id

    @pytest.mark.asyncio
    async def test_get_unknown_tenant_is_404(self, async_http_client, auth_headers):
        response = await async_http_client.get("/api/v1/tenants/nope", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_tenant(self, async_http_client, auth_headers):
        """Test PUT /api/v1/tenants/{tenant_id} endpoint."""
        tenant_id = "tenant-1"

        response = await async_http_client.put(
            f"/api/v1/tenants/{tenant_id}",
            params={"name": "Renamed", "rate_limit": 500},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed"
        assert data["rate_limit"] == 500

class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_http_client):
        """Test GET /health endpoint."""
        response = await async_http_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["checks"]["cache"] in ("memory", "redis")

    @pytest.mark.asyncio
    async def test_readiness_check(self, async_http_client):
        """Readiness probe lives at /api/v1/health/ready (was /ready)."""
        response = await async_http_client.get("/api/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "database" in data["components"]
        assert "redis" in data["components"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, async_http_client):
        """/metrics is Prometheus exposition (TEST_TRIAGE escalation 4, resolved)."""
        response = await async_http_client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "http_requests_total" in response.text
        assert "cache_hits_total" in response.text


class TestCacheEndpoints:
    """Test suite for the /api/v1/cache admin router."""

    @pytest.mark.asyncio
    async def test_cache_stats(self, async_http_client, auth_headers):
        """Test GET /api/v1/cache/stats endpoint."""
        response = await async_http_client.get("/api/v1/cache/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "hit_rate" in data
        assert "hits" in data and "misses" in data

    @pytest.mark.asyncio
    async def test_cache_clear(self, async_http_client, auth_headers):
        """Test POST /api/v1/cache/clear endpoint."""
        response = await async_http_client.post("/api/v1/cache/clear", headers=auth_headers)

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_cache_warmup(self, async_http_client, auth_headers):
        """POST /api/v1/cache/warm takes a list of keys and reports how many it warmed."""
        keys = ["What is AI?", "How does ML work?"]

        response = await async_http_client.post(
            "/api/v1/cache/warm", json=keys, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["warmed"] == len(keys)
        assert data["status"] == "completed"
