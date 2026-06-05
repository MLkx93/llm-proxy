"""Auth routes — demo login gate (login + current user)."""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from ..services.auth_service import authenticate, issue_token, identity_from_header

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    """Validate credentials against the hardcoded demo accounts; return a JWT."""
    identity = authenticate(body.username, body.password)
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = issue_token(identity)
    return {"token": token, "user": identity}


@router.get("/me")
async def me(authorization: Optional[str] = Header(default=None)):
    """Return the current user from the bearer token, or 401."""
    identity = identity_from_header(authorization)
    if identity is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"sub": identity.get("sub"), "name": identity.get("name"), "role": identity.get("role")}
