"""
Token bucket rate limiter — per API key (app_id).

Each app_id gets its own bucket:
  - Capacity: MAX_TOKENS requests
  - Refill:   REFILL_RATE tokens per second (continuous)

When a request arrives:
  - Refill the bucket based on elapsed time since last request
  - If at least 1 token available: consume it, allow
  - Otherwise: deny with RATE_LIMITED

All state is in-memory (suitable for v1 single-instance deployment).
For multi-instance, replace with Redis-backed implementation.
"""
import time
import threading
from dataclasses import dataclass, field

# Default limits — override via env config if needed in future
MAX_TOKENS: int = 60       # burst capacity (requests)
REFILL_RATE: float = 1.0   # tokens added per second (= 60 req/min sustained)


@dataclass
class _Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)


_buckets: dict[str, _Bucket] = {}
_lock = threading.Lock()


def is_allowed(app_id: str) -> bool:
    """
    Check and consume one token for app_id.
    Returns True if the request is allowed, False if rate-limited.
    """
    now = time.monotonic()
    with _lock:
        if app_id not in _buckets:
            # First request: start with a full bucket minus this request
            _buckets[app_id] = _Bucket(tokens=MAX_TOKENS - 1, last_refill=now)
            return True

        bucket = _buckets[app_id]
        elapsed = now - bucket.last_refill
        bucket.tokens = min(MAX_TOKENS, bucket.tokens + elapsed * REFILL_RATE)
        bucket.last_refill = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True

        return False


def reset(app_id: str) -> None:
    """Reset a bucket — used in tests."""
    with _lock:
        _buckets.pop(app_id, None)
