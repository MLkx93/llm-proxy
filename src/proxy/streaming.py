"""
Streaming response handlers.

Drives an SSE stream from OpenRouter through the StreamingCodeScanner,
forwarding safe chunks to the client in real-time and injecting an error
event the moment a malicious code block is detected.

Scan timing:
  - Text chunks forwarded immediately as they arrive
  - Scan fires when a closing ``` fence is encountered
  - If SAFE  → client already received the chunk, continue
  - If BLOCK → inject error SSE event, send [DONE], stop generator
"""
import json
from typing import AsyncGenerator

import httpx

from src.output_security.streaming_scanner import StreamingCodeScanner, ScanDecision
from src.proxy.logging import get_logger

logger = get_logger("streaming")


async def stream_openai_response(
    openai_body: dict,
    url: str,
    auth_headers: dict,
    scanner: StreamingCodeScanner,
    timeout: float = 60.0,
) -> AsyncGenerator[str, None]:
    """
    Streams an OpenAI-compatible SSE response from OpenRouter to the client,
    scanning each code block as it closes.

    Yields raw SSE lines (e.g. 'data: {...}\\n\\n').
    On a security block, yields a final error event then stops.
    """
    openai_body = {**openai_body, "stream": True}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            async with client.stream(
                "POST", url, json=openai_body, headers=auth_headers
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield _error_event("LLM_ERROR", f"Upstream returned {resp.status_code}: {error_body.decode()[:200]}")
                    yield "data: [DONE]\n\n"
                    return

                async for line in resp.aiter_lines():
                    if not line:
                        yield "\n"
                        continue

                    if not line.startswith("data: "):
                        yield line + "\n\n"
                        continue

                    data_str = line[6:]

                    if data_str.strip() == "[DONE]":
                        yield "data: [DONE]\n\n"
                        return

                    # Parse chunk and extract text delta
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        yield line + "\n\n"
                        continue

                    text_delta = _extract_openai_delta(chunk)

                    if text_delta:
                        decision: ScanDecision = scanner.feed(text_delta)
                        if not decision.safe:
                            logger.warning("streaming_blocked", extra={
                                "block_code": decision.block_code,
                            })
                            yield _error_event(decision.block_code, decision.block_reason)
                            yield "data: [DONE]\n\n"
                            return

                    yield line + "\n\n"

    except httpx.TimeoutException:
        yield _error_event("LLM_TIMEOUT", "LLM provider timed out during streaming.")
        yield "data: [DONE]\n\n"
    except Exception as exc:
        logger.error("streaming_error", extra={"error": str(exc)})
        yield _error_event("STREAM_ERROR", f"Streaming failed: {str(exc)[:200]}")
        yield "data: [DONE]\n\n"


def _extract_openai_delta(chunk: dict) -> str:
    """Extract text content from an OpenAI streaming chunk."""
    try:
        choices = chunk.get("choices", [])
        if not choices:
            return ""
        delta = choices[0].get("delta", {})
        return delta.get("content") or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _error_event(block_code: str, message: str) -> str:
    """Format a terminal error as an SSE event."""
    payload = json.dumps({"error": block_code, "message": message})
    return f"data: {payload}\n\n"
