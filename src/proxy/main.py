import uuid
import time
import hashlib
import asyncio
import litellm
import httpx

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .models import ChatCompletionRequest, ErrorResponse, ErrorDetail
from .models import AnthropicErrorResponse, AnthropicErrorDetail
from .logging import get_logger
from .auth import validate, validate_api_key
from .rate_limiter import is_allowed
from src.input_policy import engine as input_policy
from src.output_security import engine as output_security
from src.output_security.engine import extract_response_text, extract_response_text_anthropic
from config.settings import settings
from src.audit import logger as audit

logger = get_logger("proxy")

app = FastAPI(title="LLM Proxy", version="1.0.0")

# Timeouts
LLM_TIMEOUT_S = 60.0        # max seconds to wait for LLM provider
OUTPUT_CHECK_TIMEOUT_S = 10.0  # max seconds for Nexus validation


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    request.state.app_id = None
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


# ---------------------------------------------------------------------------
# Health & Readiness
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Liveness probe — is the process alive?"""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """
    Readiness probe — is the proxy ready to serve traffic?
    Checks that critical dependencies (config) are in place.
    Currently lightweight; extend to ping Nexus when needed.
    """
    from config.settings import settings
    issues = []
    if not settings.NEXUS_BASE_URL:
        issues.append("NEXUS_BASE_URL not configured")
    if issues:
        return JSONResponse(status_code=503, content={"status": "not_ready", "issues": issues})
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    request_id = request.state.request_id
    start = time.monotonic()

    # --- Authentication ---
    key_entry = validate(request.headers.get("Authorization"))
    if key_entry is None:
        logger.warning("unauthorized", extra={"request_id": request_id})
        audit.emit(request_id=request_id, app_id=None, action="BLOCKED", block_code="UNAUTHORIZED")
        return _block("UNAUTHORIZED", "Missing or invalid API key.", request_id, 401)

    app_id = key_entry.app_id
    request.state.app_id = app_id

    # --- Rate limiting ---
    if not is_allowed(app_id):
        logger.warning("rate_limited", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(request_id=request_id, app_id=app_id, action="BLOCKED", block_code="RATE_LIMITED")
        return _block("RATE_LIMITED", "Too many requests. Please slow down.", request_id, 429)

    # Reject streaming attempts explicitly
    raw = await request.json()
    if raw.get("stream"):
        audit.emit(request_id=request_id, app_id=app_id, action="BLOCKED", block_code="STREAMING_NOT_SUPPORTED")
        return _block("STREAMING_NOT_SUPPORTED", "Streaming is not supported in v1. Set stream=false.", request_id, 400)

    messages_raw = [m.model_dump() for m in body.messages]

    logger.info("request_received", extra={
        "request_id": request_id,
        "app_id": app_id,
        "model": body.model,
        "message_count": len(body.messages),
    })

    # --- Input Policy Engine ---
    policy = input_policy.check(messages_raw)
    if not policy.allowed:
        logger.warning("input_blocked", extra={
            "request_id": request_id,
            "app_id": app_id,
            "block_code": policy.block_code,
            "findings": policy.findings,
        })
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            messages=messages_raw, model=body.model,
            block_code=policy.block_code,
            latency_ms=_elapsed(start),
        )
        return _block(policy.block_code, policy.block_reason, request_id, 400)

    # --- LLM call (with timeout) ---
    try:
        # Build LLM call kwargs — route through LiteLLM proxy if configured
        llm_kwargs: dict = dict(
            model=body.model,
            messages=messages_raw,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        if settings.LITELLM_API_BASE:
            # When routing through a LiteLLM proxy, force OpenAI-compatible
            # format by prefixing the model name with "openai/"
            llm_kwargs["model"] = f"openai/{body.model}"
            llm_kwargs["api_base"] = settings.LITELLM_API_BASE
            llm_kwargs["api_key"] = settings.LITELLM_API_KEY

        response = await asyncio.wait_for(
            litellm.acompletion(**llm_kwargs),
            timeout=LLM_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error("llm_timeout", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(
            request_id=request_id, app_id=app_id, action="ERROR",
            messages=messages_raw, model=body.model,
            block_code="LLM_TIMEOUT",
            latency_ms=_elapsed(start),
        )
        return _block("LLM_TIMEOUT", "LLM provider did not respond in time.", request_id, 504)
    except Exception as exc:
        logger.error("llm_error", extra={"request_id": request_id, "app_id": app_id, "error": str(exc)})
        audit.emit(
            request_id=request_id, app_id=app_id, action="ERROR",
            messages=messages_raw, model=body.model,
            block_code="LLM_ERROR",
            latency_ms=_elapsed(start),
        )
        return _block("LLM_ERROR", f"Upstream LLM call failed: {exc}", request_id, 502)

    # --- Output Security Engine (with timeout) ---
    response_dict = response.model_dump()
    try:
        output_policy = await asyncio.wait_for(
            output_security.check(extract_response_text(response_dict)),
            timeout=OUTPUT_CHECK_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error("output_check_timeout", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            messages=messages_raw, model=body.model,
            block_code="NEXUS_UNAVAILABLE",
            latency_ms=_elapsed(start),
        )
        return _block("NEXUS_UNAVAILABLE", "Dependency validation timed out.", request_id, 400)

    if not output_policy.allowed:
        logger.warning("output_blocked", extra={
            "request_id": request_id,
            "app_id": app_id,
            "block_code": output_policy.block_code,
            "blocked_packages": output_policy.blocked_packages,
        })
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            messages=messages_raw, model=body.model,
            block_code=output_policy.block_code,
            latency_ms=_elapsed(start),
        )
        return _block(output_policy.block_code, output_policy.block_reason, request_id, 400)

    # --- Success ---
    latency_ms = _elapsed(start)
    logger.info("request_completed", extra={
        "request_id": request_id,
        "app_id": app_id,
        "model": body.model,
        "latency_ms": latency_ms,
    })
    audit.emit(
        request_id=request_id, app_id=app_id, action="ALLOWED",
        messages=messages_raw, model=body.model,
        latency_ms=latency_ms,
    )

    return JSONResponse(content=response_dict)


def _elapsed(start: float) -> int:
    return round((time.monotonic() - start) * 1000)


def _block(code: str, message: str, request_id: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            error=ErrorDetail(code=code, message=message, request_id=request_id)
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Anthropic error type mapping
# ---------------------------------------------------------------------------
_ANTHROPIC_ERROR_TYPE = {
    400: "invalid_request_error",
    401: "authentication_error",
    429: "rate_limit_error",
    502: "api_error",
    504: "api_error",
}


def _anthropic_block(code: str, message: str, status: int = 400) -> JSONResponse:
    """Return an error in the format the Anthropic SDK expects."""
    error_type = _ANTHROPIC_ERROR_TYPE.get(status, "invalid_request_error")
    return JSONResponse(
        status_code=status,
        content=AnthropicErrorResponse(
            error=AnthropicErrorDetail(type=error_type, message=f"[{code}] {message}")
        ).model_dump(),
    )


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _buffer_sse_response(sse_response: httpx.Response) -> dict:
    """
    Buffer an SSE stream from the upstream LiteLLM server and reassemble
    into a complete Anthropic response dict.

    SSE format: lines of 'event: ...' and 'data: {...}'.
    We collect content_block_delta events to reconstruct the full text,
    then use the message_stop/message_delta event for final metadata.
    """
    import json as _json

    full_text = []
    final_response = {}
    model = ""
    msg_id = ""
    input_tokens = 0
    output_tokens = 0
    stop_reason = None

    async for line in sse_response.aiter_lines():
        if not line.startswith("data: "):
            continue
        data_str = line[6:]  # strip "data: "
        if data_str.strip() == "[DONE]":
            break
        try:
            chunk = _json.loads(data_str)
        except _json.JSONDecodeError:
            continue

        event_type = chunk.get("type", "")

        if event_type == "message_start":
            msg = chunk.get("message", {})
            msg_id = msg.get("id", "")
            model = msg.get("model", "")
            usage = msg.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)

        elif event_type == "content_block_delta":
            delta = chunk.get("delta", {})
            if delta.get("type") == "text_delta":
                full_text.append(delta.get("text", ""))

        elif event_type == "message_delta":
            delta = chunk.get("delta", {})
            stop_reason = delta.get("stop_reason")
            usage = chunk.get("usage", {})
            output_tokens = usage.get("output_tokens", 0)

    # Reassemble into a standard Anthropic non-streamed response
    final_response = {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "".join(full_text)}],
        "model": model,
        "stop_reason": stop_reason or "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }
    return final_response


# ---------------------------------------------------------------------------
# Anthropic ↔ OpenAI format translation
# ---------------------------------------------------------------------------

def _anthropic_to_openai(body: dict) -> dict:
    """Translate an Anthropic Messages request into OpenAI chat/completions format."""
    messages = []

    # Anthropic "system" is a top-level field; OpenAI uses a system message
    system = body.get("system")
    if system:
        if isinstance(system, str):
            messages.append({"role": "system", "content": system})
        elif isinstance(system, list):
            # Anthropic system can be a list of content blocks
            text = " ".join(b.get("text", "") for b in system if b.get("type") == "text")
            if text:
                messages.append({"role": "system", "content": text})

    for msg in body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            # Anthropic content blocks → concatenate text blocks
            text = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
            messages.append({"role": role, "content": text})

    openai_body: dict = {
        "model": body.get("model", ""),
        "messages": messages,
        "stream": False,  # always buffer
    }
    if body.get("max_tokens"):
        openai_body["max_tokens"] = body["max_tokens"]
    if body.get("temperature") is not None:
        openai_body["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        openai_body["top_p"] = body["top_p"]
    if body.get("stop_sequences"):
        openai_body["stop"] = body["stop_sequences"]
    return openai_body


def _openai_to_anthropic(openai_resp: dict, model: str) -> dict:
    """Translate an OpenAI chat/completions response into Anthropic Messages format."""
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    text = message.get("content", "")
    finish = choice.get("finish_reason", "stop")
    usage = openai_resp.get("usage", {})

    # Map OpenAI finish reasons to Anthropic stop reasons
    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }

    return {
        "id": openai_resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": model,
        "stop_reason": stop_reason_map.get(finish, "end_turn"),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ---------------------------------------------------------------------------
# Anthropic Messages API Gateway — POST /v1/messages
# ---------------------------------------------------------------------------

@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    request_id = request.state.request_id
    start = time.monotonic()

    # --- Authentication (x-api-key header) ---
    key_entry = validate_api_key(request.headers.get("x-api-key"))
    if key_entry is None:
        logger.warning("unauthorized", extra={"request_id": request_id})
        audit.emit(request_id=request_id, app_id=None, action="BLOCKED", block_code="UNAUTHORIZED")
        return _anthropic_block("UNAUTHORIZED", "Missing or invalid API key.", 401)

    app_id = key_entry.app_id
    request.state.app_id = app_id

    # --- Rate limiting ---
    if not is_allowed(app_id):
        logger.warning("rate_limited", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(request_id=request_id, app_id=app_id, action="BLOCKED", block_code="RATE_LIMITED")
        return _anthropic_block("RATE_LIMITED", "Too many requests. Please slow down.", 429)

    # --- Parse body ---
    body = await request.json()
    model = body.get("model", "")
    is_streaming = body.get("stream", False)

    logger.info("request_received", extra={
        "request_id": request_id,
        "app_id": app_id,
        "model": model,
        "message_count": len(body.get("messages", [])),
        "endpoint": "/v1/messages",
        "stream": is_streaming,
    })

    # --- Input Policy Engine ---
    prompt_text = input_policy.extract_text_anthropic(body)
    policy = input_policy.check_text(prompt_text)
    p_hash = _hash_text(prompt_text)

    if not policy.allowed:
        logger.warning("input_blocked", extra={
            "request_id": request_id,
            "app_id": app_id,
            "block_code": policy.block_code,
            "findings": policy.findings,
        })
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            model=model, block_code=policy.block_code,
            prompt_hash=p_hash, latency_ms=_elapsed(start),
        )
        return _anthropic_block(policy.block_code, policy.block_reason, 400)

    # --- Forward to upstream LiteLLM server (OpenAI-compatible) ---
    if not settings.LITELLM_API_BASE:
        audit.emit(
            request_id=request_id, app_id=app_id, action="ERROR",
            model=model, block_code="NO_UPSTREAM",
            prompt_hash=p_hash, latency_ms=_elapsed(start),
        )
        return _anthropic_block("NO_UPSTREAM", "No upstream LLM server configured.", 502)

    # Translate Anthropic request → OpenAI format
    openai_body = _anthropic_to_openai(body)
    upstream_url = f"{settings.LITELLM_API_BASE.rstrip('/')}/v1/chat/completions"
    upstream_headers = {
        "content-type": "application/json",
        "x-api-key": settings.LITELLM_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT_S)) as client:
            upstream_resp = await client.post(
                upstream_url, json=openai_body, headers=upstream_headers,
            )
            if upstream_resp.status_code != 200:
                raise Exception(f"Upstream returned {upstream_resp.status_code}: {upstream_resp.text}")
            openai_response = upstream_resp.json()

    except httpx.TimeoutException:
        logger.error("llm_timeout", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(
            request_id=request_id, app_id=app_id, action="ERROR",
            model=model, block_code="LLM_TIMEOUT",
            prompt_hash=p_hash, latency_ms=_elapsed(start),
        )
        return _anthropic_block("LLM_TIMEOUT", "LLM provider did not respond in time.", 504)
    except Exception as exc:
        logger.error("llm_error", extra={"request_id": request_id, "app_id": app_id, "error": str(exc)})
        audit.emit(
            request_id=request_id, app_id=app_id, action="ERROR",
            model=model, block_code="LLM_ERROR",
            prompt_hash=p_hash, latency_ms=_elapsed(start),
        )
        return _anthropic_block("LLM_ERROR", f"Upstream LLM call failed: {exc}", 502)

    # Translate OpenAI response → Anthropic format
    response_dict = _openai_to_anthropic(openai_response, model)

    # --- Output Security Engine ---
    response_text = extract_response_text_anthropic(response_dict)
    try:
        output_policy = await asyncio.wait_for(
            output_security.check(response_text),
            timeout=OUTPUT_CHECK_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error("output_check_timeout", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            model=model, block_code="NEXUS_UNAVAILABLE",
            prompt_hash=p_hash, latency_ms=_elapsed(start),
        )
        return _anthropic_block("NEXUS_UNAVAILABLE", "Dependency validation timed out.", 400)

    if not output_policy.allowed:
        logger.warning("output_blocked", extra={
            "request_id": request_id,
            "app_id": app_id,
            "block_code": output_policy.block_code,
            "blocked_packages": output_policy.blocked_packages,
        })
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            model=model, block_code=output_policy.block_code,
            prompt_hash=p_hash, latency_ms=_elapsed(start),
        )
        return _anthropic_block(output_policy.block_code, output_policy.block_reason, 400)

    # --- Success ---
    latency_ms = _elapsed(start)
    logger.info("request_completed", extra={
        "request_id": request_id,
        "app_id": app_id,
        "model": model,
        "latency_ms": latency_ms,
        "endpoint": "/v1/messages",
    })
    audit.emit(
        request_id=request_id, app_id=app_id, action="ALLOWED",
        model=model, prompt_hash=p_hash, latency_ms=latency_ms,
    )

    return JSONResponse(content=response_dict)
