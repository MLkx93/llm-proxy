"""
Demo auth service — a simple login gate for the thesis defence.

NOT production-grade: accounts are hardcoded in settings (DEMO_ACCOUNTS) and
passwords are compared in plaintext. The goal is only to keep the admin panel
behind a login and demonstrate the user/admin role split. JWTs are HS256-signed
so the frontend can carry identity and roles across requests.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt

from config.settings import settings


def _parse_accounts() -> dict[str, dict]:
    """Parse DEMO_ACCOUNTS ('user:pass:role,...') into {username: {password, role}}."""
    accounts: dict[str, dict] = {}
    for entry in settings.DEMO_ACCOUNTS.split(","):
        parts = entry.strip().split(":")
        if len(parts) == 3:
            username, password, role = parts
            accounts[username] = {"password": password, "role": role}
    return accounts


_ACCOUNTS = _parse_accounts()


def authenticate(username: str, password: str) -> Optional[dict]:
    """Return {sub, name, role} if credentials are valid, else None."""
    acct = _ACCOUNTS.get(username)
    if acct and acct["password"] == password:
        return {"sub": username, "name": username, "role": acct["role"]}
    return None


def issue_token(identity: dict) -> str:
    """Issue an HS256 JWT carrying sub/name/role."""
    now = datetime.now(timezone.utc)
    payload = {
        **identity,
        "iat": now,
        "exp": now + timedelta(hours=settings.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Decode + verify a JWT. Returns the payload or None if invalid/expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def identity_from_header(authorization: Optional[str]) -> Optional[dict]:
    """Extract and verify identity from an 'Authorization: Bearer <jwt>' header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return decode_token(authorization[7:].strip())
