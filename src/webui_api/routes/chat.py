"""
Chat route — gateway between the React app and the LLM Security Proxy.

Responsibilities:
  - Authenticate the caller via their JWT (issued by /api/auth/login).
  - Call the proxy with the proxy's own API key PLUS an X-User-Identity header,
    so the proxy's audit log can attribute events to a real user.
  - On a security block, return a STRUCTURED error (block_code, message, safe
    version, findings) so the React UI can render a rich block card — instead of
    collapsing it to a generic string (the old behaviour).
  - Support both buffered and streaming (SSE) responses.

Identity flows: React JWT  →  webui_api decodes  →  X-User-Identity to proxy.
The proxy is still authenticated by its own API key (config/api_keys.yaml).
"""
import json
import httpx
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional

from ..services.provider_service import provider_service
from ..services.dashboard_service import dashboard_service
from ..services.auth_service import identity_from_header

router = APIRouter(tags=["chat"])

# The proxy API key the gateway uses to authenticate to the security proxy.
# (Demo: matches config/api_keys.yaml. Real deployments would inject via env.)
PROXY_API_KEY = "dev-local-key-1234"


def _identity_header(authorization: Optional[str]) -> dict:
    """Build the X-User-Identity header from the caller's JWT, if present."""
    identity = identity_from_header(authorization)
    if not identity:
        return {}
    return {"X-User-Identity": json.dumps({
        "sub": identity.get("sub"),
        "name": identity.get("name"),
        "role": identity.get("role"),
    })}


def _safe_version_from(message: str) -> Optional[str]:
    import re
    if not message:
        return None
    m = re.search(r">=\s*([\w.]+)", message)
    return m.group(1) if m else None


def _structured_block(status_code: int, proxy_json: dict) -> dict:
    """
    Normalise a proxy error response into a consistent shape the UI can render.
    Handles both OpenAI ErrorResponse and FastAPI 'detail' shapes.
    """
    err = (proxy_json or {}).get("error") or {}
    code = err.get("code") or (proxy_json or {}).get("detail") or "BLOCKED"
    message = err.get("message") or (proxy_json or {}).get("detail") or "Request was blocked by the security proxy."
    return {
        "blocked": True,
        "status": status_code,
        "block_code": code if isinstance(code, str) else "BLOCKED",
        "message": message,
        "safe_version": _safe_version_from(message),
    }


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, authorization: Optional[str] = Header(default=None)):
    """Proxy a chat completion. Streaming when body.stream is true."""
    body = await request.json()
    proxy_url = provider_service.get_proxy_base_url()
    is_streaming = bool(body.get("stream"))

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PROXY_API_KEY}",
        **_identity_header(authorization),
    }

    if is_streaming:
        return await _stream(proxy_url, body, headers)

    # ── Buffered path ────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(f"{proxy_url}/v1/chat/completions", json=body, headers=headers)
    except httpx.TimeoutException:
        dashboard_service.record_request("error_requests")
        raise HTTPException(status_code=504, detail="Request to LLM proxy timed out")
    except httpx.ConnectError:
        dashboard_service.record_request("error_requests")
        raise HTTPException(status_code=502, detail="Could not connect to LLM Security Proxy on port 8080")

    if resp.status_code == 200:
        dashboard_service.record_request("allowed_requests")
        return resp.json()

    # Non-200 → structured block so the UI can render a rich card.
    dashboard_service.record_request("blocked_requests")
    try:
        proxy_json = resp.json()
    except Exception:
        proxy_json = {"detail": resp.text[:300]}
    return JSONResponse(status_code=200, content=_structured_block(resp.status_code, proxy_json))


async def _stream(proxy_url: str, body: dict, headers: dict) -> StreamingResponse:
    """
    Forward the proxy's SSE stream to the client, including the mid-stream block
    error event. We pass the proxy's events through unchanged; the React client
    interprets them (tokens vs. error).
    """
    async def event_gen():
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream(
                    "POST", f"{proxy_url}/v1/chat/completions", json=body, headers=headers
                ) as resp:
                    if resp.status_code != 200:
                        dashboard_service.record_request("blocked_requests")
                        raw = await resp.aread()
                        try:
                            proxy_json = json.loads(raw.decode())
                        except Exception:
                            proxy_json = {"detail": raw.decode()[:300]}
                        block = _structured_block(resp.status_code, proxy_json)
                        yield f"data: {json.dumps({'error': block['block_code'], 'message': block['message'], 'safe_version': block.get('safe_version')})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    dashboard_service.record_request("allowed_requests")
                    async for line in resp.aiter_lines():
                        if line:
                            yield line + "\n\n"
                        else:
                            yield "\n"
        except httpx.TimeoutException:
            dashboard_service.record_request("error_requests")
            yield f"data: {json.dumps({'error': 'LLM_TIMEOUT', 'message': 'LLM proxy timed out.'})}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.ConnectError:
            dashboard_service.record_request("error_requests")
            yield f"data: {json.dumps({'error': 'PROXY_UNREACHABLE', 'message': 'Could not connect to the security proxy on port 8080.'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
