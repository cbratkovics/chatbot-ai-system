"""End-to-end tests for user journey."""

import asyncio
import json
import time

import pytest
from httpx import AsyncClient
from websockets import connect


class TestUserJourney:
    """Test suite for complete user journey."""

    @pytest.mark.asyncio
    async def test_complete_user_onboarding(self):
        """Test complete user onboarding flow."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            registration_data = {
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "company": "Test Corp",
                "plan": "enterprise",
            }
            response = await client.post("/api/v1/auth/register", json=registration_data)
            assert response.status_code == 201
            user_data = response.json()

            login_data = {
                "username": registration_data["email"],
                "password": registration_data["password"],
            }
            response = await client.post("/api/v1/auth/login", json=login_data)
            assert response.status_code == 200
            tokens = response.json()

            headers = {"Authorization": f"Bearer {tokens['access_token']}"}

            response = await client.get("/api/v1/user/profile", headers=headers)
            assert response.status_code == 200
            profile = response.json()
            assert profile["email"] == registration_data["email"]

            api_key_data = {"name": "Production API Key"}
            response = await client.post(
                "/api/v1/auth/api-keys", json=api_key_data, headers=headers
            )
            assert response.status_code == 201
            api_key = response.json()

            test_message = {"message": "Hello, AI!", "model": "gpt-4"}
            response = await client.post(
                "/api/v1/chat/completions", json=test_message, headers={"X-API-Key": api_key["key"]}
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_conversation_flow(self):
        """Test complete chat conversation flow."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"Authorization": "Bearer test-token"}

            session_response = await client.post("/api/v1/chat/sessions", headers=headers)
            session = session_response.json()
            session_id = session["session_id"]

            messages = [
                "Hello, I need help with Python programming",
                "Can you explain decorators?",
                "Show me an example of a decorator",
                "How do I use functools.wraps?",
                "Thanks for the help!",
            ]

            conversation_history = []

            for message in messages:
                request_data = {"message": message, "session_id": session_id, "model": "gpt-4"}

                response = await client.post(
                    "/api/v1/chat/completions", json=request_data, headers=headers
                )

                assert response.status_code == 200
                chat_response = response.json()

                conversation_history.append(
                    {
                        "user": message,
                        "assistant": chat_response["choices"][0]["message"]["content"],
                    }
                )

                await asyncio.sleep(0.5)

            history_response = await client.get(
                f"/api/v1/chat/sessions/{session_id}/history", headers=headers
            )
            assert history_response.status_code == 200
            history = history_response.json()
            assert len(history["messages"]) == len(messages) * 2

    @pytest.mark.asyncio
    async def test_websocket_streaming_journey(self):
        """Test WebSocket streaming user journey."""
        uri = "ws://localhost:8000/ws/chat"
        token = "test-token"

        async with connect(uri, extra_headers={"Authorization": f"Bearer {token}"}) as websocket:
            await websocket.send(json.dumps({"type": "auth", "token": token}))
            auth_response = await websocket.recv()
            assert json.loads(auth_response)["type"] == "auth_success"

            questions = [
                "Write a short story about a robot",
                "Continue the story",
                "How does it end?",
            ]

            for question in questions:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "chat",
                            "data": {"message": question, "stream": True, "model": "gpt-4"},
                        }
                    )
                )

                full_response = []
                while True:
                    chunk = await websocket.recv()
                    data = json.loads(chunk)

                    if data["type"] == "stream_end":
                        break
                    elif data["type"] == "stream_chunk":
                        full_response.append(data["content"])

                assert len("".join(full_response)) > 0
                await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_multi_model_comparison_journey(self):
        """Test multi-model comparison user journey."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"Authorization": "Bearer test-token"}

            prompt = "Explain quantum computing in simple terms"
            models = ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"]

            responses = {}
            latencies = {}

            for model in models:
                start_time = time.time()

                response = await client.post(
                    "/api/v1/chat/completions",
                    json={"message": prompt, "model": model},
                    headers=headers,
                )

                latencies[model] = (time.time() - start_time) * 1000

                assert response.status_code == 200
                responses[model] = response.json()

            comparison_request = {
                "responses": responses,
                "criteria": ["accuracy", "clarity", "completeness"],
            }

            comparison = await client.post(
                "/api/v1/analysis/compare", json=comparison_request, headers=headers
            )

            assert comparison.status_code == 200
            results = comparison.json()
            assert "rankings" in results
            assert all(model in results["rankings"] for model in models)

    @pytest.mark.asyncio
    async def test_cache_optimization_journey(self):
        """Test cache optimization user journey."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"Authorization": "Bearer test-token"}

            similar_questions = [
                "What is machine learning?",
                "Can you explain machine learning?",
                "Tell me about machine learning",
                "How does machine learning work?",
                "Machine learning explanation please",
            ]

            first_response = None
            cache_hits = 0

            for i, question in enumerate(similar_questions):
                start_time = time.time()

                response = await client.post(
                    "/api/v1/chat/completions",
                    json={"message": question, "model": "gpt-4"},
                    headers=headers,
                )

                latency = (time.time() - start_time) * 1000

                assert response.status_code == 200
                data = response.json()

                if i == 0:
                    first_response = data
                    assert latency > 50
                else:
                    if data.get("cached", False):
                        cache_hits += 1
                        assert latency < 50

            assert cache_hits >= 3

            cache_stats = await client.get("/api/v1/cache/stats", headers=headers)
            assert cache_stats.status_code == 200
            stats = cache_stats.json()
            assert stats["hit_rate"] > 0.3

    @pytest.mark.asyncio
    async def test_rate_limiting_journey(self):
        """Test rate limiting user journey."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"Authorization": "Bearer test-token"}

            requests_made = 0
            rate_limited = False

            for i in range(150):
                response = await client.post(
                    "/api/v1/chat/completions",
                    json={"message": f"Request {i}", "model": "gpt-4"},
                    headers=headers,
                )

                requests_made += 1

                if response.status_code == 429:
                    rate_limited = True
                    rate_limit_headers = response.headers
                    assert "X-RateLimit-Limit" in rate_limit_headers
                    assert "X-RateLimit-Remaining" in rate_limit_headers
                    assert "X-RateLimit-Reset" in rate_limit_headers

                    retry_after = int(response.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)

                    retry_response = await client.post(
                        "/api/v1/chat/completions",
                        json={"message": "Retry after rate limit", "model": "gpt-4"},
                        headers=headers,
                    )
                    assert retry_response.status_code == 200
                    break

            assert rate_limited is True

    @pytest.mark.asyncio
    async def test_error_recovery_journey(self):
        """Test error recovery user journey."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"Authorization": "Bearer test-token"}

            invalid_request = {"invalid_field": "test"}
            response = await client.post(
                "/api/v1/chat/completions", json=invalid_request, headers=headers
            )
            assert response.status_code == 422
            error = response.json()
            assert "detail" in error

            valid_request = {"message": "Valid request", "model": "gpt-4"}
            response = await client.post(
                "/api/v1/chat/completions", json=valid_request, headers=headers
            )
            assert response.status_code == 200

            expired_token_headers = {"Authorization": "Bearer expired-token"}
            response = await client.post(
                "/api/v1/chat/completions", json=valid_request, headers=expired_token_headers
            )
            assert response.status_code == 401

            refresh_response = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": "valid-refresh-token"}
            )
            assert refresh_response.status_code == 200
            new_tokens = refresh_response.json()

            new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
            response = await client.post(
                "/api/v1/chat/completions", json=valid_request, headers=new_headers
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test system performance under load."""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            headers = {"Authorization": "Bearer test-token"}

            async def make_request(request_id):
                start_time = time.time()
                response = await client.post(
                    "/api/v1/chat/completions",
                    json={"message": f"Concurrent request {request_id}", "model": "gpt-3.5-turbo"},
                    headers=headers,
                )
                latency = (time.time() - start_time) * 1000
                return {
                    "request_id": request_id,
                    "status": response.status_code,
                    "latency_ms": latency,
                }

            concurrent_users = 100
            tasks = [make_request(i) for i in range(concurrent_users)]

            results = await asyncio.gather(*tasks)

            successful = [r for r in results if r["status"] == 200]
            assert len(successful) >= concurrent_users * 0.95

            latencies = [r["latency_ms"] for r in successful]
            latencies.sort()

            p95_latency = latencies[int(len(latencies) * 0.95)]
            assert p95_latency < 200

            average_latency = sum(latencies) / len(latencies)
            assert average_latency < 150
