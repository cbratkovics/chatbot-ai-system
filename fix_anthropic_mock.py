import fileinput
import re

# Read the conftest file
with open('tests/conftest.py', 'r') as f:
    content = f.read()

# Find and replace the mock_anthropic_client fixture
new_fixture = '''@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing"""
    from unittest.mock import AsyncMock, Mock
    
    mock = Mock()
    
    # Make messages.create return an AsyncMock
    mock.messages.create = AsyncMock()
    mock.messages.create.return_value = Mock(
        content=[Mock(text="Test response")], 
        usage=Mock(input_tokens=50, output_tokens=50)
    )
    
    return mock'''

# Replace the existing fixture
pattern = r'@pytest\.fixture\s+def mock_anthropic_client\(\):.*?return mock'
content = re.sub(pattern, new_fixture, content, flags=re.DOTALL)

with open('tests/conftest.py', 'w') as f:
    f.write(content)
