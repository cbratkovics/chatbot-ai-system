"""Hash utilities for cache key generation and text normalization."""

import hashlib
import re
from typing import Any


class HashUtils:
    """Utilities for hashing and text normalization."""
    
    @staticmethod
    def generate_hash(content: str) -> str:
        """Generate SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for consistent hashing."""
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation at the end
        text = re.sub(r'[.!?]+$', '', text)
        
        # Normalize all types of quotes to single quote
        # Using character codes to avoid encoding issues
        for quote_char in ['"', "'", '`', '"', '"', ''', ''']:
            text = text.replace(quote_char, "'")
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def generate_cache_key(
        message: str,
        model: str,
        temperature: float = 0.7,
        user_id: str = "anonymous"
    ) -> str:
        """Generate deterministic cache key."""
        # Normalize the message
        normalized_message = HashUtils.normalize_text(message)
        
        # Create key components
        key_parts = [
            normalized_message,
            model,
            str(temperature),
            user_id
        ]
        
        # Join and hash
        key_content = "|".join(key_parts)
        return f"chat:{HashUtils.generate_hash(key_content)}"
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """Calculate simple text similarity (placeholder for semantic similarity)."""
        # Normalize both texts
        norm1 = HashUtils.normalize_text(text1)
        norm2 = HashUtils.normalize_text(text2)
        
        # Simple exact match for now
        # In production, use sentence transformers or TF-IDF
        return 1.0 if norm1 == norm2 else 0.0
