import uuid
import time
import asyncio
import litellm

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .models import ChatCompletionRequest, ErrorResponse, ErrorDetail
from .logging import get_logger
from .auth import validate
from .rate_limiter import is_allowed
from src.input_policy import engine as input_policy
from src.output_security import engine as output_security
from src.output_security.engine import extract_response_text
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
        return _block("LLM_ERROR", "Upstream LLM call failed.", request_id, 502)

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
