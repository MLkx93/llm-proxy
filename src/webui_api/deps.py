"""Shared FastAPI dependencies for the webui_api (auth guards)."""
from fastapi import Header, HTTPException
from typing import Optional

from .services.auth_service import identity_from_header


async def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Require any authenticated user. Returns the identity payload."""
    identity = identity_from_header(authorization)
    if identity is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return identity


async def require_admin(authorization: Optional[str] = Header(default=None)) -> dict:
    """Require an authenticated user with the 'admin' role."""
    identity = identity_from_header(authorization)
    if identity is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    if identity.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return identity
