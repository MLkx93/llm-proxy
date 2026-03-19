"""
API key authentication.

Loads the key registry from config/api_keys.yaml at startup.
Validates the Authorization: Bearer <key> header on every request.
"""
import os
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from .logging import get_logger

logger = get_logger("auth")

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "api_keys.yaml"


@dataclass(frozen=True)
class ApiKeyEntry:
    app_id: str
    team: str
    key_hash: str   # SHA-256 of the raw key — never store plaintext in memory


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load_registry(path: Path) -> dict[str, ApiKeyEntry]:
    """
    Load and index the key registry by key hash.
    Only enabled keys are loaded.
    """
    if not path.exists():
        logger.warning("api_keys_config_missing", extra={"path": str(path)})
        return {}

    with path.open() as f:
        data = yaml.safe_load(f)

    registry: dict[str, ApiKeyEntry] = {}
    for entry in data.get("keys", []):
        if not entry.get("enabled", False):
            continue
        raw_key = entry["key"]
        h = _hash(raw_key)
        registry[h] = ApiKeyEntry(
            app_id=entry["app_id"],
            team=entry["team"],
            key_hash=h,
        )

    logger.info("auth_registry_loaded", extra={"active_keys": len(registry)})
    return registry


# Loaded once at import time — module-level singleton
_registry: dict[str, ApiKeyEntry] = _load_registry(_CONFIG_PATH)


def validate(authorization_header: Optional[str]) -> Optional[ApiKeyEntry]:
    """
    Validate an Authorization header value.
    Returns the ApiKeyEntry if valid, None otherwise.
    Constant-time comparison via hash — prevents timing attacks.
    """
    if not authorization_header:
        return None

    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    raw_key = parts[1].strip()
    h = _hash(raw_key)
    return _registry.get(h)


def validate_api_key(raw_key: Optional[str]) -> Optional[ApiKeyEntry]:
    """
    Validate a raw API key (from x-api-key header).
    Same registry lookup as validate(), but skips Bearer parsing.
    """
    if not raw_key:
        return None
    h = _hash(raw_key.strip())
    return _registry.get(h)


def reload() -> None:
    """Force reload of the registry (useful for testing)."""
    global _registry
    _registry = _load_registry(_CONFIG_PATH)
