# LLM Security Proxy — Project Presentation

**Author:** Malak
**Date:** March 2026
**Status:** Production-Ready (138/138 tests passing)

---

## Executive Summary

A transparent security gateway that sits between developers using Claude Code and the upstream LLM provider. It intercepts all requests, enforces security policies on both input and output, and only forwards safe traffic.

**Key Achievement:** Enables safe AI-assisted development by preventing credential leaks, blocking prompt injection attacks, and ensuring only approved dependencies are suggested.

---

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────────────────┐     ┌──────────────┐
│   Claude Code   │────▶│              LLM Security Proxy         │────▶│   LiteLLM    │
│   (Developer)   │◀────│  Input Policy │ Forward │ Output Check  │◀────│   (Upstream) │
└─────────────────┘     └─────────────────────────────────────────┘     └──────────────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ Sonatype     │
                                   │ Nexus        │
                                   │ (Pkg Check)  │
                                   └──────────────┘
```

**Request Flow:**
1. **Auth** → Validate API key
2. **Rate Limit** → Per-app token bucket (60 burst, 1/s sustained)
3. **Input Policy** → Scan for PII, credentials, prompt injection
4. **Forward** → Translate format, call upstream LLM
5. **Output Security** → Extract code blocks, validate packages against Nexus
6. **Response** → Return to client or block with error

---

## Security Features

### Input Policy Engine

| Threat | Detection Method | Example Blocked |
|--------|------------------|-----------------|
| **PII Exposure** | Microsoft Presidio | `Email me at john@company.com` |
| **Credential Leak** | 11 regex patterns | `sk-proj-abc123...`, `AKIA...` |
| **Prompt Injection** | 8 heuristic patterns | `Ignore previous instructions...` |

**Patterns Detected:**
- OpenAI, Anthropic, GitHub, AWS keys
- Bearer tokens, Basic auth
- Private key blocks (RSA, EC, OpenSSH)
- Connection strings (MongoDB, PostgreSQL, Redis)
- Password assignments

### Output Security Engine

| Check | Action | Example |
|-------|--------|---------|
| **Unknown Package** | Block response | `import evil_pkg` not in Nexus |
| **Nexus Unavailable** | Fail-closed (block) | Circuit breaker after 3 failures |
| **Approved Package** | Allow through | `import requests` found in Nexus |

**Languages Supported:**
- Python (import, from...import, pip install)
- JavaScript/TypeScript (require, import from, npm install)
- Java (import statements)
- Go (import blocks)
- Ruby (require, gem)
- Shell/Bash (pip install, npm install)

---

## Endpoints

| Endpoint | Format | Auth | Purpose |
|----------|--------|------|---------|
| `POST /v1/messages` | Anthropic | Pass-through | Claude Code compatibility |
| `POST /v1/chat/completions` | OpenAI | Proxy keys | Generic OpenAI clients |
| `GET /health` | - | None | Liveness probe |
| `GET /ready` | - | None | Readiness probe (checks Nexus) |

---

## Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `BLOCKED_PII` | 400 | Personal information detected |
| `BLOCKED_CREDENTIALS` | 400 | API keys or secrets detected |
| `BLOCKED_INJECTION` | 400 | Prompt injection attempt |
| `BLOCKED_UNVALIDATED_DEP` | 400 | Package not in approved Nexus repo |
| `NEXUS_UNAVAILABLE` | 400 | Cannot validate (fail-closed) |
| `UNAUTHORIZED` | 401 | Invalid or missing API key |
| `RATE_LIMITED` | 429 | Too many requests |
| `LLM_TIMEOUT` | 504 | Upstream didn't respond in 60s |

---

## Resilience Patterns

| Pattern | Implementation |
|---------|----------------|
| **Circuit Breaker** | Opens after 3 Nexus failures, 30s recovery |
| **Fail-Closed** | Nexus down = block all code responses |
| **Rate Limiting** | Token bucket per app_id |
| **Timeouts** | LLM: 60s, Nexus: 10s per call |

---

## Audit Logging

**Format:** Append-only JSONL at `logs/audit.jsonl`

```json
{
  "timestamp": "2026-03-27T20:00:00Z",
  "request_id": "uuid",
  "app_id": "claude-code-dev",
  "action": "BLOCKED",
  "block_code": "BLOCKED_PII",
  "model": "claude-opus-4-5",
  "prompt_hash": "sha256:abc...",
  "latency_ms": 45
}
```

**Privacy:** Raw prompts never logged — SHA-256 hash only.

---

## Test Coverage

| Category | Tests | Coverage |
|----------|-------|----------|
| Input Policy | 20 | PII, credentials, injection |
| Output Security | 22 | Code parsing, Nexus validation |
| Auth | 14 | Keys, headers, edge cases |
| Audit | 12 | Logging, thread safety |
| Resilience | 12 | Rate limit, timeouts, circuit breaker |
| E2E | 12 | Full pipeline scenarios |
| Anthropic Gateway | 42 | Format translation, streaming |
| **Total** | **138** | All passing |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Python 3.11 + FastAPI |
| PII Detection | Microsoft Presidio |
| LLM Routing | LiteLLM |
| Package Validation | Sonatype Nexus REST API |
| HTTP Client | httpx (async) |
| Container | Multi-stage Docker, non-root |
| Testing | pytest + httpx AsyncClient |

---

## Deployment

```bash
# Development
source .env && .venv/bin/uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080

# Production (Docker)
docker-compose up -d
```

**Required Environment:**
```
LITELLM_API_BASE=http://litellm-server:3115/api
NEXUS_BASE_URL=https://nexus.company.com
NEXUS_API_KEY=<token>
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Fail-closed on Nexus errors | Security over availability |
| Pass-through auth for Anthropic | Users already have LiteLLM keys |
| Scan only last user message | Avoid cascading blocks from conversation history |
| Redact old violations (don't block) | Allow users to continue after a block |
| No streaming in v1 | Can't scan output before it reaches client |

---

## Lessons Learned

1. **Presidio false positives** — Tech terms (Django, Flask, Anthropic) flagged as person names. Solved with allowlist.

2. **Claude Code message format** — Bundles multiple turns as content blocks in a single message. Must check at block level, not message level.

3. **pip install flags** — `-r` from `pip install -r requirements.txt` was parsed as a package. Fixed parser to skip flags.

4. **Conversation history after blocks** — Old blocked content would block all future requests. Solved by redacting old violations instead of blocking.

---

## Future Enhancements

- [ ] Streaming support with chunked output scanning
- [ ] Webhook notifications for blocked requests
- [ ] Admin dashboard for audit log visualization
- [ ] Configurable policy rules per team/app
- [ ] Integration with vulnerability databases (OSV, Snyk)

---

## Live Demo Screenshots

### 1. Setup — Connecting Claude Code to the Proxy

![Setup](screenshots/01-setup.png)

*Developer configures environment variables to route Claude Code through the security proxy.*

```bash
export ANTHROPIC_BASE_URL="http://localhost:8080"
export ANTHROPIC_API_KEY="<litellm-key>"
claude --model claude-opus-4-5
```

---

### 2. Allowed Request — Approved Package (requests)

![Allowed](screenshots/02-allowed.png)

*Request passes input policy, LLM generates code using `requests`, package found in Nexus, response delivered.*

---

### 3. Blocked Request — Unapproved Package (anthropic)

![Blocked](screenshots/03-blocked.png)

*Request passes input policy, but LLM generates code with `import anthropic`. Package not found in Nexus → `BLOCKED_UNVALIDATED_DEP`.*

---

### 4. Blocked Request — PII Detected

![PII Blocked](screenshots/04-pii-blocked.png)

*Email address detected in prompt → `BLOCKED_PII`. Request never reaches LLM.*

---

## Current Issues & Next Steps

### Known Issues Being Addressed

| Issue | Description | Planned Fix |
|-------|-------------|-------------|
| **Conversation context after output block** | When a response is blocked (e.g., unapproved package), the LLM still has conversation context. Subsequent prompts like "ok" cause LLM to retry the blocked request. | Investigate conversation history sanitization for output blocks, or return a signal to client to clear context. |
| **Presidio false positives** | Some tech terms still get flagged as person names. Current allowlist covers common cases but edge cases remain. | Expand allowlist dynamically, consider training custom Presidio recognizer. |
| **No streaming support** | All responses are buffered. This adds latency and prevents real-time output. | Implement chunked output scanning — accumulate code blocks, validate incrementally. |

### Planned Enhancements (Next Phase)

1. **Streaming Support**
   - Buffer code blocks during stream
   - Validate packages as blocks complete
   - Fail-fast on first blocked package

2. **Admin Dashboard**
   - Real-time audit log visualization
   - Block rate metrics per app/team
   - Policy violation trends

3. **Configurable Policies**
   - Per-team PII sensitivity levels
   - Custom package allowlists
   - Prompt injection rule tuning

4. **Vulnerability Integration**
   - Cross-reference packages with OSV/Snyk
   - Block packages with known CVEs
   - Severity-based blocking thresholds

5. **Improved Error UX**
   - More descriptive error messages
   - Suggest approved alternatives for blocked packages
   - Link to internal documentation

---

## Demo Commands

```bash
# Should PASS — safe prompt, approved package
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-1234" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Write Python using requests to fetch a URL"}]}'

# Should BLOCK — PII detected
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-1234" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Email results to john@secret.com"}]}'

# Should BLOCK — package not in Nexus
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-1234" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Write Python using langchain for RAG"}]}'
```

---

## Contact

- **Repository:** ~/LLM-proxy
- **Tests:** `.venv/bin/python -m pytest tests/`
- **Logs:** `logs/audit.jsonl`
