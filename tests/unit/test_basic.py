"""Basic unit tests to ensure the test suite runs."""


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