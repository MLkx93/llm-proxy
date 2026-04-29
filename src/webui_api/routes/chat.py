"""Chat completion API route - proxies requests to the LLM Security Proxy."""

import httpx
from fastapi import APIRouter, HTTPException, Request

from ..services.provider_service import provider_service
from ..services.dashboard_service import dashboard_service

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completion requests to the LLM Security Proxy.

    The proxy handles all security scanning before forwarding to the LLM provider.
    """
    try:
        body = await request.json()
        proxy_url = provider_service.get_proxy_base_url()

        # Forward to the LLM Security Proxy (port 8080)
        # The proxy applies security policies and routes to the active provider
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{proxy_url}/v1/chat/completions",
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": request.headers.get("Authorization", ""),
                },
            )

        # Record the outcome
        if response.status_code == 200:
            dashboard_service.record_request("allowed_requests")
        else:
            dashboard_service.record_request("blocked_requests")

        return response.json()

    except httpx.TimeoutException:
        dashboard_service.record_request("error_requests")
        raise HTTPException(status_code=504, detail="Request to LLM proxy timed out")
    except httpx.ConnectError:
        dashboard_service.record_request("error_requests")
        raise HTTPException(
            status_code=502,
            detail="Could not connect to LLM Security Proxy. Make sure it is running on port 8080",
        )
    except Exception as e:
        dashboard_service.record_request("error_requests")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
