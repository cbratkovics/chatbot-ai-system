"""
Database module
"""


class Database:
    """Placeholder for Database"""

    def __init__(self, **kwargs):
        """Initialize Database"""
        for key, value in kwargs.items():
            setattr(self, key, value)
