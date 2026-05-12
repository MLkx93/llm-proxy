"""
Integration tests for the core proxy pass-through.
LiteLLM is mocked so no real LLM API key is needed.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from src.proxy.main import app


FAKE_RESPONSE = MagicMock()
FAKE_RESPONSE.model_dump.return_value = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello, world!"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}

AUTH = {"Authorization": "Bearer dev-local-key-1234"}


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_chat_completions_pass_through(client):
    with patch("src.proxy.main.settings.OPENROUTER_API_KEY", ""), \
         patch("src.proxy.main.settings.LITELLM_API_BASE", "http://fake"), \
         patch("src.proxy.main.settings.LITELLM_API_KEY", "fake"):
        with patch("src.proxy.main.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = FAKE_RESPONSE
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Say hello"}]},
                headers=AUTH,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Hello, world!"
        assert "X-Request-Id" in response.headers


@pytest.mark.asyncio
async def test_streaming_is_rejected(client):
    response = await client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}], "stream": True},
        headers=AUTH,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "STREAMING_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_llm_error_returns_502(client):
    with patch("src.proxy.main.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("provider unavailable")
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
            headers=AUTH,
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "LLM_ERROR"
