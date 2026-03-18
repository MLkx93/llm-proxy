"""
Tests for Phase 6: health/readiness endpoints, rate limiting, and timeouts.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from src.proxy.main import app
from src.proxy.rate_limiter import is_allowed, reset, MAX_TOKENS

AUTH = {"Authorization": "Bearer dev-local-key-1234"}

FAKE_RESPONSE = MagicMock()
FAKE_RESPONSE.model_dump.return_value = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
}

VALID_PAYLOAD = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Health & Readiness
# ---------------------------------------------------------------------------
class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client):
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ready_without_nexus_config_returns_503(self, client):
        # NEXUS_BASE_URL is empty in test env
        response = await client.get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert any("NEXUS_BASE_URL" in issue for issue in body["issues"])

    @pytest.mark.asyncio
    async def test_ready_with_nexus_config_returns_200(self, client):
        import config.settings as s
        s.settings.NEXUS_BASE_URL = "http://nexus.internal"
        response = await client.get("/ready")
        s.settings.NEXUS_BASE_URL = ""
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------
class TestRateLimiter:
    def test_first_request_allowed(self):
        reset("test-app")
        assert is_allowed("test-app") is True

    def test_requests_within_capacity_allowed(self):
        reset("test-app-b")
        for _ in range(MAX_TOKENS):
            assert is_allowed("test-app-b") is True

    def test_request_beyond_capacity_denied(self):
        reset("test-app-c")
        for _ in range(MAX_TOKENS):
            is_allowed("test-app-c")
        # Next one should be denied
        assert is_allowed("test-app-c") is False

    def test_different_apps_isolated(self):
        reset("app-alpha")
        reset("app-beta")
        # Exhaust alpha
        for _ in range(MAX_TOKENS):
            is_allowed("app-alpha")
        assert is_allowed("app-alpha") is False
        # Beta is unaffected
        assert is_allowed("app-beta") is True

    def test_tokens_refill_over_time(self):
        import time
        reset("refill-app")
        for _ in range(MAX_TOKENS):
            is_allowed("refill-app")
        assert is_allowed("refill-app") is False
        # Wait for 1 token to refill (1 token/sec)
        time.sleep(1.1)
        assert is_allowed("refill-app") is True


# ---------------------------------------------------------------------------
# Rate limiting integration (proxy returns 429)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limited_returns_429(client):
    reset("local-dev")  # reset so we control the bucket
    # Exhaust the bucket
    for _ in range(MAX_TOKENS):
        is_allowed("local-dev")
    # Next request through the proxy should be 429
    response = await client.post("/v1/chat/completions", json=VALID_PAYLOAD, headers=AUTH)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    reset("local-dev")  # clean up so other tests aren't affected


# ---------------------------------------------------------------------------
# Timeout tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_llm_timeout_returns_504(client):
    async def slow(*args, **kwargs):
        await asyncio.sleep(999)

    with patch("src.proxy.main.litellm.acompletion", side_effect=slow):
        with patch("src.proxy.main.LLM_TIMEOUT_S", 0.05):
            response = await client.post("/v1/chat/completions", json=VALID_PAYLOAD, headers=AUTH)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "LLM_TIMEOUT"


@pytest.mark.asyncio
async def test_output_check_timeout_returns_400(client):
    async def slow_check(*args, **kwargs):
        await asyncio.sleep(999)

    with patch("src.proxy.main.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = FAKE_RESPONSE
        with patch("src.proxy.main.output_security.check", side_effect=slow_check):
            with patch("src.proxy.main.OUTPUT_CHECK_TIMEOUT_S", 0.05):
                response = await client.post("/v1/chat/completions", json=VALID_PAYLOAD, headers=AUTH)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "NEXUS_UNAVAILABLE"
