# Add to existing conftest.py - fix mock_anthropic_client
@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    mock = Mock()
    
    # Create an async mock that returns a proper response
    async def mock_create(**kwargs):
        if kwargs.get('stream'):
            # Return async generator for streaming
            async def stream_gen():
                for chunk in ["Hello", " from", " Claude"]:
                    yield {"delta": {"text": chunk}}
            return stream_gen()
        else:
            # Return dict response for non-streaming
            return {
                "id": "test-id",
                "content": [{"text": "Test response"}],
                "model": kwargs.get('model', 'claude-3-sonnet'),
                "usage": {"input_tokens": 10, "output_tokens": 20}
            }
    
    mock.messages.create = mock_create
    return mock
