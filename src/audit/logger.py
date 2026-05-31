"""
Audit Logger.

Writes one JSON object per line to logs/audit.jsonl (append-only).
Each event captures what happened, who did it, and why — without
storing the raw prompt (privacy) or the raw API key (security).

Schema per event:
  timestamp     ISO-8601 UTC
  request_id    UUID
  app_id        from API key registry (or "unauthenticated")
  action        ALLOWED | BLOCKED | ERROR
  block_code    error code if action != ALLOWED, else null
  model         LLM model requested (or null if blocked before routing)
  prompt_hash   SHA-256 of concatenated prompt content (not the raw text)
  latency_ms    wall-clock ms from request start to audit write (or null)
"""
import json
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import settings
from src.proxy.logging import get_logger

logger = get_logger("audit")

# Thread lock: multiple async workers may write simultaneously in production
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_messages(messages: list[dict]) -> str:
    """SHA-256 of concatenated message contents. Never logs raw prompts."""
    combined = "\n".join(m.get("content", "") for m in messages)
    return hashlib.sha256(combined.encode()).hexdigest()


def _write(event: dict) -> None:
    log_path = Path(settings.AUDIT_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, separators=(",", ":")) + "\n"
    with _lock:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)


def emit(
    *,
    request_id: str,
    app_id: Optional[str],
    action: str,                    # "ALLOWED" | "BLOCKED" | "ERROR"
    messages: Optional[list[dict]] = None,
    model: Optional[str] = None,
    block_code: Optional[str] = None,
    latency_ms: Optional[int] = None,
    prompt_hash: Optional[str] = None,
    findings: Optional[list[str]] = None,      # NEW: List of detected PII/secrets
    redaction_details: Optional[dict] = None,  # NEW: Redaction metadata
) -> None:
    """
    Write a single audit event. Safe to call from async context —
    the file write is synchronous but brief (append-only, no seek).

    If prompt_hash is provided, it's used directly (for Anthropic-format requests
    where messages are pre-extracted). Otherwise, computed from messages.
    
    New parameters:
    - findings: List of detected PII/secrets types (e.g., ["EMAIL_ADDRESS", "OPENAI_API_KEY"])
    - redaction_details: Dictionary with redaction metadata (see below)
    
    Redaction details structure:
    {
        "redacted": bool,           # True if redaction occurred
        "pii_types": list[str],     # ["EMAIL_ADDRESS", "PHONE_NUMBER", etc.]
        "redaction_count": int,     # Number of items redacted
        "original_hash": str,       # SHA-256 before redaction
        "sanitized_hash": str,     # SHA-256 after redaction
        "redaction_method": str,    # "presidio" or "regex"
    }
    """
    computed_hash = prompt_hash
    if computed_hash is None and messages:
        computed_hash = _hash_messages(messages)

    event = {
        "timestamp": _now(),
        "request_id": request_id,
        "app_id": app_id or "unauthenticated",
        "action": action,
        "block_code": block_code,
        "model": model,
        "prompt_hash": computed_hash,
        "latency_ms": latency_ms,
    }
    
    # Add new fields if provided
    if findings:
        event["findings"] = findings
    if redaction_details:
        event["redaction_details"] = redaction_details
        
    try:
        _write(event)
    except OSError as exc:
        # Never let audit failure crash the proxy — but do log it loudly
        logger.error("audit_write_failed", extra={"error": str(exc)})
