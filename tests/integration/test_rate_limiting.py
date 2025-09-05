"""Integration tests for rate limiting functionality."""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chatbot_ai_system.middleware.rate_limiter import RateLimiter
from chatbot_ai_system.exceptions import RateLimitError


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting integration."""

    @pytest.fixture
    async def rate_limiter(self, mock_redis):
        """Create rate limiter instance."""
        limiter = RateLimiter(
            redis_client=mock_redis,
            default_limit=10,
            default_window=60,
        )
        return limiter

    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self, rate_limiter):
        """Test basic rate limiting functionality."""
        client_id = "test_client"

        # Make requests within limit
        for i in range(10):
            allowed = await rate_limiter.check_limit(client_id)
            assert allowed is True

        # Exceed limit
        allowed = await rate_limiter.check_limit(client_id)
        assert allowed is False

        # Check remaining
        remaining = await rate_limiter.get_remaining(client_id)
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_rate_limit_window_reset(self, rate_limiter):
        """Test rate limit window reset."""
        client_id = "reset_client"
        
        # Configure shorter window for testing
        await rate_limiter.set_limit(client_id, limit=5, window=1)

        # Use up limit
        for _ in range(5):
            await rate_limiter.check_limit(client_id)

        # Should be blocked
        allowed = await rate_limiter.check_limit(client_id)
        assert allowed is False

        # Wait for window to reset
        await asyncio.sleep(1.1)

        # Should be allowed again
        allowed = await rate_limiter.check_limit(client_id)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_per_tenant_rate_limits(self, rate_limiter):
        """Test different rate limits per tenant."""
        # Set different limits for different tenants
        await rate_limiter.set_limit("tenant_free", limit=10, window=60)
        await rate_limiter.set_limit("tenant_pro", limit=100, window=60)
        await rate_limiter.set_limit("tenant_enterprise", limit=1000, window=60)

        # Test free tier
        for _ in range(10):
            assert await rate_limiter.check_limit("tenant_free") is True
        assert await rate_limiter.check_limit("tenant_free") is False

        # Test pro tier (should still have capacity)
        for _ in range(50):
            assert await rate_limiter.check_limit("tenant_pro") is True

        # Test enterprise tier (should still have capacity)
        for _ in range(500):
            assert await rate_limiter.check_limit("tenant_enterprise") is True

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, rate_limiter):
        """Test rate limit header information."""
        client_id = "header_client"
        await rate_limiter.set_limit(client_id, limit=20, window=60)

        # Make some requests
        for _ in range(5):
            await rate_limiter.check_limit(client_id)

        # Get header info
        headers = await rate_limiter.get_headers(client_id)
        
        assert headers["X-RateLimit-Limit"] == "20"
        assert headers["X-RateLimit-Remaining"] == "15"
        assert "X-RateLimit-Reset" in headers
        
        # Reset timestamp should be in the future
        reset_time = int(headers["X-RateLimit-Reset"])
        assert reset_time > time.time()

    @pytest.mark.asyncio
    async def test_distributed_rate_limiting(self, rate_limiter):
        """Test rate limiting across distributed instances."""
        client_id = "distributed_client"
        
        # Simulate multiple instances checking the same client
        async def instance_requests(instance_id, count):
            results = []
            for i in range(count):
                allowed = await rate_limiter.check_limit(client_id)
                results.append((instance_id, i, allowed))
                await asyncio.sleep(0.01)  # Small delay
            return results

        # Run concurrent requests from multiple "instances"
        tasks = [
            instance_requests("instance_1", 5),
            instance_requests("instance_2", 5),
            instance_requests("instance_3", 5),
        ]
        
        all_results = await asyncio.gather(*tasks)
        
        # Flatten results
        flat_results = [r for instance_results in all_results for r in instance_results]
        
        # Count allowed requests
        allowed_count = sum(1 for _, _, allowed in flat_results if allowed)
        
        # Should respect global limit (10 by default)
        assert allowed_count == 10

    @pytest.mark.asyncio
    async def test_rate_limit_by_endpoint(self, rate_limiter):
        """Test different rate limits for different endpoints."""
        client_id = "endpoint_client"
        
        # Configure endpoint-specific limits
        endpoints = {
            "/api/v1/chat": {"limit": 10, "window": 60},
            "/api/v1/completions": {"limit": 5, "window": 60},
            "/api/v1/embeddings": {"limit": 20, "window": 60},
        }
        
        for endpoint, config in endpoints.items():
            key = f"{client_id}:{endpoint}"
            await rate_limiter.set_limit(key, **config)
        
        # Test each endpoint separately
        for endpoint, config in endpoints.items():
            key = f"{client_id}:{endpoint}"
            limit = config["limit"]
            
            # Use up the limit
            for _ in range(limit):
                assert await rate_limiter.check_limit(key) is True
            
            # Should be blocked
            assert await rate_limiter.check_limit(key) is False

    @pytest.mark.asyncio
    async def test_rate_limit_burst_handling(self, rate_limiter):
        """Test burst request handling."""
        client_id = "burst_client"
        
        # Configure with burst allowance
        await rate_limiter.set_limit(
            client_id,
            limit=10,
            window=60,
            burst_limit=15,  # Allow burst up to 15
        )
        
        # Send burst of requests
        burst_tasks = [
            rate_limiter.check_limit(client_id) for _ in range(15)
        ]
        results = await asyncio.gather(*burst_tasks)
        
        # All burst requests should be allowed
        assert all(results)
        
        # Next request should be blocked
        assert await rate_limiter.check_limit(client_id) is False

    @pytest.mark.asyncio
    async def test_rate_limit_exemptions(self, rate_limiter):
        """Test rate limit exemptions for special clients."""
        # Configure exempted clients
        exempted_clients = ["admin_client", "monitoring_client"]
        
        for client in exempted_clients:
            await rate_limiter.add_exemption(client)
        
        # Exempted clients should never be limited
        for client in exempted_clients:
            for _ in range(100):  # Way over normal limit
                assert await rate_limiter.check_limit(client) is True
        
        # Normal client should still be limited
        normal_client = "normal_client"
        for _ in range(10):
            await rate_limiter.check_limit(normal_client)
        assert await rate_limiter.check_limit(normal_client) is False

    @pytest.mark.asyncio
    async def test_rate_limit_with_cost_based_limiting(self, rate_limiter):
        """Test cost-based rate limiting (e.g., token-based)."""
        client_id = "cost_client"
        
        # Configure token bucket
        await rate_limiter.configure_token_bucket(
            client_id,
            capacity=1000,  # Total tokens
            refill_rate=100,  # Tokens per minute
        )
        
        # Small request
        consumed = await rate_limiter.consume_tokens(client_id, 50)
        assert consumed is True
        
        # Large request
        consumed = await rate_limiter.consume_tokens(client_id, 200)
        assert consumed is True
        
        # Check remaining
        remaining = await rate_limiter.get_remaining_tokens(client_id)
        assert remaining == 750
        
        # Request exceeding remaining
        consumed = await rate_limiter.consume_tokens(client_id, 800)
        assert consumed is False

    @pytest.mark.asyncio
    async def test_rate_limit_sliding_window(self, rate_limiter):
        """Test sliding window rate limiting algorithm."""
        client_id = "sliding_client"
        
        # Configure sliding window
        await rate_limiter.set_sliding_window(
            client_id,
            limit=10,
            window=10,  # 10 seconds
        )
        
        # First batch of requests
        for _ in range(5):
            assert await rate_limiter.check_limit(client_id) is True
        
        # Wait half window
        await asyncio.sleep(5)
        
        # Second batch
        for _ in range(5):
            assert await rate_limiter.check_limit(client_id) is True
        
        # Should be at limit
        assert await rate_limiter.check_limit(client_id) is False
        
        # Wait for first batch to expire
        await asyncio.sleep(5.1)
        
        # Should have capacity from expired requests
        for _ in range(5):
            assert await rate_limiter.check_limit(client_id) is True

    @pytest.mark.asyncio
    async def test_rate_limit_graceful_degradation(self, rate_limiter):
        """Test graceful degradation when rate limited."""
        client_id = "degradation_client"
        
        # Use up normal limit
        for _ in range(10):
            await rate_limiter.check_limit(client_id)
        
        # Configure degraded service
        degraded_response = {
            "message": "Rate limit exceeded. Using cached/reduced functionality.",
            "cached": True,
            "degraded": True,
        }
        
        # When rate limited, should return degraded response
        result = await rate_limiter.get_degraded_response(client_id)
        assert result["degraded"] is True
        assert result["cached"] is True

    @pytest.mark.asyncio
    async def test_rate_limit_analytics(self, rate_limiter):
        """Test rate limit analytics and monitoring."""
        # Generate traffic from multiple clients
        clients = [f"client_{i}" for i in range(10)]
        
        for client in clients:
            # Some clients hit limits, some don't
            limit = 5 if "odd" in client else 10
            for _ in range(limit + 2):  # Try to exceed
                await rate_limiter.check_limit(client)
        
        # Get analytics
        analytics = await rate_limiter.get_analytics()
        
        assert "total_requests" in analytics
        assert "rate_limited_requests" in analytics
        assert "unique_clients" in analytics
        assert analytics["unique_clients"] == 10
        assert analytics["rate_limited_requests"] > 0
        
        # Get per-client analytics
        for client in clients:
            client_stats = await rate_limiter.get_client_stats(client)
            assert "total_requests" in client_stats
            assert "blocked_requests" in client_stats