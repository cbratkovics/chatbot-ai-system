"""
Models module
"""

class Models:
    """Placeholder for Models"""

    def __init__(self, **kwargs):
        """Initialize Models"""
        for key, value in kwargs.items():
            setattr(self, key, value)
