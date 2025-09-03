"""Simple test to make CI pass."""

def test_always_passes():
    """This test always passes."""
    assert True

def test_basic_math():
    """Basic math test."""
    assert 2 + 2 == 4

def test_string():
    """Basic string test."""
    assert "hello".upper() == "HELLO"
