"""
Unit tests for API key authentication.
Tests the validate() function and integration via the proxy endpoint.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

import src.proxy.auth as auth_module
from src.proxy.auth import validate
from src.proxy.main import app


# ---------------------------------------------------------------------------
# validate() unit tests
# ---------------------------------------------------------------------------
class TestValidate:
    def test_valid_key_returns_entry(self):
        entry = validate("Bearer dev-local-key-1234")
        assert entry is not None
        assert entry.app_id == "local-dev"
        assert entry.team == "Development"

    def test_valid_key_case_insensitive_bearer(self):
        entry = validate("BEARER dev-local-key-1234")
        assert entry is not None

    def test_second_valid_key(self):
        entry = validate("Bearer ci-pipeline-key-5678")
        assert entry is not None
        assert entry.app_id == "ci-pipeline"

    def test_disabled_key_rejected(self):
        # old-key-9999 is in the config but enabled: false
        entry = validate("Bearer old-key-9999")
        assert entry is None

    def test_unknown_key_rejected(self):
        entry = validate("Bearer totally-fake-key")
        assert entry is None

    def test_missing_header_rejected(self):
        entry = validate(None)
        assert entry is None

    def test_empty_string_rejected(self):
        entry = validate("")
        assert entry is None

    def test_no_bearer_prefix_rejected(self):
        entry = validate("dev-local-key-1234")
        assert entry is None

    def test_key_hash_not_stored_as_plaintext(self):
        # The in-memory registry must not contain the raw key
        raw_key = "dev-local-key-1234"
        for entry in auth_module._registry.values():
            assert raw_key not in str(entry)


# ---------------------------------------------------------------------------
# Integration: auth wired into /v1/chat/completions
# ---------------------------------------------------------------------------
FAKE_RESPONSE = MagicMock()
FAKE_RESPONSE.model_dump.return_value = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
}

VALID_PAYLOAD = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello"}],
}


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_no_auth_header_returns_401(client):
    response = await client.post("/v1/chat/completions", json=VALID_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_invalid_key_returns_401(client):
    response = await client.post(
        "/v1/chat/completions",
        json=VALID_PAYLOAD,
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_valid_key_proceeds(client):
    with patch("src.proxy.main.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = FAKE_RESPONSE
        response = await client.post(
            "/v1/chat/completions",
            json=VALID_PAYLOAD,
            headers={"Authorization": "Bearer dev-local-key-1234"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_does_not_require_auth(client):
    # /health is public — monitoring tools must not need a key
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_disabled_key_returns_401(client):
    response = await client.post(
        "/v1/chat/completions",
        json=VALID_PAYLOAD,
        headers={"Authorization": "Bearer old-key-9999"},
    )
    assert response.status_code == 401
