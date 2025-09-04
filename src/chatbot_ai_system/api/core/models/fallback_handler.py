"""
FallbackHandler module
"""


class FallbackHandler:
    """Placeholder for FallbackHandler"""

    def __init__(self, **kwargs):
        """Initialize FallbackHandler"""
        for key, value in kwargs.items():
            setattr(self, key, value)
