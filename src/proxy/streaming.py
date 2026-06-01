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


async def stream_anthropic_response(
    openai_body: dict,
    url: str,
    auth_headers: dict,
    scanner: StreamingCodeScanner,
    model: str,
    timeout: float = 60.0,
) -> AsyncGenerator[str, None]:
    """
    Streams an OpenRouter response (OpenAI SSE format) to the client in
    Anthropic SSE format, scanning code blocks in real-time.

    Anthropic SSE format expected by Claude SDK:
      event: message_start      → message metadata
      event: content_block_start
      event: content_block_delta → text deltas
      event: content_block_stop
      event: message_delta      → stop reason + usage
      event: message_stop
    """
    import uuid
    openai_body = {**openai_body, "stream": True}
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            async with client.stream(
                "POST", url, json=openai_body, headers=auth_headers
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield _anthropic_error_event("LLM_ERROR", f"Upstream returned {resp.status_code}: {error_body.decode()[:200]}")
                    return

                # Send opening events
                yield _sse("message_start", {
                    "type": "message_start",
                    "message": {
                        "id": msg_id, "type": "message", "role": "assistant",
                        "content": [], "model": model,
                        "stop_reason": None, "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    }
                })
                yield _sse("content_block_start", {
                    "type": "content_block_start", "index": 0,
                    "content_block": {"type": "text", "text": ""}
                })
                yield _sse("ping", {"type": "ping"})

                output_tokens = 0
                stop_reason = "end_turn"

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    text_delta = _extract_openai_delta(chunk)

                    # Track finish reason and token usage
                    choice = chunk.get("choices", [{}])[0]
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
                        stop_reason = "end_turn" if finish == "stop" else "max_tokens"
                    usage = chunk.get("usage") or {}
                    if usage.get("completion_tokens"):
                        output_tokens = usage["completion_tokens"]

                    if text_delta:
                        decision: ScanDecision = scanner.feed(text_delta)
                        if not decision.safe:
                            logger.warning("streaming_blocked", extra={"block_code": decision.block_code})
                            yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
                            yield _anthropic_error_event(decision.block_code, decision.block_reason)
                            return

                        yield _sse("content_block_delta", {
                            "type": "content_block_delta", "index": 0,
                            "delta": {"type": "text_delta", "text": text_delta}
                        })

                # Send closing events
                yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
                yield _sse("message_delta", {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                    "usage": {"output_tokens": output_tokens},
                })
                yield _sse("message_stop", {"type": "message_stop"})

    except httpx.TimeoutException:
        yield _anthropic_error_event("LLM_TIMEOUT", "LLM provider timed out during streaming.")
    except Exception as exc:
        logger.error("streaming_error", extra={"error": str(exc)})
        yield _anthropic_error_event("STREAM_ERROR", f"Streaming failed: {str(exc)[:200]}")


def _sse(event: str, data: dict) -> str:
    """Format an Anthropic SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _anthropic_error_event(block_code: str, message: str) -> str:
    """Format a terminal error as an Anthropic SSE error event."""
    payload = {"type": "error", "error": {"type": "invalid_request_error", "message": f"[{block_code}] {message}"}}
    return f"event: error\ndata: {json.dumps(payload)}\n\n"


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
