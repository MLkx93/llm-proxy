"""Provider management API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.provider_service import provider_service

router = APIRouter(prefix="/api/providers", tags=["providers"])


class SwitchProviderRequest(BaseModel):
    provider_id: str


class SetApiKeyRequest(BaseModel):
    provider_id: str
    api_key: str


@router.get("")
async def get_providers():
    """Get all providers with their status."""
    return provider_service.get_providers()


@router.get("/{provider_id}/models")
async def get_provider_models(provider_id: str):
    """Get models for a specific provider."""
    result = provider_service.get_models(provider_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")
    return result


@router.post("/switch")
async def switch_provider(request: SwitchProviderRequest):
    """Switch the active provider."""
    result = provider_service.switch_provider(request.provider_id)
    if result is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {request.provider_id}")
    return result


@router.post("/api-key")
async def set_api_key(request: SetApiKeyRequest):
    """Set API key for a provider."""
    result = provider_service.set_api_key(request.provider_id, request.api_key)
    if result is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {request.provider_id}")
    return result