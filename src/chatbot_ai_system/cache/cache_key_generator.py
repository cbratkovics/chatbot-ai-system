"""
Cache key generation with deterministic hashing and semantic similarity.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)


class CacheKeyGenerator:
    """Generate deterministic cache keys with semantic similarity support."""
    
    # Cache key version for easy invalidation
    KEY_VERSION = "v1"
    
    def __init__(
        self,
        semantic_cache_enabled: bool = True,
        similarity_threshold: float = 0.95,
        max_similarity_candidates: int = 100
    ):
        """
        Initialize cache key generator.
        
        Args:
            semantic_cache_enabled: Enable semantic similarity matching
            similarity_threshold: Threshold for considering queries similar
            max_similarity_candidates: Maximum candidates to check for similarity
        """
        self.semantic_cache_enabled = semantic_cache_enabled
        self.similarity_threshold = similarity_threshold
        self.max_similarity_candidates = max_similarity_candidates
        
        # TF-IDF vectorizer for semantic similarity
        self.vectorizer = None
        self.message_vectors = {}
        self.message_cache = {}
        
        if semantic_cache_enabled:
            self._initialize_vectorizer()
    
    def _initialize_vectorizer(self):
        """Initialize TF-IDF vectorizer for semantic similarity."""
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 3),
            stop_words='english',
            lowercase=True,
            strip_accents='unicode'
        )
    
    def generate_key(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        user_id: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate deterministic cache key.
        
        Args:
            messages: Chat messages
            model: Model identifier
            temperature: Temperature setting
            user_id: Optional user identifier
            additional_params: Additional parameters to include in key
        
        Returns:
            Cache key string
        """
        # Normalize messages
        normalized_messages = self._normalize_messages(messages)
        
        # Create key components
        key_components = {
            "version": self.KEY_VERSION,
            "messages": normalized_messages,
            "model": model.lower().strip(),
            "temperature": round(temperature, 2),  # Round to 2 decimal places
        }
        
        # Add optional components
        if user_id:
            key_components["user_id"] = user_id
        
        if additional_params:
            # Sort params for consistency
            key_components["params"] = dict(sorted(additional_params.items()))
        
        # Generate hash
        key_string = json.dumps(key_components, sort_keys=True, separators=(',', ':'))
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()
        
        # Create final key
        prefix = f"chat:{self.KEY_VERSION}:{model}"
        if user_id:
            prefix += f":{user_id}"
        
        return f"{prefix}:{key_hash}"
    
    def _normalize_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Normalize messages for consistent key generation.
        
        Args:
            messages: Original messages
        
        Returns:
            Normalized messages
        """
        normalized = []
        
        for msg in messages:
            # Normalize content
            content = msg.get("content", "")
            content = self._normalize_text(content)
            
            normalized.append({
                "role": msg.get("role", "").lower().strip(),
                "content": content
            })
        
        return normalized
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent hashing.
        
        Args:
            text: Original text
        
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove trailing punctuation that doesn't affect meaning
        text = text.rstrip('.,;:!? ')
        
        return text
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score (0-1)
        """
        if not self.semantic_cache_enabled or not self.vectorizer:
            return 0.0
        
        try:
            # Normalize texts
            text1 = self._normalize_text(text1)
            text2 = self._normalize_text(text2)
            
            # Check exact match first
            if text1 == text2:
                return 1.0
            
            # Calculate TF-IDF vectors
            vectors = self.vectorizer.fit_transform([text1, text2])
            
            # Calculate cosine similarity
            similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def find_similar_key(
        self,
        messages: List[Dict[str, str]],
        cached_keys: List[str],
        model: str,
        temperature: float,
        redis_client: Any = None
    ) -> Optional[Tuple[str, float]]:
        """
        Find similar cached query.
        
        Args:
            messages: Current messages
            cached_keys: List of cached keys to check
            model: Model identifier
            temperature: Temperature setting
            redis_client: Redis client for fetching cached messages
        
        Returns:
            Tuple of (similar_key, similarity_score) or None
        """
        if not self.semantic_cache_enabled:
            return None
        
        # Get current message content
        current_content = self._extract_message_content(messages)
        
        best_match = None
        best_score = 0.0
        
        # Limit number of keys to check
        keys_to_check = cached_keys[:self.max_similarity_candidates]
        
        for key in keys_to_check:
            # Only check keys for same model and similar temperature
            if model.lower() not in key.lower():
                continue
            
            # Get cached message content (would need Redis lookup)
            # This is simplified - in production, you'd batch these lookups
            if key in self.message_cache:
                cached_content = self.message_cache[key]
            else:
                # Skip if we can't get the cached content
                continue
            
            # Calculate similarity
            similarity = self.calculate_similarity(current_content, cached_content)
            
            if similarity > self.similarity_threshold and similarity > best_score:
                best_match = key
                best_score = similarity
        
        if best_match:
            logger.info(f"Found similar cached query with {best_score:.2%} similarity")
            return (best_match, best_score)
        
        return None
    
    def _extract_message_content(self, messages: List[Dict[str, str]]) -> str:
        """
        Extract content from messages for similarity comparison.
        
        Args:
            messages: Chat messages
        
        Returns:
            Combined message content
        """
        content_parts = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Focus on user messages for similarity
            if role == "user":
                content_parts.append(content)
            elif role == "system":
                # Include system prompts but with less weight
                content_parts.append(f"[system: {content[:100]}]")
        
        return " ".join(content_parts)
    
    def add_to_similarity_index(self, key: str, messages: List[Dict[str, str]]):
        """
        Add messages to similarity index.
        
        Args:
            key: Cache key
            messages: Messages to index
        """
        if not self.semantic_cache_enabled:
            return
        
        content = self._extract_message_content(messages)
        self.message_cache[key] = content
        
        # In production, you might want to limit the size of this cache
        if len(self.message_cache) > 10000:
            # Remove oldest entries
            oldest_keys = list(self.message_cache.keys())[:1000]
            for k in oldest_keys:
                del self.message_cache[k]
    
    def generate_pattern(self, model: Optional[str] = None, user_id: Optional[str] = None) -> str:
        """
        Generate pattern for cache invalidation.
        
        Args:
            model: Model to match
            user_id: User ID to match
        
        Returns:
            Pattern string for Redis SCAN
        """
        pattern_parts = ["chat", self.KEY_VERSION]
        
        if model:
            pattern_parts.append(model)
        else:
            pattern_parts.append("*")
        
        if user_id:
            pattern_parts.append(user_id)
        else:
            pattern_parts.append("*")
        
        pattern_parts.append("*")
        
        return ":".join(pattern_parts)
    
    def extract_metadata_from_key(self, key: str) -> Dict[str, str]:
        """
        Extract metadata from cache key.
        
        Args:
            key: Cache key
        
        Returns:
            Dictionary with metadata
        """
        parts = key.split(":")
        
        metadata = {
            "type": parts[0] if len(parts) > 0 else None,
            "version": parts[1] if len(parts) > 1 else None,
            "model": parts[2] if len(parts) > 2 else None,
        }
        
        # Check if user_id is present
        if len(parts) > 4:
            metadata["user_id"] = parts[3]
            metadata["hash"] = parts[4]
        else:
            metadata["hash"] = parts[3] if len(parts) > 3 else None
        
        return metadata