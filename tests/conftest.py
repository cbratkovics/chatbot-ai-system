"""Global test configuration and fixtures."""
import asyncio
import json
import time
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.core.config import settings
from api.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_session():
    """Create database session for testing."""
    engine = create_async_engine(settings.DATABASE_URL_TEST)
    async_session = sessionmaker(engine, class_=AsyncSession)

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def auth_headers():
    """Generate authentication headers."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def mock_database():
    """Mock database for testing."""
    mock = AsyncMock()
    mock.query = AsyncMock()
    mock.add = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    # Redis returns bytes for most operations
    mock.get = AsyncMock(return_value=str(time.time()).encode())
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.ttl = AsyncMock(return_value=3600)
    mock.hget = AsyncMock(return_value=json.dumps({"key": "value"}))
    mock.hset = AsyncMock(return_value=1)
    mock.hdel = AsyncMock(return_value=1)
    mock.hgetall = AsyncMock(return_value={b"key": b"value"})
    mock.incr = AsyncMock(return_value=1)
    mock.decr = AsyncMock(return_value=0)
    mock.zadd = AsyncMock(return_value=1)
    mock.zrange = AsyncMock(return_value=[])
    mock.zrem = AsyncMock(return_value=1)
    mock.pipeline = Mock(return_value=mock)
    mock.execute = AsyncMock(return_value=[True])
    return mock


@pytest.fixture
def mock_cache():
    """Mock cache for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.clear = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_websocket():
    """Mock WebSocket for testing."""
    mock = AsyncMock()
    mock.accept = AsyncMock()
    mock.send_json = AsyncMock()
    mock.send_text = AsyncMock()
    mock.send_bytes = AsyncMock()
    mock.receive_json = AsyncMock(return_value={"message": "test"})
    mock.receive_text = AsyncMock(return_value="test")
    mock.close = AsyncMock()
    mock.client = Mock()
    mock.client.host = "127.0.0.1"
    mock.client.port = 12345
    return mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock = MagicMock()
    
    # Mock completion response
    completion_response = MagicMock()
    completion_response.choices = [
        MagicMock(
            message=MagicMock(content="Test response"),
            finish_reason="stop",
            index=0
        )
    ]
    completion_response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30
    )
    completion_response.model = "gpt-3.5-turbo"
    
    # Mock chat completions
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = MagicMock(return_value=completion_response)
    
    # Mock streaming response
    async def mock_stream():
        chunks = [
            MagicMock(
                choices=[
                    MagicMock(
                        delta=MagicMock(content="Test "),
                        finish_reason=None
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        delta=MagicMock(content="response"),
                        finish_reason="stop"
                    )
                ]
            )
        ]
        for chunk in chunks:
            yield chunk
    
    mock.chat.completions.create = AsyncMock(return_value=mock_stream())
    
    return mock


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    from unittest.mock import AsyncMock, Mock
    
    mock = Mock()
    
    # Create an async function that returns the response
    async def async_create(**kwargs):
        return Mock(
            content=[Mock(text="Test response")], 
            usage=Mock(input_tokens=50, output_tokens=50),
            id="test-id",
            model=kwargs.get('model', 'claude-3-sonnet')
        )
    
    # Assign the async function
    mock.messages.create = async_create
    
    return mock


@pytest.fixture
def mock_metrics_collector():
    """Mock metrics collector."""
    mock = AsyncMock()
    mock.increment_counter = AsyncMock()
    mock.record_gauge = AsyncMock()
    mock.record_histogram = AsyncMock()
    mock.record_latency = AsyncMock()
    mock.record_summary = AsyncMock()
    mock.get_metrics = AsyncMock(return_value={})
    return mock


@pytest.fixture
def tenant_config():
    """Sample tenant configuration."""
    return {
        "tenant_id": "test-tenant",
        "tier": "standard",
        "status": "active",
        "rate_limits": {
            "requests_per_minute": 1000,
            "requests_per_hour": 10000,
            "tokens_per_day": 1000000
        },
        "features": ["semantic_cache", "streaming", "multi_model"],
        "quotas": {
            "tokens": 1000000,
            "storage": 1073741824,  # 1GB
            "users": 100
        },
        "billing": {
            "plan": "standard",
            "cycle": "monthly",
            "amount": 99.99
        }
    }


@pytest.fixture
def mock_stream():
    """Mock stream for testing streaming responses."""
    async def stream_generator():
        chunks = ["Hello", " ", "World", "!"]
        for chunk in chunks:
            yield chunk
    
    return stream_generator()


@pytest.fixture
def mock_model_provider():
    """Mock model provider for testing."""
    mock = AsyncMock()
    mock.name = "test-provider"
    mock.models = ["model-1", "model-2"]
    mock.is_healthy = AsyncMock(return_value=True)
    mock.generate = AsyncMock(return_value="Test response")
    mock.stream = AsyncMock(return_value=mock_stream())
    mock.count_tokens = Mock(return_value=10)
    return mock


@pytest.fixture
def mock_circuit_breaker():
    """Mock circuit breaker for testing."""
    mock = MagicMock()
    mock.state = "closed"
    mock.failure_count = 0
    mock.success_count = 0
    mock.is_open = Mock(return_value=False)
    mock.is_closed = Mock(return_value=True)
    mock.is_half_open = Mock(return_value=False)
    mock.call = AsyncMock(side_effect=lambda f: f())
    mock.record_success = Mock()
    mock.record_failure = Mock()
    return mock


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter for testing."""
    mock = AsyncMock()
    mock.allow_request = AsyncMock(return_value=True)
    mock.get_remaining_tokens = AsyncMock(return_value=100)
    mock.get_reset_time = AsyncMock(return_value=time.time() + 3600)
    mock.consume = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_tenant_manager():
    """Mock tenant manager for testing."""
    mock = AsyncMock()
    mock.get_tenant = AsyncMock(return_value={
        "id": "test-tenant",
        "name": "Test Tenant",
        "tier": "standard",
        "status": "active"
    })
    mock.create_tenant = AsyncMock(return_value="test-tenant-id")
    mock.update_tenant = AsyncMock(return_value=True)
    mock.delete_tenant = AsyncMock(return_value=True)
    mock.get_tenant_usage = AsyncMock(return_value={
        "tokens": 1000,
        "requests": 100,
        "storage": 1024
    })
    return mock


@pytest.fixture
def mock_auth_service():
    """Mock authentication service for testing."""
    mock = AsyncMock()
    mock.authenticate = AsyncMock(return_value={
        "user_id": "test-user",
        "tenant_id": "test-tenant",
        "role": "user"
    })
    mock.authorize = AsyncMock(return_value=True)
    mock.create_token = Mock(return_value="test-token")
    mock.verify_token = AsyncMock(return_value={
        "user_id": "test-user",
        "tenant_id": "test-tenant"
    })
    return mock


@pytest.fixture
def mock_embeddings():
    """Mock embeddings for testing."""
    import numpy as np
    
    # Create sample embeddings
    embeddings = np.random.rand(10, 768).astype(np.float32)
    
    mock = MagicMock()
    mock.encode = Mock(return_value=embeddings[0])
    mock.encode_batch = Mock(return_value=embeddings)
    mock.similarity = Mock(return_value=0.95)
    return mock


@pytest.fixture
def cache():
    """In-memory cache for testing."""
    storage = {}
    
    class TestCache:
        async def get(self, key):
            return storage.get(key)
        
        async def set(self, key, value, ttl=None):
            storage[key] = value
            return True
        
        async def delete(self, key):
            return storage.pop(key, None) is not None
        
        async def clear(self):
            storage.clear()
            return True
        
        async def exists(self, key):
            return key in storage
    
    return TestCache()
@pytest.fixture
def cache_config():
    """Cache configuration for testing."""
    return {
        "similarity_threshold": 0.9,
        "ttl_seconds": 3600,
        "max_cache_size": 1000,
        "embedding_model": "text-embedding-ada-002"
    }

# Override the mock_redis fixture
@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock = AsyncMock()
    
    # Configure get to return None by default (can be overridden in tests)
    mock.get = AsyncMock(return_value=None)
    
    # Configure hget to return string values
    mock.hget = AsyncMock(return_value=None)
    
    # Other methods with proper return types
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=False)
    mock.delete = AsyncMock(return_value=1)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.ttl = AsyncMock(return_value=3600)
    mock.zadd = AsyncMock(return_value=1)
    mock.zrange = AsyncMock(return_value=[])
    mock.ping = AsyncMock(return_value=True)
    mock.hset = AsyncMock(return_value=1)
    mock.hmset = AsyncMock(return_value=True)
    
    return mock
