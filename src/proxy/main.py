import uuid
import time
import hashlib
import asyncio
from typing import Optional
import httpx
import jwt
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .models import ChatCompletionRequest, ErrorResponse, ErrorDetail
from .models import AnthropicErrorResponse, AnthropicErrorDetail
from .models import AnthropicMessageRequest
from .logging import get_logger
from .auth import validate, validate_api_key
from .rate_limiter import is_allowed
from src.input_policy import engine as input_policy
from src.output_security import engine as output_security
from src.output_security.engine import extract_response_text, extract_response_text_anthropic
from src.output_security.streaming_scanner import StreamingCodeScanner
from src.proxy.streaming import stream_openai_response, stream_anthropic_response
import litellm
from config.settings import settings
from src.audit import logger as audit

logger = get_logger("proxy")

app = FastAPI(title="LLM Proxy", version="1.0.0")

# Built-in audit dashboard API (ships with the proxy — see src/proxy/audit_api.py)
from .audit_api import router as audit_api_router
app.include_router(audit_api_router)


@app.on_event("startup")
async def _init_audit_db():
    """Provision the audit DB schema on startup (best-effort; degrades to JSONL)."""
    try:
        from src.db.init import init_db
        await init_db()
    except Exception:
        pass

# Timeouts
LLM_TIMEOUT_S = settings.LLM_TIMEOUT_S
OUTPUT_CHECK_TIMEOUT_S = 10.0  # max seconds for Nexus validation


def _parse_identity(request: Request) -> dict:
    """
    Parse the optional X-User-Identity header set by the webui_api gateway.
    Returns {"user_sub": ..., "user_name": ...} or empty dict. Demo deliverable —
    lets the audit log attribute events to a real user without coupling the proxy
    to any identity provider.
    """
    import json as _json
    raw = request.headers.get("X-User-Identity")
    if not raw:
        return {}
    try:
        data = _json.loads(raw)
        return {"user_sub": data.get("sub"), "user_name": data.get("name")}
    except (ValueError, TypeError):
        return {}


def _last_user_text(messages: list[dict]) -> str:
    """Return the content of the last user message (for the admin display field)."""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content", "")
            return c if isinstance(c, str) else str(c)
    return ""


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
# Simple auth for admin console (same-origin, no CORS needed)
# ---------------------------------------------------------------------------

_ADMIN_ACCOUNTS = {
    "admin": {"password": "admin", "role": "admin"},
    "user": {"password": "user", "role": "user"},
}

@app.post("/api/auth/login")
async def admin_login(request: Request):
    """Simple JWT login for the admin console served from /admin."""
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "").strip()

        account = _ADMIN_ACCOUNTS.get(username)
        if not account or account["password"] != password:
            return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

        # Create a simple HS256 JWT (same as demo)
        token = jwt.encode(
            {
                "sub": username,
                "name": username,
                "exp": datetime.utcnow() + timedelta(hours=24),
            },
            settings.JWT_SECRET,
            algorithm="HS256"
        )

        return {
            "token": token,
            "user": {
                "sub": username,
                "name": username,
                "role": account["role"],
            }
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})

@app.get("/api/auth/me")
async def admin_me(request: Request):
    """Check current auth status for the admin console."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    token = auth[7:].strip()
    try:
        claims = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        username = claims.get("sub")
        account = _ADMIN_ACCOUNTS.get(username)
        if not account:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return {
            "sub": username,
            "name": username,
            "role": account["role"],
        }
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=401, content={"detail": "Token expired"})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=401, content={"detail": "Invalid token"})


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
    identity = _parse_identity(request)

    # --- Rate limiting ---
    if not is_allowed(app_id):
        logger.warning("rate_limited", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(request_id=request_id, app_id=app_id, action="BLOCKED", block_code="RATE_LIMITED", **identity)
        return _block("RATE_LIMITED", "Too many requests. Please slow down.", request_id, 429)

    raw = await request.json()
    if raw.get("stream") and not settings.STREAMING_ENABLED:
        audit.emit(request_id=request_id, app_id=app_id, action="BLOCKED", block_code="STREAMING_NOT_SUPPORTED")
        return _block("STREAMING_NOT_SUPPORTED", "Streaming is not supported. Set STREAMING_ENABLED=true or use stream=false.", request_id, 400)

    messages_raw = [m.model_dump() for m in body.messages]

    logger.info("request_received", extra={
        "request_id": request_id,
        "app_id": app_id,
        "model": body.model,
        "message_count": len(body.messages),
    })

    # --- Input Policy Engine ---
    sanitized_messages, policy, redaction_details = input_policy.check_and_sanitize_openai(messages_raw)
    if not policy.allowed:
        logger.warning("input_blocked", extra={
            "request_id": request_id,
            "app_id": app_id,
            "block_code": policy.block_code,
            "findings": policy.findings,
        })
        # For blocked requests, log a redacted version of the prompt to prevent secret leakage
        last_msg = _extract_last_user_text(messages_raw)
        redacted_prompt = _redact_secrets(last_msg)
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            messages=sanitized_messages, model=body.model,
            block_code=policy.block_code,
            latency_ms=_elapsed(start),
            findings=policy.findings,
            redaction_details=redaction_details,
            sanitized_prompt=redacted_prompt,
            block_reason=policy.block_reason,
            **identity,
        )
        return _block(policy.block_code, policy.block_reason, request_id, 400)

    # --- LLM call (with timeout) ---
    try:
        if settings.use_openrouter:
            # Use OpenRouter directly (OpenAI-compatible API)
            # Transform model name from Claude Code format to OpenRouter format
            transformed_model = settings.transform_model_name(body.model)
            logger.info("model_transformed", extra={
                "request_id": request_id,
                "original_model": body.model,
                "transformed_model": transformed_model,
            })
            
            openai_body = {
                "model": transformed_model,
                "messages": sanitized_messages,
            }
            if body.temperature is not None:
                openai_body["temperature"] = body.temperature
            if body.max_tokens is not None:
                openai_body["max_tokens"] = body.max_tokens

            # --- Streaming branch ---
            if body.stream and settings.STREAMING_ENABLED:
                auth_headers = {
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                }
                scanner = StreamingCodeScanner()
                logger.info("streaming_request", extra={"request_id": request_id, "app_id": app_id})
                return StreamingResponse(
                    stream_openai_response(
                        openai_body=openai_body,
                        url=f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                        auth_headers=auth_headers,
                        scanner=scanner,
                        timeout=LLM_TIMEOUT_S,
                    ),
                    media_type="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
                )

            async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT_S)) as client:
                response = await client.post(
                    f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                    json=openai_body,
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
                if response.status_code != 200:
                    raise Exception(f"OpenRouter returned {response.status_code}: {response.text}")
                response_dict = response.json()
        elif settings.use_litellm:
            # Use LiteLLM proxy (legacy mode)
            import litellm
            llm_kwargs: dict = dict(
                model=f"openai/{body.model}",
                messages=sanitized_messages,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                api_base=settings.LITELLM_API_BASE,
                api_key=settings.LITELLM_API_KEY,
            )
            response = await asyncio.wait_for(
                litellm.acompletion(**llm_kwargs),
                timeout=LLM_TIMEOUT_S,
            )
            response_dict = response.model_dump()
        else:
            raise Exception("No LLM provider configured. Set OPENROUTER_API_KEY or LITELLM_API_BASE.")
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
            "block_reason": output_policy.block_reason,
        })
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            messages=messages_raw, model=body.model,
            block_code=output_policy.block_code,
            latency_ms=_elapsed(start),
            sanitized_prompt=_last_user_text(sanitized_messages),
            llm_output=extract_response_text(response_dict),
            block_reason=output_policy.block_reason,
            safe_version=_extract_safe_version(output_policy.block_reason),
            **identity,
        )
        return _block(output_policy.block_code, output_policy.block_reason, request_id, 400)

    # --- Success ---
    latency_ms = _elapsed(start)
    log_extra = {
        "request_id": request_id,
        "app_id": app_id,
        "model": body.model,
        "latency_ms": latency_ms,
    }
    # Log redaction details if any occurred
    if redaction_details.get("redacted"):
        log_extra["redaction"] = {
            "pii_types": redaction_details.get("pii_types"),
            "count": redaction_details.get("redaction_count"),
            "method": redaction_details.get("redaction_method"),
        }
    logger.info("request_completed", extra=log_extra)
    audit.emit(
        request_id=request_id, app_id=app_id, action="ALLOWED",
        messages=messages_raw, model=body.model,
        latency_ms=latency_ms,
        findings=policy.findings if policy.findings else None,
        redaction_details=redaction_details,
        sanitized_prompt=_last_user_text(sanitized_messages),
        llm_output=extract_response_text(response_dict),
        **identity,
    )

    return JSONResponse(content=response_dict)


def _elapsed(start: float) -> int:
    return round((time.monotonic() - start) * 1000)


def _extract_safe_version(reason: str) -> Optional[str]:
    """Pull the suggested safe version out of a block reason like '... use >=2.3.1 instead'."""
    import re
    if not reason:
        return None
    m = re.search(r">=\s*([\w.]+)", reason)
    return m.group(1) if m else None


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


def _extract_last_user_text(messages: list[dict]) -> str:
    """Extract text from the last user message in a list of messages."""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, str):
                return c
            elif isinstance(c, list):
                # Claude Code bundles messages as blocks
                for block in reversed(c):
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
    return ""


def _redact_secrets(text: str) -> str:
    """Redact API keys and secrets from text using the input policy engine's patterns."""
    from src.input_policy.patterns import SECRET_PATTERNS

    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.pattern.sub("[REDACTED]", redacted)
    return redacted


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
async def anthropic_messages(request: Request, body: AnthropicMessageRequest):
    request_id = request.state.request_id
    start = time.monotonic()

    # --- Authentication (pass-through: user's LiteLLM key) ---
    # Check both x-api-key and authorization headers (different SDKs use different headers)
    user_api_key = request.headers.get("x-api-key", "")
    if not user_api_key:
        # Anthropic SDK sends Authorization: Bearer when ANTHROPIC_API_KEY is set
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            user_api_key = auth_header[7:].strip()
    if not user_api_key:
        logger.warning("unauthorized", extra={"request_id": request_id})
        audit.emit(request_id=request_id, app_id=None, action="BLOCKED", block_code="UNAUTHORIZED")
        return _anthropic_block("UNAUTHORIZED", "Missing API key.", 401)

    # Derive an app_id from the key for rate limiting and audit (hash to avoid logging raw keys)
    app_id = f"key-{hashlib.sha256(user_api_key.encode()).hexdigest()[:12]}"
    request.state.app_id = app_id
    identity = _parse_identity(request)

    # --- Rate limiting ---
    if not is_allowed(app_id):
        logger.warning("rate_limited", extra={"request_id": request_id, "app_id": app_id})
        audit.emit(request_id=request_id, app_id=app_id, action="BLOCKED", block_code="RATE_LIMITED", **identity)
        return _anthropic_block("RATE_LIMITED", "Too many requests. Please slow down.", 429)

    # --- Parse body ---
    model = body.model
    is_streaming = body.stream

    logger.info("request_received", extra={
        "request_id": request_id,
        "app_id": app_id,
        "model": model,
        "message_count": len(body.messages),
        "endpoint": "/v1/messages",
        "stream": is_streaming,
    })

    # --- Input Policy Engine ---
    # Check last message for violations (block if found).
    # Redact violations in older messages (don't block, just sanitize).
    sanitized_body, policy, redaction_details = input_policy.check_and_sanitize_anthropic(body.model_dump())
    prompt_text = input_policy.extract_text_anthropic(body.model_dump())
    p_hash = _hash_text(prompt_text)

    if not policy.allowed:
        logger.warning("input_blocked", extra={
            "request_id": request_id,
            "app_id": app_id,
            "block_code": policy.block_code,
            "findings": policy.findings,
        })
        # For blocked requests, log a redacted version of the prompt to prevent secret leakage
        redacted_prompt = _redact_secrets(prompt_text)
        audit.emit(
            request_id=request_id, app_id=app_id, action="BLOCKED",
            model=model, block_code=policy.block_code,
            prompt_hash=p_hash, latency_ms=_elapsed(start),
            findings=policy.findings,
            redaction_details=redaction_details,
            sanitized_prompt=redacted_prompt,
        )
        return _anthropic_block(policy.block_code, policy.block_reason, 400)

    # --- LLM call based on provider configuration ---
    # Translate Anthropic request → OpenAI format (using sanitized body)
    openai_body = _anthropic_to_openai(sanitized_body)
    
    # Transform model name from Claude Code format to OpenRouter format
    transformed_model = settings.transform_model_name(model)
    logger.info("model_transformed", extra={
        "request_id": request_id,
        "original_model": model,
        "transformed_model": transformed_model,
    })
    
    if settings.use_openrouter:
        # Use OpenRouter directly
        # Update the model in openai_body to the transformed model
        openai_body["model"] = transformed_model
        upstream_url = f"{settings.OPENROUTER_BASE_URL}/chat/completions"
        upstream_headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        # --- Streaming branch ---
        if is_streaming and settings.STREAMING_ENABLED:
            scanner = StreamingCodeScanner()
            logger.info("streaming_request", extra={"request_id": request_id, "app_id": app_id, "endpoint": "/v1/messages"})
            return StreamingResponse(
                stream_anthropic_response(
                    openai_body=openai_body,
                    url=upstream_url,
                    auth_headers=upstream_headers,
                    scanner=scanner,
                    model=model,
                    timeout=LLM_TIMEOUT_S,
                ),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
            )

    elif settings.use_litellm:
        # Use LiteLLM proxy (legacy mode)
        upstream_url = f"{settings.LITELLM_API_BASE.rstrip('/')}/v1/chat/completions"
        upstream_headers = {
            "content-type": "application/json",
            "x-api-key": user_api_key,  # pass-through: user's own LiteLLM key
        }
    else:
        audit.emit(
            request_id=request_id, app_id=app_id, action="ERROR",
            model=model, block_code="NO_UPSTREAM",
            prompt_hash=p_hash, latency_ms=_elapsed(start),
        )
        return _anthropic_block("NO_UPSTREAM", "No upstream LLM server configured.", 502)

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
    log_extra = {
        "request_id": request_id,
        "app_id": app_id,
        "model": model,
        "latency_ms": latency_ms,
        "endpoint": "/v1/messages",
    }
    # Log redaction details if any occurred
    if redaction_details.get("redacted"):
        log_extra["redaction"] = {
            "pii_types": redaction_details.get("pii_types"),
            "count": redaction_details.get("redaction_count"),
            "method": redaction_details.get("redaction_method"),
        }
    logger.info("request_completed", extra=log_extra)
    audit.emit(
        request_id=request_id, app_id=app_id, action="ALLOWED",
        model=model, prompt_hash=p_hash, latency_ms=latency_ms,
        findings=policy.findings if policy.findings else None,
        redaction_details=redaction_details,
    )

    return JSONResponse(content=response_dict)


# ---------------------------------------------------------------------------
# Admin dashboard (static SPA) — served by the proxy itself at /admin
# ---------------------------------------------------------------------------
# The proxy ships its own admin console. Built from the React app with
# REACT_APP_AUTH_MODE=keycloak into src/webui-react/build (or a dedicated
# admin build dir). Mounted LAST so it never shadows the API routes above.
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles
from fastapi.responses import FileResponse as _FileResponse, HTMLResponse as _HTMLResponse

_ADMIN_BUILD = _Path(__file__).parent.parent / "webui-react" / "build"

@app.get("/admin")
@app.get("/admin/{full_path:path}")
async def serve_admin(full_path: str = ""):
    """Serve the admin SPA with rewritten asset paths."""
    if not _ADMIN_BUILD.exists():
        return _FileResponse(status_code=404)

    # Try to serve a specific file (e.g. /admin/favicon.ico)
    candidate = _ADMIN_BUILD / full_path
    if full_path and candidate.exists() and candidate.is_file():
        return _FileResponse(candidate)

    # Serve index.html, rewriting /static/ → /admin/static/
    index_path = _ADMIN_BUILD / "index.html"
    if index_path.exists():
        html = index_path.read_text()
        # Rewrite asset paths
        html = html.replace('src="/static/', 'src="/admin/static/')
        html = html.replace('href="/static/', 'href="/admin/static/')
        return _HTMLResponse(html, media_type="text/html; charset=utf-8")

    return _FileResponse(_ADMIN_BUILD / "index.html")

# Mount static assets at /admin/static/
if _ADMIN_BUILD.exists():
    app.mount("/admin/static", _StaticFiles(directory=_ADMIN_BUILD / "static"), name="admin-static")
