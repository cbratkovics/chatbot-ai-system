# Update mock_redis fixture to handle different return types
@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock = AsyncMock()
    
    # Configure get to return bytes (Redis default)
    mock.get = AsyncMock(side_effect=lambda key: None)
    
    # Configure hget to return string values
    mock.hget = AsyncMock(return_value=None)
    
    # Other methods
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
    
    return mock
