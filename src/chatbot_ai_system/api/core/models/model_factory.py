"""
ModelFactory module
"""


class ModelFactory:
    """Placeholder for ModelFactory"""

    def __init__(self, **kwargs):
        """Initialize ModelFactory"""
        for key, value in kwargs.items():
            setattr(self, key, value)
