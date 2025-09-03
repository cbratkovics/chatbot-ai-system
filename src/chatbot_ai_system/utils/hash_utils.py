"""
Hash utilities for message normalization and semantic hashing.
"""

import hashlib
import re
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher
import unicodedata
import logging

logger = logging.getLogger(__name__)


class HashUtils:
    """Utilities for hashing and message similarity."""
    
    @staticmethod
    def normalize_message(text: str, aggressive: bool = False) -> str:
        """
        Normalize message text for consistent hashing.
        
        Args:
            text: Original text
            aggressive: Use aggressive normalization (more likely to match)
        
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)
        text = ''.join([c for c in text if not unicodedata.combining(c)])
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        if aggressive:
            # Remove all punctuation for aggressive matching
            text = re.sub(r'[^\w\s]', ' ', text)
            
            # Remove numbers (they often don't affect semantic meaning)
            text = re.sub(r'\d+', '', text)
            
            # Remove common filler words
            filler_words = ['um', 'uh', 'like', 'you know', 'basically', 'actually', 'literally']
            for word in filler_words:
                text = re.sub(r'\b' + word + r'\b', '', text, flags=re.IGNORECASE)
            
            # Remove extra whitespace again
            text = ' '.join(text.split())
        else:
            # Light normalization - keep some punctuation
            # Remove trailing punctuation
            text = text.rstrip('.,;:!? ')
            
            # Normalize quotes
            text = re.sub(r'[""`\'']', "'", text)
            
            # Normalize dashes
            text = re.sub(r'[—–−]', '-', text)
        
        return text.strip()
    
    @staticmethod
    def calculate_similarity_score(text1: str, text2: str, method: str = "ratio") -> float:
        """
        Calculate similarity score between two texts.
        
        Args:
            text1: First text
            text2: Second text
            method: Similarity method (ratio, quick_ratio, real_quick_ratio)
        
        Returns:
            Similarity score (0-1)
        """
        # Normalize both texts
        text1 = HashUtils.normalize_message(text1)
        text2 = HashUtils.normalize_message(text2)
        
        # Check exact match after normalization
        if text1 == text2:
            return 1.0
        
        # Use SequenceMatcher for similarity
        matcher = SequenceMatcher(None, text1, text2)
        
        if method == "ratio":
            return matcher.ratio()
        elif method == "quick_ratio":
            return matcher.quick_ratio()
        elif method == "real_quick_ratio":
            return matcher.real_quick_ratio()
        else:
            return matcher.ratio()
    
    @staticmethod
    def generate_semantic_hash(text: str, hash_size: int = 8) -> str:
        """
        Generate semantic hash for similarity detection.
        Uses SimHash-like algorithm.
        
        Args:
            text: Text to hash
            hash_size: Size of hash in bytes
        
        Returns:
            Semantic hash string
        """
        # Normalize text
        normalized = HashUtils.normalize_message(text, aggressive=True)
        
        if not normalized:
            return "0" * (hash_size * 2)
        
        # Generate n-grams
        ngrams = HashUtils._generate_ngrams(normalized, n=3)
        
        # Initialize hash vector
        hash_vector = [0] * (hash_size * 8)
        
        # Process each n-gram
        for ngram in ngrams:
            # Hash the n-gram
            ngram_hash = hashlib.md5(ngram.encode()).digest()[:hash_size]
            
            # Update hash vector
            for i, byte in enumerate(ngram_hash):
                for j in range(8):
                    bit = (byte >> j) & 1
                    if bit:
                        hash_vector[i * 8 + j] += 1
                    else:
                        hash_vector[i * 8 + j] -= 1
        
        # Generate final hash
        result = 0
        for i, value in enumerate(hash_vector):
            if value > 0:
                result |= (1 << i)
        
        # Convert to hex string
        return format(result, f'0{hash_size * 2}x')
    
    @staticmethod
    def _generate_ngrams(text: str, n: int = 3) -> List[str]:
        """
        Generate n-grams from text.
        
        Args:
            text: Input text
            n: N-gram size
        
        Returns:
            List of n-grams
        """
        words = text.split()
        ngrams = []
        
        # Word-level n-grams
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i + n])
            ngrams.append(ngram)
        
        # Character-level n-grams for short texts
        if len(words) < n:
            for i in range(len(text) - n + 1):
                ngram = text[i:i + n]
                ngrams.append(ngram)
        
        return ngrams
    
    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """
        Calculate Hamming distance between two hashes.
        
        Args:
            hash1: First hash
            hash2: Second hash
        
        Returns:
            Hamming distance
        """
        if len(hash1) != len(hash2):
            return max(len(hash1), len(hash2))
        
        # Convert hex strings to integers
        try:
            int1 = int(hash1, 16)
            int2 = int(hash2, 16)
            
            # XOR and count set bits
            xor = int1 ^ int2
            distance = bin(xor).count('1')
            
            return distance
        except ValueError:
            # Fallback to character comparison
            return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    
    @staticmethod
    def semantic_similarity(text1: str, text2: str, threshold: int = 10) -> bool:
        """
        Check if two texts are semantically similar using SimHash.
        
        Args:
            text1: First text
            text2: Second text
            threshold: Maximum Hamming distance for similarity
        
        Returns:
            True if texts are similar
        """
        hash1 = HashUtils.generate_semantic_hash(text1)
        hash2 = HashUtils.generate_semantic_hash(text2)
        
        distance = HashUtils.hamming_distance(hash1, hash2)
        
        return distance <= threshold
    
    @staticmethod
    def hash_messages(messages: List[Dict[str, str]], include_system: bool = True) -> str:
        """
        Generate hash for a list of messages.
        
        Args:
            messages: List of message dictionaries
            include_system: Include system messages in hash
        
        Returns:
            SHA-256 hash of messages
        """
        # Extract and normalize message content
        content_parts = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Skip system messages if not included
            if role == "system" and not include_system:
                continue
            
            # Normalize content
            normalized = HashUtils.normalize_message(content)
            
            # Add role prefix for context
            content_parts.append(f"{role}:{normalized}")
        
        # Join all parts
        combined = "|".join(content_parts)
        
        # Generate SHA-256 hash
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def quick_hash(text: str) -> str:
        """
        Generate quick hash for text (MD5).
        
        Args:
            text: Text to hash
        
        Returns:
            MD5 hash string
        """
        return hashlib.md5(text.encode()).hexdigest()
    
    @staticmethod
    def secure_hash(text: str) -> str:
        """
        Generate secure hash for text (SHA-256).
        
        Args:
            text: Text to hash
        
        Returns:
            SHA-256 hash string
        """
        return hashlib.sha256(text.encode()).hexdigest()
    
    @staticmethod
    def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract keywords from text for indexing.
        
        Args:
            text: Input text
            max_keywords: Maximum number of keywords
        
        Returns:
            List of keywords
        """
        # Normalize text
        normalized = HashUtils.normalize_message(text, aggressive=True)
        
        # Simple keyword extraction (word frequency)
        words = normalized.split()
        
        # Filter out short words and stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall'
        }
        
        keywords = []
        word_count = {}
        
        for word in words:
            if len(word) > 2 and word not in stopwords:
                word_count[word] = word_count.get(word, 0) + 1
        
        # Sort by frequency
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        
        # Return top keywords
        for word, _ in sorted_words[:max_keywords]:
            keywords.append(word)
        
        return keywords