# Project Digest — LLM Security Proxy

> **Purpose of this document.** A self-contained brief of the project, written to
> give an AI assistant (or a reader) full context for producing the academic
> end-of-studies report. Part I is narrative (problem, architecture, decisions,
> rationale, journey, results). Part II is a technical reference (modules, APIs,
> data models, configuration). Nothing here requires reading the source code.

---

# PART I — NARRATIVE

## 1. Problem & Motivation

Organisations increasingly route developer and application traffic through Large
Language Models (LLMs) — for code generation, assistance, and automation. This
creates two security exposures that traditional controls do not cover:

1. **Outbound risk (what users send to the LLM).** Prompts may leak secrets (API
   keys, credentials), personal data (PII), or carry prompt-injection attacks.
2. **Inbound risk (what the LLM returns).** Generated code may reference
   vulnerable packages, pin known-vulnerable versions, or contain outright
   malicious patterns (e.g. `exec(base64.b64decode(...))`, environment-variable
   exfiltration, shell execution).

Because LLM clients are heterogeneous (IDE assistants, CLIs, CI pipelines,
in-house apps), the control point cannot live inside any one client. It must sit
**between the clients and the LLM provider** — a security proxy.

**Goal:** build a provider-agnostic security proxy that inspects every request
and response, enforces policy (block / redact / allow), and records a complete,
queryable audit trail — deployable as a standalone product in front of any LLM
traffic.

## 2. What the Project Is (and Is Not)

- **The product** is the **proxy**: a middleware security layer. It is what gets
  deployed on a machine and integrated with arbitrary LLM clients.
- **The demonstration interface** (a web chat + admin dashboard) is **one example
  client** built to *showcase* the proxy's behaviour for evaluation. It is not the
  deliverable; deleting it leaves the proxy fully functional for every other
  client (curl, Claude Code, CI, etc.).

This distinction is deliberate and is reflected in the architecture: security,
logging, and the audit dashboard all belong to the proxy; the chat UI is a
separable consumer.

## 3. High-Level Architecture

```
   Clients (curl / IDE assistant / CI / demo chat UI …)
                        │  HTTP (OpenAI- or Anthropic-format)
                        ▼
        ┌───────────────────────────────────────────┐
        │            LLM SECURITY PROXY               │  ← the product (port 8080)
        │                                             │
        │  1. Authentication (API keys)               │
        │  2. Rate limiting (token bucket)            │
        │  3. Input Policy Engine                     │
        │       PII · secrets · prompt injection      │
        │  4. → LLM provider call (OpenRouter)        │
        │  5. Output Security Engine (multi-phase)    │
        │       malicious code · vulnerable packages  │
        │       · versions · dependencies · sandbox   │
        │  6. Audit logging (JSONL + Postgres)        │
        │  7. Built-in audit dashboard API + UI       │
        └───────────────────────────────────────────┘
                        │
                        ▼
              LLM Providers (via OpenRouter / LiteLLM)
```

The proxy exposes **two API surfaces** so existing clients work unchanged:
- `POST /v1/chat/completions` — OpenAI-compatible
- `POST /v1/messages` — Anthropic-compatible (translated to/from OpenAI format)

Both run the identical security pipeline.

## 4. The Security Pipeline

### 4.1 Input Policy Engine (before the LLM call)
Scans the outbound prompt for:
- **PII** (names, emails, phones, SSNs, credit cards) — via Microsoft **Presidio**
  + custom regex. Default action: **redact** (strip the sensitive span, let the
  request through). Configurable to **block**.
- **Secrets / credentials** (API keys, tokens) — default action: **block**.
- **Prompt injection** — pattern-based detection; **block**.

### 4.2 Output Security Engine (after the LLM call)
A configurable multi-phase pipeline over the generated text:
- **Phase 0.5 — Malicious code detection (always on).** Synchronous regex/pattern
  scan of code blocks for dangerous behaviours, classified CRITICAL / HIGH:
  - CRITICAL: `eval/exec` + base64 obfuscation; environment-variable access + network call.
  - HIGH: `os.system`/shell execution, `eval`, sensitive file access (`/etc/passwd`,
    `~/.ssh`), privilege escalation (`chmod 777`, `sudo`).
- **Phase 1 — Vulnerability scanning.** Queries **OSV** and **NVD/CVE** for known
  vulnerabilities in referenced packages; blocks above a severity threshold and
  **suggests a safe version** (see §5.3).
- **Phase 2 — Version validation.** Semantic-version range checks against a local
  advisory database.
- **Phase 3 — Dependency tree analysis.** Recursive/transitive dependency risk.
- **Phase 4 — Code sandbox.** Optional containerised behavioural analysis (Docker).
- **(Nexus)** — optional repository-firewall integration: only packages present in
  an approved Nexus repository pass (an allowlist model).

**Fail-closed philosophy:** when a check cannot validate something or a high-risk
signal is found, the response is blocked rather than passed through.

### 4.3 Block taxonomy
Distinct, machine-readable block codes flow back to the client, e.g.:
`BLOCKED_CREDENTIALS`, `BLOCKED_PII`, `BLOCKED_INJECTION`,
`MALICIOUS_CODE_PATTERN`, `BLOCKED_VULNERABLE_PACKAGE`,
`BLOCKED_VULNERABLE_VERSION`, `BLOCKED_DEPENDENCY_VULNERABILITY`,
`BLOCKED_SANDBOX`, `BLOCKED_GUARDRAILS`, plus operational codes
(`UNAUTHORIZED`, `RATE_LIMITED`, `LLM_TIMEOUT`, `LLM_ERROR`).

## 5. Key Design Decisions & Rationale

### 5.1 Real-time streaming security
**Problem:** scanning only after a full response means a user waits, and malicious
output is fully generated before any check. **Decision:** a **stateful streaming
scanner** that accumulates streamed text and fires a scan the moment a fenced code
block closes — blocking *mid-stream* by injecting an error event, before the
dangerous block reaches the client. **Why:** reduces the detection window from
"whole response" to "per code block" while preserving live token streaming UX.
Implemented for both the OpenAI and Anthropic streaming formats.

### 5.2 Fail-closed, defence-in-depth
Multiple independent phases, each able to block. A package can pass the malicious-
pattern scan yet be caught by the vulnerability scan, etc. **Why:** no single
detector is complete; layering raises the cost of a miss.

### 5.3 Safe-version suggestions (turning "no" into "do this")
**Problem:** blocking a vulnerable package is a dead end for the developer.
**Decision:** when a package is blocked, query OSV for the fix data of **all** its
known vulnerabilities and suggest the **lowest version that clears every known
vulnerability** (the maximum fix boundary). **Why:** a suggestion that only patches
one CVE while leaving others open is worse than useless; the chosen version is both
*safe* and *recent*. Example output: *"Package 'pillow' has a CRITICAL vulnerability
(CVSS 9.8, CVE-2016-4009) — use >=3.1.1 instead."*

### 5.4 Auditing is a proxy-level concern (client-agnostic)
**Decision:** every request through either endpoint is logged by the proxy itself,
independent of the client. Identity is always tracked at the **API-key** level
(`app_id`); an optional `X-User-Identity` header lets a client enrich events with a
named end-user. **Why:** observability must not depend on which client is used; the
proxy is the single chokepoint where all traffic is visible.

### 5.5 The dashboard ships with the proxy
**Decision:** the audit **query API** (`/v1/audit/stats`, `/v1/audit/logs`) and the
admin **dashboard UI** (`/admin`) are served by the proxy itself, not the demo app.
**Why:** "deploy the proxy → get a security dashboard for free" must hold for any
deployment regardless of clients. The demo's dashboard became a thin *consumer* of
the proxy's API — making the product/demo boundary self-evident.

### 5.6 Authentication: pragmatic now, enterprise-ready
- The proxy authenticates clients with **API keys** (a hashed registry; constant-
  time lookup; revocation via an `enabled` flag).
- For the **internal admin dashboard**, the design integrates **Keycloak (OIDC/SSO)**:
  the proxy verifies Keycloak-signed tokens (RS256 via the realm's JWKS) and checks
  an admin role. This is **built but dormant** (`OIDC_ENABLED=false`) pending the
  company realm details; until then the dashboard uses API-key auth. **Why:** an
  internal security-team panel should authenticate real people via corporate SSO,
  but the system must still run without that dependency.

### 5.7 Conversation continuity under blocking (demo correctness)
In the demo chat, a blocked turn is shown as a UI-only notice and is **never**
inserted into the message history sent to the LLM. **Why:** otherwise the next turn
would ship a fake "blocked" assistant message back to the model, polluting the
conversation. The fix separates the *displayed transcript* from the *LLM-sent
history*.

## 6. Development Journey (chronological highlights)

From version history, the project evolved roughly as:
1. Working proxy v1 with OpenRouter integration and provider selection.
2. PII redaction via Presidio; input documentation.
3. Package/dependency security hardening (vulnerability + version + dependency).
4. Malicious-code parser (output pattern detection).
5. Real-time streaming security (chunk-based interception).
6. Safer package suggestions (safe-version recommendations).
7. (This internship's later work) Persistence with PostgreSQL; a demonstration
   chat + admin dashboard; making the audit dashboard a built-in proxy capability;
   Keycloak/OIDC admin authentication (dormant).

## 7. Results & Validation

- **Automated tests:** ~270 collected; 260 passing. The ~10 failures are
  environmental (Docker sandbox host mounts, Presidio language config, OpenRouter
  credit limits) rather than logic regressions.
- **Verified behaviours (end-to-end):** secret/PII/injection blocking; malicious-
  code interception mid-stream; vulnerable-package blocking with safe-version
  suggestion; client-agnostic audit tracking (a raw `curl` request appears in the
  proxy's own audit API with no UI involved); the proxy serving its admin console
  at `/admin`; role-gated audit access; graceful degradation when the database or
  Keycloak is unreachable.

## 8. Limitations & Future Work

- Keycloak SSO is implemented but not yet validated against a live realm (company
  details pending).
- Rate limiting and some caches are in-memory (single-instance); a multi-instance
  deployment would use Redis.
- The Docker sandbox phase depends on host Docker configuration.
- Demo auth (chat app) uses hardcoded accounts — intentional, as it is a demo gate.

---

# PART II — TECHNICAL REFERENCE

## A. Repository Layout (key paths)

```
config/
  settings.py            Central configuration (env-driven)
  api_keys.yaml          Proxy API-key registry (hashed at load)
src/
  proxy/                 ── THE PRODUCT ──
    main.py              FastAPI app; both endpoints; serves /admin
    auth.py              API-key validation (SHA-256, constant-time)
    rate_limiter.py      Token-bucket rate limiting (per app_id)
    models.py            Request/response + error schemas (OpenAI & Anthropic)
    streaming.py         Streaming generators (OpenAI + Anthropic SSE)
    audit_api.py         Built-in dashboard API (/v1/audit/stats, /logs)
    oidc.py              Keycloak/OIDC token verification (RS256/JWKS)
    logging.py           Structured JSON logging
  input_policy/          Input scanning
    engine.py            check_and_sanitize_openai / _anthropic
    injection.py, patterns.py, pii_patterns.py
  output_security/       Output scanning (multi-phase)
    engine.py            SecurityOrchestrator; phase coordination
    malicious_code_detector.py, code_parser.py
    vulnerability_scanner.py (OSV/CVE + get_safe_version)
    version_parser.py, version_validator.py, security_advisory.py
    dependency_resolver.py, dependency_tree.py
    sandbox.py, guardrails.py, risk_scorer.py, detection_rules.py
    nexus.py             Repository-firewall (allowlist) integration
    streaming_scanner.py Stateful per-code-block streaming scanner
  audit/
    logger.py            emit() → JSONL + best-effort Postgres sink
    README.md            Documents audit as a proxy-level subsystem
  db/                    SQLAlchemy async (Postgres)
    models.py            audit_events, conversations, messages
    session.py, init.py
  webui_api/             ── DEMO GATEWAY (port 8000) ──
    main.py              FastAPI; serves demo React build; CORS
    routes/chat.py       Forwards chat to proxy; structured block passthrough; streaming
    routes/auth.py       Demo login (HS256 JWT) + /me
    routes/audit.py      Forwards to proxy /v1/audit/* (consumer)
    routes/history.py    Conversation/message CRUD
    services/auth_service.py  Demo JWT + hardcoded accounts
    deps.py              require_user / require_admin guards
  webui-react/           ── DEMO + ADMIN UI ──
    src/components/Chat.js, BlockCard.js   Demo chat client
    src/pages/SecurityOverview.js, AuditLog.js  Admin console
    src/AuthContext.js   Dual mode: demo JWT / Keycloak SSO
    src/keycloak.js      keycloak-js init (admin/SSO mode)
    src/services/api.js  Axios client + auth interceptor
docs/                    Test prompts, setup, this digest
scripts/
  start_proxy.sh         Starts proxy with streaming + scanning enabled
  seed_demo_data.py      Seeds Postgres with varied demo audit data
```

## B. Endpoints

**Proxy (port 8080) — the product**
| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/v1/chat/completions` | OpenAI-format chat (+ streaming) | API key |
| POST | `/v1/messages` | Anthropic-format chat (+ streaming) | pass-through key |
| GET | `/v1/audit/stats` | Aggregated audit metrics | API key, or Keycloak admin if OIDC on |
| GET | `/v1/audit/logs` | Paginated/filterable audit entries | same |
| GET | `/admin`, `/admin/*` | Admin dashboard SPA | (UI; data calls gated above) |
| GET | `/health`, `/ready` | Probes | none |

**Demo gateway (port 8000)**
`POST /v1/chat/completions` (forwards to proxy), `/api/auth/login`, `/api/auth/me`,
`/api/audit/stats|logs` (forward to proxy), `/api/history*`, `/api/providers*`,
`/api/dashboard/*`.

## C. Data Model (Postgres, `src/db/models.py`)

- **audit_events** — timestamp, request_id, app_id, action (ALLOWED/BLOCKED/ERROR),
  block_code, model, prompt_hash, latency_ms, findings (JSONB), redaction_details
  (JSONB), user_sub, user_name, and display fields sanitized_prompt, llm_output,
  block_reason, safe_version.
- **conversations** — id, user_sub, title, timestamps.
- **messages** — id, conversation_id, role, content, blocked, block_code, timestamp.

## D. Audit Event (JSONL) — fields
`timestamp, request_id, app_id, action, block_code, model, prompt_hash,
latency_ms, findings[], redaction_details{}`. **Raw prompts and raw API keys are
never stored** (only a SHA-256 prompt hash and finding *types*).

## E. Key Configuration Flags (`config/settings.py`)
- LLM: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `LLM_TIMEOUT_S`.
- Streaming: `STREAMING_ENABLED`.
- Input: `PII_ACTION` (redact|block), `CREDENTIAL_ACTION`.
- Output phases: `MALICIOUS_CODE_ENABLED`, `VULN_SCAN_ENABLED`,
  `VULN_BLOCK_MIN_SEVERITY`, `VERSION_VALIDATION_ENABLED`,
  `DEPENDENCY_SCAN_ENABLED`, `SANDBOX_ENABLED`, `GUARDRAILS_ENABLED`,
  Nexus (`NEXUS_BASE_URL`, `NEXUS_FAIL_OPEN`).
- Persistence: `DATABASE_URL` (Postgres).
- Auth: `JWT_SECRET` (demo), `DEMO_ACCOUNTS`; `OIDC_ENABLED`,
  `KEYCLOAK_SERVER_URL/REALM/CLIENT_ID/AUDIENCE/ADMIN_ROLE`.

## F. Technology Stack
- **Backend:** Python, FastAPI, Uvicorn, httpx, Pydantic.
- **Security libs:** Microsoft Presidio (PII), pyjwt + cryptography (OIDC RS256).
- **Data:** PostgreSQL via SQLAlchemy (async, asyncpg); JSONL audit log; SQLite
  advisory DB.
- **Threat intel:** OSV API, NVD/CVE API; optional Sonatype Nexus.
- **Frontend:** React 19, React Router 7, Axios, Chart.js, keycloak-js.
- **Infra:** Docker / docker-compose (proxy + Postgres); pytest test suite.

## G. Provider Integration
Primary provider is **OpenRouter** (OpenAI-compatible). Model names are translated
from client formats (e.g. Claude Code names) to OpenRouter names. **LiteLLM** is
supported as a legacy pass-through. The Anthropic endpoint translates Anthropic ↔
OpenAI request/response (and SSE) formats.

## H. How to Run (reference)
```
docker compose -f docker/docker-compose.yml up -d postgres   # database
bash scripts/start_proxy.sh                                   # proxy :8080 (streaming on)
uvicorn src.webui_api.main:app --port 8000                    # demo gateway
cd src/webui-react && npm start                                # demo UI :3000
```
Proxy-served admin console: `http://localhost:8080/admin`.

---

*End of digest. For specific code excerpts, see the paths in §A.*
