"""
Unit tests for the audit logger and its integration in the proxy pipeline.
"""
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient, ASGITransport

import config.settings as settings_module
from src.audit.logger import emit, _hash_messages
from src.proxy.main import app


AUTH = {"Authorization": "Bearer dev-local-key-1234"}

FAKE_RESPONSE = MagicMock()
FAKE_RESPONSE.model_dump.return_value = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
}


@pytest.fixture
def tmp_audit_path(tmp_path):
    """Redirect audit log to a temp file for test isolation."""
    log_file = tmp_path / "audit.jsonl"
    original = settings_module.settings.AUDIT_LOG_PATH
    settings_module.settings.AUDIT_LOG_PATH = str(log_file)
    yield log_file
    settings_module.settings.AUDIT_LOG_PATH = original


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Audit logger unit tests
# ---------------------------------------------------------------------------
class TestAuditLogger:
    def test_emit_writes_jsonl(self, tmp_audit_path):
        emit(request_id="req-1", app_id="test-app", action="ALLOWED", model="gpt-4o")
        events = read_events(tmp_audit_path)
        assert len(events) == 1
        e = events[0]
        assert e["request_id"] == "req-1"
        assert e["app_id"] == "test-app"
        assert e["action"] == "ALLOWED"
        assert e["model"] == "gpt-4o"
        assert e["block_code"] is None
        assert "timestamp" in e

    def test_emit_blocked_includes_block_code(self, tmp_audit_path):
        emit(request_id="req-2", app_id="app-x", action="BLOCKED", block_code="BLOCKED_PII")
        events = read_events(tmp_audit_path)
        assert events[0]["block_code"] == "BLOCKED_PII"
        assert events[0]["action"] == "BLOCKED"

    def test_emit_unauthenticated_uses_fallback_app_id(self, tmp_audit_path):
        emit(request_id="req-3", app_id=None, action="BLOCKED", block_code="UNAUTHORIZED")
        events = read_events(tmp_audit_path)
        assert events[0]["app_id"] == "unauthenticated"

    def test_emit_multiple_appends(self, tmp_audit_path):
        emit(request_id="r1", app_id="a", action="ALLOWED")
        emit(request_id="r2", app_id="a", action="BLOCKED", block_code="BLOCKED_PII")
        emit(request_id="r3", app_id="a", action="ERROR", block_code="LLM_ERROR")
        events = read_events(tmp_audit_path)
        assert len(events) == 3
        assert [e["action"] for e in events] == ["ALLOWED", "BLOCKED", "ERROR"]

    def test_prompt_hash_not_raw_text(self, tmp_audit_path):
        messages = [{"role": "user", "content": "super secret prompt"}]
        emit(request_id="r4", app_id="a", action="ALLOWED", messages=messages)
        events = read_events(tmp_audit_path)
        raw_line = tmp_audit_path.read_text()
        assert "super secret prompt" not in raw_line
        assert events[0]["prompt_hash"] is not None
        assert len(events[0]["prompt_hash"]) == 64  # SHA-256 hex

    def test_same_messages_same_hash(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert _hash_messages(msgs) == _hash_messages(msgs)

    def test_different_messages_different_hash(self):
        a = _hash_messages([{"role": "user", "content": "hello"}])
        b = _hash_messages([{"role": "user", "content": "world"}])
        assert a != b

    def test_latency_recorded(self, tmp_audit_path):
        emit(request_id="r5", app_id="a", action="ALLOWED", latency_ms=123)
        events = read_events(tmp_audit_path)
        assert events[0]["latency_ms"] == 123

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "audit.jsonl"
        settings_module.settings.AUDIT_LOG_PATH = str(nested)
        emit(request_id="r6", app_id="a", action="ALLOWED")
        assert nested.exists()
        settings_module.settings.AUDIT_LOG_PATH = "logs/audit.jsonl"


# ---------------------------------------------------------------------------
# Integration: audit events emitted through the full proxy
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_allowed_request_audit_event(client, tmp_audit_path):
    with patch("src.proxy.main.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = FAKE_RESPONSE
        await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
            headers=AUTH,
        )
    events = read_events(tmp_audit_path)
    assert len(events) == 1
    assert events[0]["action"] == "ALLOWED"
    assert events[0]["app_id"] == "local-dev"
    assert events[0]["model"] == "gpt-4o"
    assert events[0]["latency_ms"] is not None


@pytest.mark.asyncio
async def test_unauthorized_audit_event(client, tmp_audit_path):
    await client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": "Bearer bad-key"},
    )
    events = read_events(tmp_audit_path)
    assert len(events) == 1
    assert events[0]["action"] == "BLOCKED"
    assert events[0]["block_code"] == "UNAUTHORIZED"
    assert events[0]["app_id"] == "unauthenticated"


@pytest.mark.asyncio
async def test_input_blocked_audit_event(client, tmp_audit_path):
    await client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "my email is john@example.com"}]},
        headers=AUTH,
    )
    events = read_events(tmp_audit_path)
    assert len(events) == 1
    assert events[0]["action"] == "BLOCKED"
    assert events[0]["block_code"] == "BLOCKED_PII"
    assert events[0]["prompt_hash"] is not None
