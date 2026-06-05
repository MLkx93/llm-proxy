# Architecture — LLM Security Proxy

## Overview

The **LLM Security Proxy** is a middleware security layer that sits between clients and LLM providers. It inspects every request and response, enforces security policy, and maintains a complete audit trail.

### The Product vs. The Demo

- **The Product:** The proxy itself (port 8080) — can be deployed standalone with any client
- **The Demo:** The chat UI (port 8000) — one example client showing the proxy in action
- **The Admin Console:** Security dashboard (port 8080/admin) — shipped with the proxy, owned by the proxy

This distinction is **architectural:** the proxy is useful without the demo; the demo is useless without the proxy.

---

## Port Layout

| Port | Service | Purpose | Auth |
|------|---------|---------|------|
| **8080** | LLM Security Proxy | Security scanning + audit logging | API Key |
| **8080/admin** | Admin Console | Security team dashboard | API Key (or Keycloak when SSO enabled) |
| **8000** | WebUI API Gateway | Demo chat + forwarding | JWT (demo mode) |
| **3000** | React Dev Server | (development only) | JWT (demo mode) |
| **5433** | PostgreSQL | Audit event persistence | DB credentials |

---

## Request Flow

### Demo Chat Path (End User Perspective)
```
User Browser (localhost:3000 or 8000)
    ↓
React App (Chat UI)
    ↓
WebUI API (port 8000) — validates JWT, forwards request
    ↓
LLM Proxy (port 8080) — security scanning
    ↓
OpenRouter → Claude, GPT, etc.
    ↓
Response flows back, logged to Postgres
```

### Admin Console Path
```
Security Team Browser (localhost:8080/admin)
    ↓
React App (Security Overview / Audit Log)
    ↓
LLM Proxy API (same port, /v1/audit/*)
    ↓
Postgres → aggregated metrics & log entries
```

### CLI / Automation Path
```
curl / CI Pipeline / IDE Assistant
    ↓
LLM Proxy (port 8080)
    ↓
OpenRouter
    ↓
Response logged to Postgres
```

---

## Security Pipeline (Per Request)

### Phase 1: Input Scanning
Before the LLM call:
- **PII Detection** (Presidio) — redact or block sensitive data
- **Credential Detection** — block API keys, tokens
- **Prompt Injection** — detect and block malicious input patterns

### Phase 2: LLM Call
Forward to OpenRouter, LiteLLM, or other providers.

### Phase 3: Output Scanning (Multi-Phase)
After the response:
- **Malicious Code Detection** — regex/pattern scan for `eval`, `exec`, shell commands, privilege escalation
- **Vulnerability Scanning** — OSV/CVE database queries, suggests safe versions
- **Version Validation** — semantic-version range checks
- **Dependency Tree Analysis** — transitive dependency risk
- **Code Sandbox** (optional) — containerized behavioral analysis
- **Repository Firewall** (optional) — Nexus allowlist

### Phase 4: Audit Logging
- JSONL log (always, for offline analysis)
- Postgres (best-effort async insert)
- Fields: timestamp, request_id, app_id, action (ALLOWED/BLOCKED/ERROR), block_code, findings, identity

---

## Key Design Decisions

### 1. Proxy-Level Auditing
Every request through `/v1/chat/completions` or `/v1/messages` is logged, **regardless of client**. This makes the proxy the single chokepoint for observability.

### 2. Real-Time Streaming Security
Mid-stream code block scanning — blocks dangerous output the moment it closes, not after the full response.

### 3. Safe-Version Suggestions
When a package is blocked for CVE, suggest the **minimum version that fixes ALL known vulnerabilities** for that package (not just one).

### 4. Fail-Closed Philosophy
If anything is uncertain or high-risk, block rather than pass through.

### 5. Dashboard Ships with Proxy
The audit query API and admin console are **served by the proxy itself**, not the demo. This means "deploy the proxy → get observability" is always true.

### 6. Graceful Degradation
- If the database is down, the proxy still works (logs to JSONL only)
- If an optional security phase fails, the next phase runs (not chain-blocked)
- If authentication is misconfigured, audit endpoints fail safely with 401/403

### 7. Dual UI, Single Build
The same React build serves both the admin console (port 8080, full security pages) and demo chat (port 8000, chat + dashboard). Port-based conditional rendering keeps them separate without needing two builds.

---

## Audit Trail

### Stored In
- **JSONL** → `/logs/*.jsonl` (append-only, never deleted)
- **Postgres** → `audit_events` table (queryable, analysable, TTL-able)

### Key Fields
| Field | Purpose | Example |
|-------|---------|---------|
| `timestamp` | When the request occurred | `2026-06-05T09:10:51Z` |
| `request_id` | Unique identifier | UUID v4 |
| `app_id` | Which client/key made it | `local-dev` |
| `action` | Outcome | `ALLOWED` / `BLOCKED` / `ERROR` |
| `block_code` | Why blocked (if blocked) | `BLOCKED_CREDENTIALS`, `MALICIOUS_CODE_PATTERN`, etc. |
| `model` | Which LLM was targeted | `openai/gpt-4o-mini` |
| `findings` | What was detected | `["API_KEY", "PROMPT_INJECTION"]` |
| `user_sub` / `user_name` | Who is the human user | (optional, from `X-User-Identity` header) |
| `latency_ms` | How long the request took | `2350` |

**Never stored:**
- Raw prompts (only SHA-256 hash)
- Raw API keys (only the hashed app_id)

---

## Authentication

### For Chat/Proxy Endpoints
**API Keys** (proxy's own registry in `config/api_keys.yaml`)
- SHA-256 hashed at load
- Constant-time comparison (no timing attacks)
- Revocable per-key via `enabled` flag

### For Admin Dashboard
**API Keys** (when OIDC disabled)
- Same as above

**Keycloak/OIDC** (when enabled, for SSO)
- RS256 token verification via JWKS
- Role-based access control (`security-admin` role)
- Gracefully falls back to API-key if Keycloak is down

### For Demo Chat
**HS256 JWT** (demo-only, hardcoded accounts)
- Not used by the proxy itself
- Separates demo auth from the real product

---

## Configuration

### Key Toggles
```bash
# Streaming + security phases
export STREAMING_ENABLED=true
export MALICIOUS_CODE_ENABLED=true
export VULN_SCAN_ENABLED=true
export VERSION_VALIDATION_ENABLED=true
export DEPENDENCY_SCAN_ENABLED=true
export SANDBOX_ENABLED=false  # requires Docker
export GUARDRAILS_ENABLED=true

# Keycloak/OIDC (optional, for SSO)
export OIDC_ENABLED=false
export KEYCLOAK_SERVER_URL=https://sso.company.com
export KEYCLOAK_REALM=security
export KEYCLOAK_CLIENT_ID=shield-admin
export KEYCLOAK_AUDIENCE=shield-admin
export KEYCLOAK_ADMIN_ROLE=security-admin

# Database
export DATABASE_URL=postgresql://shield:shield@localhost:5433/shield

# LLM Provider
export OPENROUTER_API_KEY=sk-xxx
export LLM_TIMEOUT_S=60

# PII handling
export PII_ACTION=redact  # or 'block'
export CREDENTIAL_ACTION=block
```

---

## Deployment

### Development
```bash
bash scripts/launch_all.sh
```

### Production
1. Set up persistent Postgres (not Docker container)
2. Build React admin bundle with `REACT_APP_AUTH_MODE=keycloak` (once Keycloak realm is available)
3. Run proxy with `STREAMING_ENABLED=true`, all security phases on
4. Configure Keycloak realm + client (public SPA, standard flow, PKCE, admin role)
5. Use reverse proxy (nginx) for HTTPS termination

---

## Key Files

- `src/proxy/main.py` — FastAPI app, both endpoints, audit logging
- `src/proxy/audit_api.py` — `/v1/audit/stats` + `/v1/audit/logs`
- `src/input_policy/engine.py` — prompt scanning (PII, secrets, injection)
- `src/output_security/engine.py` — response scanning orchestrator
- `src/db/models.py` — SQLAlchemy models (AuditEvent, Conversation, Message)
- `src/webui-react/src/App.js` — port-based conditional rendering (admin vs. demo)
- `scripts/launch_all.sh` — one-command startup

---

## Metrics & Observability

### Built-In Dashboard Metrics
- Total requests (24h, 7d, 1h)
- Allowed vs. blocked vs. errors (with rates)
- Block reasons distribution (pie chart)
- Top findings (bar chart)
- Secrets detected per user (waterfall)
- PII redaction count
- Average latency
- Request volume over time (line chart)

### Via `/v1/audit/logs`
- Paginated, filterable audit entries
- Search by request ID, model, block code
- 25–200 entries per page

---

## Example Workflows

### Scenario 1: Dev Asking Claude Code for Help
```
Claude Code IDE → Proxy (API key) → OpenRouter → Claude
↓
Proxy scans for secrets (finds none) → ALLOWED
↓
Response scanned, generates import statement with known vulnerable package
↓
Proxy blocks, suggests safe version → dev uses it
↓
Audit event logged
```

### Scenario 2: Security Team Investigating Incident
```
Open http://localhost:8080/admin
↓
Security Overview shows spike in BLOCKED_CREDENTIALS last hour
↓
Click to Audit Log, filter by BLOCKED_CREDENTIALS
↓
Find 15 requests from app_id="some-ci-pipeline" with API keys in prompts
↓
Click into one, see full prompt (redacted), alert the team
```

### Scenario 3: Automation / CI Pipeline
```
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer ci-key-5678" \
  -d '{"model":"openai/gpt-4o-mini","messages":[...]}'
↓
Proxy returns either:
  - 200 + response (if allowed)
  - 400 + error code (if blocked, with reason)
↓
CI pipeline reads block_code, decides to fail build or retry
```

---

## Status

### Implemented ✅
- Streaming security (mid-stream blocking)
- Safe-version suggestions
- Audit persistence (JSONL + Postgres)
- Admin dashboard (Security Overview + Audit Log)
- Port-based UI separation (admin vs. demo)
- Real-time auto-refresh (5-second polling)
- Keycloak/OIDC support (dormant, ready when realm available)
- Multiple LLM provider support (OpenRouter primary, LiteLLM legacy)

### TODO
- [ ] Keycloak realm configuration (awaiting company details)
- [ ] Multi-instance rate limiting (Redis, currently in-memory)
- [ ] Custom webhook alerting on high-risk blocks
- [ ] Machine learning-based anomaly detection

---

## For Your Thesis

This architecture demonstrates:
1. **Security-first design** — policy enforcement at the gateway, not in clients
2. **Observability by design** — every request logged, queryable
3. **Provider agnosticism** — works with any LLM via OpenRouter
4. **Graceful degradation** — core security continues even if optional features fail
5. **Real-time response** — mid-stream blocking, not batch post-processing

The key insight: **a single proxy can protect heterogeneous clients** (IDEs, CLIs, CI, web UIs) with uniform policy, eliminating the need to secure every client separately.
