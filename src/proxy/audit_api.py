"""
Audit query API — a BUILT-IN capability of the proxy.

This ships WITH the proxy, not the demo UI. Any deployment of the proxy gets a
security dashboard API for free: every request through /v1/chat/completions and
/v1/messages is tracked (by src/audit/logger.py) into Postgres, and these
endpoints expose that data for visualisation by ANY client.

  GET /v1/audit/stats : aggregated metrics (totals, by action/block_code/finding,
                        secrets-by-user, latency)
  GET /v1/audit/logs  : paginated, filterable audit entries

Auth: the proxy's own API-key registry (config/api_keys.yaml) — same keys that
authorise chat traffic. No dependency on the demo's login gate.
"""
from fastapi import APIRouter, Query, HTTPException, Header
from sqlalchemy import select, func
from typing import Optional

from .auth import validate
from .oidc import verify_oidc_token, has_admin_role
from config.settings import settings
from src.db.session import get_session_factory
from src.db.models import AuditEvent

router = APIRouter(prefix="/v1/audit", tags=["audit"])


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _require_admin(authorization: Optional[str]):
    """
    Authorise access to audit data.

    - OIDC_ENABLED=true  → require a valid Keycloak token bearing the admin role
                           (SSO-only; API keys are NOT accepted for audit data).
    - OIDC_ENABLED=false → fall back to the proxy API-key registry, so the
                           dashboard/demo keep working until Keycloak is wired.
    """
    if settings.OIDC_ENABLED:
        token = _bearer(authorization)
        claims = verify_oidc_token(token) if token else None
        if claims is None:
            raise HTTPException(status_code=401, detail="Valid Keycloak token required.")
        if not has_admin_role(claims):
            raise HTTPException(status_code=403, detail="Admin role required.")
        return
    # OIDC off → API-key gate
    if validate(authorization) is None:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")


def _serialize(e: AuditEvent) -> dict:
    return {
        "id": e.id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "request_id": e.request_id,
        "app_id": e.app_id,
        "action": e.action,
        "block_code": e.block_code,
        "model": e.model,
        "latency_ms": e.latency_ms,
        "findings": e.findings or [],
        "redaction_details": e.redaction_details,
        "user_sub": e.user_sub,
        "user_name": e.user_name,
        "sanitized_prompt": e.sanitized_prompt,
        "llm_output": e.llm_output,
        "block_reason": e.block_reason,
        "safe_version": e.safe_version,
    }


@router.get("/stats")
async def get_stats(time_range: str = Query("24h"), authorization: Optional[str] = Header(default=None)):
    """Aggregated metrics over the time range. Authorised by proxy API key."""
    _require_admin(authorization)
    from datetime import datetime, timezone, timedelta
    hours = {"1h": 1, "24h": 24, "7d": 168}.get(time_range, 24)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    factory = get_session_factory()
    try:
        async with factory() as session:
            rows = (await session.execute(
                select(AuditEvent).where(AuditEvent.timestamp >= cutoff)
            )).scalars().all()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    total = len(rows)
    blocked = sum(1 for r in rows if r.action == "BLOCKED")
    allowed = sum(1 for r in rows if r.action == "ALLOWED")
    errors = sum(1 for r in rows if r.action == "ERROR")

    block_reasons: dict[str, int] = {}
    finding_counts: dict[str, int] = {}
    secrets_by_user: dict[str, int] = {}
    latencies: list[int] = []

    for r in rows:
        if r.block_code:
            block_reasons[r.block_code] = block_reasons.get(r.block_code, 0) + 1
        for f in (r.findings or []):
            finding_counts[f] = finding_counts.get(f, 0) + 1
            if "KEY" in f or "TOKEN" in f or "SECRET" in f:
                who = r.user_name or r.app_id or "unknown"
                secrets_by_user[who] = secrets_by_user.get(who, 0) + 1
        if r.latency_ms is not None and r.latency_ms < 10000:
            latencies.append(r.latency_ms)

    secrets_detected = sum(
        1 for r in rows
        if r.block_code == "BLOCKED_CREDENTIALS"
        or any("KEY" in f or "TOKEN" in f for f in (r.findings or []))
    )
    pii_redacted = sum(
        (r.redaction_details or {}).get("redaction_count", 0)
        for r in rows if (r.redaction_details or {}).get("redacted")
    )
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0

    return {
        "total": total, "blocked": blocked, "allowed": allowed, "errors": errors,
        "blockReasons": block_reasons, "findingCounts": finding_counts,
        "secretsByUser": secrets_by_user, "secretsDetected": secrets_detected,
        "piiRedacted": pii_redacted, "avgLatency": avg_latency,
    }


@router.get("/logs")
async def get_logs(
    time_range: str = Query("24h"),
    status: str = Query("ALL"),
    block_code: str = Query("ALL"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    authorization: Optional[str] = Header(default=None),
):
    """Paginated, filterable audit entries, newest first. Authorised by proxy API key."""
    _require_admin(authorization)
    from datetime import datetime, timezone, timedelta
    hours = {"1h": 1, "24h": 24, "7d": 168}.get(time_range, 24)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    factory = get_session_factory()
    try:
        async with factory() as session:
            q = select(AuditEvent).where(AuditEvent.timestamp >= cutoff)
            if status != "ALL":
                q = q.where(AuditEvent.action == status)
            if block_code != "ALL":
                q = q.where(AuditEvent.block_code == block_code)
            if search:
                like = f"%{search.lower()}%"
                q = q.where(
                    func.lower(AuditEvent.request_id).like(like)
                    | func.lower(func.coalesce(AuditEvent.model, "")).like(like)
                    | func.lower(func.coalesce(AuditEvent.block_code, "")).like(like)
                )

            total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
            q = q.order_by(AuditEvent.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
            rows = (await session.execute(q)).scalars().all()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    return {
        "total": total, "page": page, "page_size": page_size,
        "entries": [_serialize(r) for r in rows],
    }
