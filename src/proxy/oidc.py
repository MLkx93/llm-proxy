"""
Keycloak / OIDC token verification for the proxy's admin dashboard.

The security team logs into the company Keycloak; the proxy verifies the
resulting access token (RS256, signed by Keycloak) using the realm's published
public keys (JWKS). No shared secret — the proxy only needs Keycloak's public
keys, fetched once and cached.

Used by src/proxy/audit_api.py to gate /v1/audit/* when OIDC_ENABLED=true.
Degrades cleanly: if OIDC is disabled or misconfigured, verify_oidc_token
returns None and the caller falls back to API-key auth.
"""
import time
from typing import Optional

import httpx
import jwt
from jwt import PyJWKClient

from config.settings import settings
from src.proxy.logging import get_logger

logger = get_logger("oidc")

# Cache the JWKS client (it fetches + caches the realm public keys internally).
_jwk_client: Optional[PyJWKClient] = None
_jwk_client_built_at: float = 0.0
_JWK_TTL = 3600.0  # rebuild the client hourly so key rotations are picked up


def _realm_base() -> str:
    """Base URL of the realm, e.g. https://sso.company.com/realms/security."""
    return f"{settings.KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}"


def _jwks_uri() -> str:
    return f"{_realm_base()}/protocol/openid-connect/certs"


def _issuer() -> str:
    return _realm_base()


def _get_jwk_client() -> Optional[PyJWKClient]:
    global _jwk_client, _jwk_client_built_at
    if not (settings.KEYCLOAK_SERVER_URL and settings.KEYCLOAK_REALM):
        return None
    now = time.monotonic()
    if _jwk_client is None or (now - _jwk_client_built_at) > _JWK_TTL:
        try:
            _jwk_client = PyJWKClient(_jwks_uri())
            _jwk_client_built_at = now
        except Exception as exc:
            logger.error("jwks_client_build_failed", extra={"error": str(exc)})
            return None
    return _jwk_client


def verify_oidc_token(token: str) -> Optional[dict]:
    """
    Verify a Keycloak access token. Returns the decoded claims on success,
    None on any failure (invalid signature, expired, wrong issuer/audience).
    """
    if not settings.OIDC_ENABLED:
        return None
    client = _get_jwk_client()
    if client is None:
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        options = {"verify_aud": bool(settings.KEYCLOAK_AUDIENCE)}
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_AUDIENCE or None,
            issuer=_issuer(),
            options=options,
        )
        return claims
    except Exception as exc:
        logger.warning("oidc_verify_failed", extra={"error": str(exc)})
        return None


def has_admin_role(claims: dict) -> bool:
    """True if the token carries the configured admin role (realm or client roles)."""
    if not claims:
        return False
    role = settings.KEYCLOAK_ADMIN_ROLE
    # Realm roles
    realm_roles = (claims.get("realm_access") or {}).get("roles", [])
    if role in realm_roles:
        return True
    # Client roles (resource_access.<client>.roles)
    resource = claims.get("resource_access") or {}
    for client_id, data in resource.items():
        if role in (data or {}).get("roles", []):
            return True
    return False


def identity_from_claims(claims: dict) -> dict:
    """Normalise Keycloak claims into the audit identity shape."""
    return {
        "sub": claims.get("sub"),
        "name": claims.get("preferred_username") or claims.get("name") or claims.get("email"),
    }
