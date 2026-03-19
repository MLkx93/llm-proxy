# LLM Proxy — Implementation Plan

## Phase 0: Foundation (Prerequisites) ✅ COMPLETE

**All decisions locked 2026-03-18:**

| Decision | Choice | Notes |
|----------|--------|-------|
| Language / Framework | Python + FastAPI | LiteLLM is Python-native; async |
| PII Detection | Presidio + custom regex | Presidio for standard PII, custom regex for internal identifiers/secrets |
| Streaming (v1) | Block — force buffered only | Clients must not use `stream=true`; simplest safe default |
| Nexus unreachable | Fail-closed — block response | Security over availability |
| Repo Firewall | Sonatype Nexus Firewall | Enterprise-grade, integrates with existing Nexus |
| Audit Logs (v1) | Local structured JSON file | Forward-compatible with Filebeat/Fluentd/Splunk later |

**Error response schema (all blocked responses):**
```json
{
  "error": {
    "code": "BLOCKED_PII | BLOCKED_INJECTION | BLOCKED_UNSAFE_CODE | BLOCKED_UNVALIDATED_DEP | NEXUS_UNAVAILABLE | UNAUTHORIZED | RATE_LIMITED",
    "message": "Human-readable reason",
    "request_id": "<uuid>"
  }
}
```

---

## Phase 1: Core Proxy (Skeleton) ✅ COMPLETE

- [x] Scaffold project structure (src/, tests/, config/, docker/)
- [x] Scaffold FastAPI app with `/v1/chat/completions` endpoint (OpenAI-compatible)
- [x] Integrate LiteLLM as the routing layer
- [x] Implement basic request/response pass-through with structured JSON logging
- [x] Write integration tests — 4/4 passing (health, pass-through, stream rejection, LLM error)

## Phase 2: Input Policy Engine ✅ COMPLETE

- [x] Integrate Microsoft Presidio for PII detection (PERSON, EMAIL, CREDIT_CARD, SSN, IBAN, IP, URL, etc.)
- [x] Custom regex patterns: 11 secret types (OpenAI, Anthropic, GitHub, AWS, generic API keys, bearer tokens, private keys, passwords, connection strings)
- [x] Prompt injection heuristics: 8 patterns (ignore instructions, DAN, role hijack, system prompt leak, context escape tags, etc.)
- [x] Engine wired into `/v1/chat/completions` — blocks before LiteLLM call
- [x] Standardized error codes: BLOCKED_CREDENTIALS / BLOCKED_INJECTION / BLOCKED_PII
- [x] 20 unit tests passing + 4 integration tests — 24/24 total
- Note: LOCATION removed from Presidio entities (too many false positives on country/city names)

## Phase 3: Output Security Engine ✅ COMPLETE

- [x] Markdown code block detection (fenced blocks with language tag)
- [x] Dependency extraction: Python, JS/TS, Java, Go, Ruby, Shell/Bash — stdlib filtered out
- [x] Nexus Firewall client (async httpx, Nexus REST API v1 search)
- [x] Circuit breaker: opens after 3 failures, 30s recovery timeout, half-open probe
- [x] Fail-closed: NEXUS_UNAVAILABLE when Nexus is down or unconfigured
- [x] Fail-fast: stops at first blocked package
- [x] Wired into response pipeline after LiteLLM call, before returning to client
- [x] 22 unit tests passing — 46/46 total across all phases

## Phase 4: Auth & Access Control ✅ COMPLETE

- [x] API key auth via `Authorization: Bearer <key>` header
- [x] Keys stored as SHA-256 hashes in memory — plaintext never retained
- [x] YAML key registry (config/api_keys.yaml): app_id, team, enabled flag
- [x] 401 UNAUTHORIZED on missing, malformed, unknown, or disabled key
- [x] `/health` intentionally public (no auth required)
- [x] `app_id` logged on every request event (received, blocked, completed)
- [x] 14 unit/integration tests — 60/60 total

## Phase 5: Audit Logging ✅ COMPLETE

- [x] Append-only JSONL at `logs/audit.jsonl` (path configurable via env var)
- [x] Schema: timestamp, request_id, app_id, action, block_code, model, prompt_hash, latency_ms
- [x] Raw prompt never logged — SHA-256 hash only (privacy by design)
- [x] Covers all exit points: ALLOWED, BLOCKED (every reason), ERROR
- [x] Thread-safe write via lock (safe for multi-worker deployments)
- [x] Audit failure never crashes the proxy (OSError caught, logged)
- [x] Parent dirs auto-created on first write
- [x] 12 unit/integration tests — 72/72 total

## Phase 6: Observability & Resilience ✅ COMPLETE

- [x] `/health` — liveness probe, no auth, always 200 if process is alive
- [x] `/ready` — readiness probe, 503 if NEXUS_BASE_URL unconfigured, 200 when ready
- [x] Token bucket rate limiter (60 req burst, 1 req/s sustained, per app_id, thread-safe)
- [x] 429 RATE_LIMITED response with audit event
- [x] LLM call timeout: 60s → 504 LLM_TIMEOUT
- [x] Output check timeout: 10s → 400 NEXUS_UNAVAILABLE (fail-closed)
- [x] Circuit breaker already implemented in Phase 3 (nexus.py)
- [x] 12 tests — 84/84 total

## Phase 7: Hardening & Deployment ✅ COMPLETE

- [x] Multi-stage Dockerfile: builder + slim runtime, non-root user (uid 1001), read-only filesystem
- [x] docker-compose.yml: env_file, volume mount for logs, read_only, no-new-privileges, healthcheck
- [x] .env.example: documents all required env vars, never committed
- [x] .gitignore: excludes .env, keys, venv, logs, caches
- [x] .dockerignore: excludes secrets, dev artefacts, test files from image
- [x] 12 E2E tests covering all 12 block/allow scenarios from Context.md
- [x] Final run: 96/96 tests passing

## Phase 8: Anthropic Gateway & Live Integration ✅ COMPLETE

- [x] Anthropic-format endpoint (`POST /v1/messages`) with format translation (Anthropic → OpenAI → LiteLLM → OpenAI → Anthropic)
- [x] Pass-through auth: user sends their own LiteLLM key, proxy forwards it (no separate proxy keys needed)
- [x] Accept both `x-api-key` and `Authorization: Bearer` headers (Anthropic SDK uses Bearer)
- [x] SSE stream buffering for streamed responses
- [x] Input policy: scan only last user message, strip tool-generated XML tags (Claude Code compatibility)
- [x] Whitespace trimming on all env vars in settings.py
- [x] Live-tested with Claude Code through LiteLLM server at litellm.internal.example:3115/api
- [x] SETUP.md and GUIDE.md fully rewritten for transparent gateway architecture
- [x] 138/138 tests passing (42 new Anthropic gateway tests)

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-18 | Plan created | First session — no code yet |
| 2026-03-18 | Phase 0 complete | All architectural decisions resolved before coding |
| 2026-03-19 | Pass-through auth for /v1/messages | Users already have LiteLLM keys — no need for separate proxy keys |
| 2026-03-19 | Anthropic→OpenAI format translation | LiteLLM server only exposes OpenAI-compatible endpoints |
| 2026-03-19 | Scan only last user message | Claude Code sends full conversation history — rescanning old messages causes cascading blocks |
| 2026-03-19 | Strip XML tags from scanned text | Claude Code injects system-reminder tags into user messages with URLs/names that trigger PII false positives |
