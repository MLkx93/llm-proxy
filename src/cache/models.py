"""
Cache data models for the LLM Proxy response caching system.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
from pydantic import BaseModel


@dataclass
class CacheMetadata:
    """Metadata for cached responses."""
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    model: str = ""
    prompt_hash: str = ""
    cache_size_bytes: int = 0


class CacheKey(BaseModel):
    """Cache key model for Redis operations."""
    prompt_hash: str
    model: str
    timestamp_hour: str  # YYYY-MM-DD HH:00:00 format

    @classmethod
    def generate(cls, messages: list, model: str, timestamp: datetime) -> str:
        """Generate cache key from messages and model."""
        # Create a normalized prompt representation
        prompt_text = cls._normalize_messages(messages)
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()

        # Round timestamp to hour for cache grouping
        timestamp_hour = timestamp.strftime("%Y-%m-%d %H:00:00")

        return f"llm_cache:{prompt_hash}:{model}:{timestamp_hour}"

    @staticmethod
    def _normalize_messages(messages: list) -> str:
        """Normalize messages for consistent hashing."""
        # Sort messages by role for consistency
        sorted_messages = sorted(messages, key=lambda x: x.get('role', ''))

        # Remove common variations that don't affect meaning
        normalized = []
        for msg in sorted_messages:
            normalized_msg = {
                'role': msg.get('role', ''),
                'content': msg.get('content', '').strip().lower()
            }
            normalized.append(normalized_msg)

        return json.dumps(normalized, sort_keys=True)


@dataclass
class CachedResponse:
    """Cached response data structure."""
    content: str
    model: str
    created_at: datetime
    expires_at: datetime
    metadata: Dict[str, Any]
    cache_key: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return {
            'content': self.content,
            'model': self.model,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'metadata': self.metadata,
            'cache_key': self.cache_key
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedResponse':
        """Create instance from dictionary."""
        return cls(
            content=data['content'],
            model=data['model'],
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']),
            metadata=data.get('metadata', {}),
            cache_key=data.get('cache_key', '')
        )


@dataclass
class CacheStats:
    """Cache statistics."""
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    total_cached_items: int
    total_cache_size_bytes: int
    avg_response_time_ms: float

    @property
    def miss_rate(self) -> float:
        """Calculate miss rate."""
        return 1.0 - self.hit_rate if self.total_requests > 0 else 0.0