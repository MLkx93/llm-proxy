"""
Audit routes (demo gateway) — a thin CONSUMER of the proxy's built-in audit API.

The dashboard data now lives with the proxy (src/proxy/audit_api.py, served at
:8080/v1/audit/*). This module forwards the browser's requests there, attaching
the proxy API key. It keeps the demo's admin-JWT gate so the browser still needs
to log in, but the data itself comes from the product — demonstrating that the
dashboard ships with the proxy and the UI is merely one consumer.
"""
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

from ..deps import require_admin
from ..services.provider_service import provider_service

router = APIRouter(prefix="/api/audit", tags=["audit"])

# Proxy API key the gateway uses to read the proxy's audit endpoints.
PROXY_API_KEY = "dev-local-key-1234"


async def _proxy_get(path: str, params: dict) -> dict:
    base = provider_service.get_proxy_base_url()
    headers = {"Authorization": f"Bearer {PROXY_API_KEY}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{base}{path}", params=params, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Proxy audit API returned {resp.status_code}")
    return resp.json()


@router.get("/stats")
async def get_stats(time_range: str = Query("24h"), _admin: dict = Depends(require_admin)):
    """Forward to the proxy's built-in /v1/audit/stats."""
    try:
        return await _proxy_get("/v1/audit/stats", {"time_range": time_range})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Proxy unreachable: {exc}")


@router.get("/logs")
async def get_logs(
    time_range: str = Query("24h"),
    status: str = Query("ALL"),
    block_code: str = Query("ALL"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    _admin: dict = Depends(require_admin),
):
    """Forward to the proxy's built-in /v1/audit/logs."""
    params = {
        "time_range": time_range, "status": status, "block_code": block_code,
        "page": page, "page_size": page_size,
    }
    if search:
        params["search"] = search
    try:
        return await _proxy_get("/v1/audit/logs", params)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Proxy unreachable: {exc}")
