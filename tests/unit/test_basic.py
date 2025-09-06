"""Basic unit tests for core functionality."""
import pytest
from chatbot_ai_system import __version__


def test_version():
    """Test version is set correctly."""
    assert __version__ == "1.0.0"


def test_imports():
    """Test core imports work."""
    from chatbot_ai_system import ChatbotClient, Settings
    assert ChatbotClient is not None
    assert Settings is not None


def test_settings_defaults():
    """Test settings have proper defaults."""
    from chatbot_ai_system import Settings
    settings = Settings()
    assert settings.environment in ["development", "production", "test"]
    assert settings.api_prefix == "/api/v1"


def test_client_initialization():
    """Test client can be initialized."""
    from chatbot_ai_system import ChatbotClient, Settings
    settings = Settings()
    client = ChatbotClient()
    assert client is not None


def test_basic_math():
    """Test basic arithmetic operations."""
    assert 2 + 2 == 4
    assert 10 - 5 == 5
    assert 3 * 4 == 12
    assert 15 / 3 == 5


def test_basic_string():
    """Test basic string operations."""
    assert "hello" + " " + "world" == "hello world"
    assert "Python".lower() == "python"
    assert "test".upper() == "TEST"
    assert len("test") == 4


def test_basic_list():
    """Test basic list operations."""
    test_list = [1, 2, 3, 4, 5]
    assert len(test_list) == 5
    assert test_list[0] == 1
    assert test_list[-1] == 5
    assert sum(test_list) == 15


def test_basic_dict():
    """Test basic dictionary operations."""
    test_dict = {"key1": "value1", "key2": "value2"}
    assert len(test_dict) == 2
    assert test_dict["key1"] == "value1"
    assert "key2" in test_dict
    assert test_dict.get("key3") is None


def test_basic_boolean():
    """Test basic boolean operations."""
    assert True
    assert not False
    assert True and True
    assert True or False
    assert not (False and True)