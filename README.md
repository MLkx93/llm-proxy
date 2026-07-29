# LLM Security Proxy

A drop-in HTTP proxy that sits between AI coding assistants (Claude Code, IDE
plugins, CI jobs) and LLM providers, so that **secrets and PII never leave the
network** and **package names the model invents never reach a developer's
terminal**.

It exists because an LLM coding assistant is two separate supply-chain risks
wearing one coat: developers paste credentials and customer data into prompts,
and models hallucinate plausible-sounding package names that attackers register
on PyPI/npm ("slopsquatting"). Point your client's base URL at this proxy and
both are handled centrally, with an audit trail, instead of relying on every
developer to be careful.

---

## Table of contents

- [How it works](#how-it-works)
- [Setup](#setup)
- [Running it](#running-it)
- [Verifying it actually works](#verifying-it-actually-works)
- [Configuration](#configuration)
- [Known issues](#known-issues)
- [Gotchas](#gotchas)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Design notes](#design-notes)

---

## How it works

```
Claude Code / curl / CI
        │  ANTHROPIC_BASE_URL or OPENAI_BASE_URL points here
        ▼
┌───────────────────────────────────────────────┐
│  Security Proxy  :8080                        │
│    1. Auth (config/api_keys.yaml) + rate limit│
│    2. INPUT  — PII redact, secrets, injection │
│    3. → upstream LLM (OpenRouter / LiteLLM)   │
│    4. OUTPUT — parse code, validate packages  │
│    5. Audit log (Postgres + JSONL)            │
└───────────────────────────────────────────────┘
        ▼
  OpenRouter → OpenAI / Anthropic / Google / Meta
```

The proxy exposes **two API surfaces backed by the same pipeline**:

| Endpoint | Format | Used by |
|---|---|---|
| `POST /v1/chat/completions` | OpenAI | curl, OpenAI SDKs, most tooling |
| `POST /v1/messages` | Anthropic | Claude Code, Anthropic SDK |

Anthropic requests are translated to OpenAI format, sent upstream, and
translated back. That translation is why one security pipeline covers both.

Two extra surfaces ship alongside it:

- **Admin console** — `http://localhost:8080/admin`, served by the proxy itself.
  Security-team view: audit log and blocked-request stats. Works even if the
  chat UI is deleted.
- **Demo chat UI** — `http://localhost:8000`, a React app plus its own FastAPI
  backend, for showing the proxy's behaviour interactively.

### What gets blocked

Every rejection returns a stable `block_code`, which is what the audit log and
dashboard aggregate on:

`BLOCKED_PII` · `BLOCKED_CREDENTIALS` · `BLOCKED_INJECTION` ·
`BLOCKED_UNVALIDATED_DEP` · `BLOCKED_VULNERABLE_PACKAGE` ·
`BLOCKED_VULNERABLE_VERSION` · `BLOCKED_DEPENDENCY_VULNERABILITY` ·
`BLOCKED_SANDBOX` · `BLOCKED_GUARDRAILS` · `NEXUS_UNAVAILABLE` ·
`RATE_LIMITED` · `UNAUTHORIZED` · `LLM_TIMEOUT` · `LLM_ERROR`

Note that PII **redacts** by default rather than blocking (`PII_ACTION=redact`)
— the request proceeds with `jane@corp.com` replaced by `[REDACTED]`.
Credentials **block** by default (`CREDENTIAL_ACTION=block`), because a leaked
AWS key is not something you want to silently paper over.

---

## Setup

### Prerequisites

- **Python 3.12** (3.12.3 is what this was developed and tested against)
- **Docker + Docker Compose** — required for Postgres; also for the optional
  sandbox phase
- **Node.js 20+** — only if you want to rebuild the React frontend
- An **OpenRouter API key** (or an existing LiteLLM server)

### Option A — Docker (recommended, and what actually gets used)

This is the path with the fewest surprises: it builds the spaCy model into the
image and wires the containers together for you.

```bash
git clone <this-repo> llm-proxy
cd llm-proxy

cp .env.example .env
# Edit .env — at minimum set OPENROUTER_API_KEY (see Configuration below)

docker compose -f docker/docker-compose.yml up -d --build
```

Brings up four containers: `postgres` (host port **5433**), `proxy` (8080),
`webui` (8000), `frontend` (3000).

### Option B — Local Python

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# REQUIRED and NOT in requirements.txt — Presidio will not start without it.
python -m spacy download en_core_web_sm

# Presidio's anonymizer is also not in requirements.txt:
pip install presidio-anonymizer

cp .env.example .env      # then edit it

# Postgres still comes from Docker; the app degrades to JSONL without it,
# but the dashboard needs it.
docker compose -f docker/docker-compose.yml up -d postgres

bash scripts/proxy.sh     # starts proxy :8080 and webui API :8000
```

> **The spaCy model is the single most common setup failure.** It is installed
> in `docker/Dockerfile` but absent from `requirements.txt`, so a local install
> looks complete and then dies at the first request with a spaCy model-loading
> error. See [Known issues](#known-issues).

### Frontend (only if changing the UI)

```bash
cd src/webui-react
npm install
npm start        # dev server on :3000
npm run build    # production build → served by :8000 and by /admin on :8080
```

---

## Running it

```bash
bash scripts/proxy.sh      # start proxy + webui API (writes logs/*.pid)
bash scripts/stop.sh       # stop both
bash scripts/launch_all.sh # postgres + proxy + webui, with a printed summary
```

`scripts/start_proxy.sh` runs the proxy alone with the demo feature flags
(`STREAMING_ENABLED`, `VULN_SCAN_ENABLED`, `MALICIOUS_CODE_ENABLED`) forced on.

### Pointing Claude Code at the proxy

```bash
export ANTHROPIC_BASE_URL="http://localhost:8080"
export ANTHROPIC_API_KEY="dev-local-key-1234"   # a proxy key, not a real Anthropic key
claude
```

![Claude Code configured against the proxy](screenshots/setup.png)

The key is one of the demo keys in `config/api_keys.yaml`, **not** an Anthropic
credential. The proxy authenticates you against its own registry and uses its
*own* upstream key to call the provider — which is the point: developers never
hold provider credentials.

---

## Verifying it actually works

Run these in order. If all four behave as described, the pipeline is live.

**1. The process is up**

```bash
curl -s localhost:8080/health
# {"status":"ok"}
```

**2. Auth is enforced**

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}'
# 401
```

**3. Credentials are blocked** — the important one; needs no upstream credits

```bash
curl -s -X POST localhost:8080/v1/chat/completions \
  -H 'Authorization: Bearer dev-local-key-1234' \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"my aws key is AKIAIOSFODNN7EXAMPLE"}]}'
# {"error":{"code":"BLOCKED_CREDENTIALS","message":"Prompt contains what appears to be secret credentials or API keys.",...}}
```

**4. The block was recorded**

```bash
curl -s localhost:8080/v1/audit/stats -H 'Authorization: Bearer dev-local-key-1234'
# {"total":3,"blocked":2,...,"findingCounts":{"AWS_ACCESS_KEY":1},...}
```

Check PII redaction without spending upstream credits:

```bash
.venv/bin/python -c "
from src.input_policy import engine
s, p, d = engine.check_and_sanitize_openai([{'role':'user','content':'contact jane.doe@example.com'}])
print(s); print(d['pii_types'])"
# [{'role': 'user', 'content': 'contact [REDACTED]'}]
# ['EMAIL_ADDRESS']
```

Below: PII redaction and a blocked hallucinated package, seen from Claude Code.

![PII blocked in Claude Code](screenshots/allowed.png)
![Hallucinated package blocked](screenshots/blocked.png)

> `/ready` returns **503** `NEXUS_BASE_URL not configured` on a default install.
> That is expected — see the Nexus issue below. Use `/health` for liveness.

---

## Configuration

Everything is environment variables, read in `config/settings.py`. Copy
`.env.example` to `.env`; `.env` is gitignored and must never be committed.

### Minimum to get running

| Variable | Notes |
|---|---|
| `OPENROUTER_API_KEY` | Primary provider. Its presence alone switches the proxy into OpenRouter mode. **Missing from `.env.example` — add it manually.** |
| `DATABASE_URL` | Defaults to `postgresql+asyncpg://shield:shield@localhost:5433/shield`, matching docker-compose. Also missing from `.env.example`. |

### Provider selection

There is no `PROVIDER=` switch; the mode is inferred:

- `OPENROUTER_API_KEY` set → **OpenRouter** (`use_openrouter`)
- otherwise `LITELLM_API_BASE` set → **LiteLLM** passthrough (`use_litellm`)
- neither → every request fails with `LLM_ERROR` / `NO_UPSTREAM`

### Security phases

Phase 0 (malicious-code patterns) and the Nexus allowlist always run. The rest
are opt-in and default to **off**:

| Variable | Default | Phase |
|---|---|---|
| `MALICIOUS_CODE_ENABLED` | `true` | 0 — regex/AST patterns |
| `VULN_SCAN_ENABLED` | `false` | 1 — OSV/CVE lookup |
| `VERSION_VALIDATION_ENABLED` | `false` | 2 — version-range advisories |
| `DEPENDENCY_SCAN_ENABLED` | `false` | 3 — transitive tree |
| `SANDBOX_ENABLED` | `false` | 4 — Docker behavioural analysis |
| `GUARDRAILS_ENABLED` | `false` | 5 — toxicity / prompt leakage |

They default off because each adds latency and external calls; turn on only
what you need. The `*_BLOCK_MIN_SEVERITY` variants are deliberately stricter
than the `*_MIN_SEVERITY` scan thresholds — the system detects broadly and
blocks narrowly, so the audit log stays informative without over-blocking.

### Handling policy

| Variable | Default | Effect |
|---|---|---|
| `PII_ACTION` | `redact` | `redact` or `block` |
| `CREDENTIAL_ACTION` | `block` | `block` or `redact` |
| `STREAMING_ENABLED` | `false` | SSE streaming; scans chunks as they arrive |
| `LLM_TIMEOUT_S` | `120` | Upstream timeout |

---

## Known issues

Ordered by how much time they will cost you.

### 1. Nexus is fail-closed and unconfigured by default — all code responses block

With `NEXUS_BASE_URL` empty (the shipped default), **any LLM response
containing a code block is rejected** with:

```
NEXUS_UNAVAILABLE — "Nexus is not configured. Cannot validate dependencies."
```

Plain prose replies work fine, which makes this look like an intermittent bug
rather than a config gap. It is deliberate: an unvalidated dependency is
exactly the thing this proxy exists to stop, so it refuses rather than guesses.

**Worse: `NEXUS_FAIL_OPEN` does not work.** It is defined in
`config/settings.py:26` and documented in `docs/nexus_fix_spec.md`, but it is
**read nowhere in the codebase** — I grepped the whole tree. Setting it to
`true` has no effect; the "not configured" branch in
[src/output_security/nexus.py:90-97](src/output_security/nexus.py#L90-L97)
returns a block unconditionally.

**Fix:** point `NEXUS_BASE_URL` at a Nexus Repository instance. To develop
without one, either implement the missing `NEXUS_FAIL_OPEN` check in that
branch, or test with prompts that don't produce code.

### 2. Ten tests fail on a clean checkout

`283 passed, 10 failed`. They fail for three unrelated reasons — don't treat
them as one bug:

**Stale test expectations (assertions are simply wrong):**
- `test_dependency_tree.py::test_node_is_leaf` — asserts a node with no
  children is *not* a leaf, contradicting `is_leaf` at
  [dependency_tree.py:45-47](src/output_security/dependency_tree.py#L45-L47).
- `test_sandbox.py::test_calculate_risk_score` — expects `13.0` from a
  function that caps at `10.0` (the test's own comment says "capped at 10").
- `test_security_orchestrator.py::test_phase_order` — expects `NEXUS` first,
  but `MALICIOUS_CODE` was later added ahead of it.

**Environment-dependent:**
- `test_sandbox.py::test_safe_code_passes` — needs a working Docker socket;
  returns `SandboxStatus.ERROR` without one.
- `test_pii_redaction.py::test_multiple_pii_types_redaction` — Presidio
  redacts the word "phone" in "office phone" as part of a `PHONE_NUMBER` span,
  so an assertion on surrounding text fails. Cosmetic; redaction is correct.

**Costs real money / needs upstream credits:**
- `test_audit.py::test_input_blocked_audit_event`,
  `test_e2e.py::test_pii_in_prompt_blocked`,
  `test_anthropic_gateway.py::test_pii_blocked` and
  `::test_pii_in_content_blocks_blocked` — **these call the live OpenRouter
  API.** They currently fail with HTTP 402 (out of credits). Two also have real
  mocking bugs (`Object of type coroutine is not JSON serializable`).

### 3. The OpenRouter account is out of credits

Any real completion returns HTTP 402. Add credits or swap
`OPENROUTER_API_KEY`. Everything up to the upstream call (auth, PII,
credentials, audit) still works and is testable offline.

### 4. Demo authentication is not production auth

`admin/admin` and `user/user` are hardcoded in
[src/proxy/main.py:133-136](src/proxy/main.py#L133-L136), and `JWT_SECRET`
defaults to `shield-demo-secret-change-me`. The app logs a warning at startup
when these defaults are live. Keycloak/OIDC support exists
(`OIDC_ENABLED=true`, see `docs/KEYCLOAK_ADMIN_SETUP.md`) and is the intended
production path.

### 5. `.env.example` is incomplete

Missing several variables the code reads: `OPENROUTER_API_KEY`,
`OPENROUTER_BASE_URL`, `DATABASE_URL`, `STREAMING_ENABLED`,
`CREDENTIAL_ACTION`, `MALICIOUS_CODE_ENABLED`, `LLM_TIMEOUT_S`, and the
`GUARDRAILS_*` group. Treat `config/settings.py` as the authoritative list.

### 6. Credentials were removed from git history

This repository's history was rewritten before publication to purge a proxy
bearer token, a Stitch API key, an internal LiteLLM host, and personal
identifiers. **Every commit hash changed.** Any clone predating that rewrite
is incompatible and should be discarded. The affected credentials should be
considered compromised and rotated.

---

## Gotchas

Things that look wrong but aren't, and things that look fine but aren't.

- **`/ready` returns 503 on a healthy install.** It checks `NEXUS_BASE_URL`.
  Use `/health` for liveness/orchestration probes.

- **Postgres is on host port `5433`, not 5432.** Deliberate — 5432 is usually
  taken by a local install. Inside the Docker network, containers talk to
  `postgres:5432`; docker-compose overrides `DATABASE_URL` per-container to
  handle this. Connecting from the host requires `localhost:5433`.

- **`src/webui-react/.env` has its comment and its variable on the same line**,
  so `REACT_APP_API_URL` is silently commented out and the frontend falls back
  to its default. Put the variable on its own line if you need to override it.

- **Scripts must run from the repository root.** `scripts/proxy.sh` and
  `start_proxy.sh` resolve `.venv` and `.env` relative to the working
  directory. `launch_all.sh` `cd`s to the root itself; the others don't.

- **`.env` changes require a restart.** Nothing hot-reloads config;
  `config/settings.py` reads the environment once at import.

- **`config/api_keys.yaml` is loaded once at startup.** Adding a key means
  restarting the proxy. The committed keys (`dev-local-key-1234`,
  `ci-pipeline-key-5678`) are **demo values — replace them before any real
  deployment.**

- **Two API key systems exist and are unrelated.** `/v1/chat/completions`
  validates against `config/api_keys.yaml`. `/v1/messages` accepts *any*
  non-empty key and hashes it into an `app_id` for rate limiting — because in
  LiteLLM mode it forwards the caller's own key upstream. Do not assume
  `/v1/messages` enforces the registry.

- **Model names are rewritten.** `transform_model_name()` in
  `config/settings.py` maps Claude Code names to OpenRouter slugs. **The map is
  outdated** — it points `claude-sonnet-4.6` at `anthropic/claude-3-sonnet`.
  Unmapped names pass through unchanged, so prefer explicit OpenRouter slugs
  (`openai/gpt-4o-mini`) to avoid silently getting an older model.

- **`.venv` in this working copy was created in a *different* directory**
  (`/home/malakx/LLM-proxy`) and copied. Application imports resolve fine, but
  `pip` installs into the original path and pytest tracebacks cite files in the
  sibling directory. **Rebuild the venv from scratch** rather than debugging
  this.

- **Some "unit" tests make real, billed API calls.** See Known issue 2 before
  running the suite in a loop.

---

## Testing

```bash
pytest tests/ -v                  # everything (10 known failures)
pytest tests/unit/ -v             # unit only — mostly offline
pytest tests/integration/ -v      # needs a live upstream; costs credits
pytest tests/ --cov=src/ --cov-report=html
```

There is no `pytest.ini`/`pyproject.toml`, so **pytest must be run from the
repository root** for `src.*` imports to resolve.

---

## Project layout

```
src/
  proxy/            The proxy itself — both endpoints, auth, rate limiting,
                    streaming, translation, and the /admin console mount
  input_policy/     Inbound: Presidio PII, secret patterns, injection
  output_security/  Outbound: code parsing, Nexus, CVE, versions, dependency
                    tree, sandbox, guardrails, orchestrator
  audit/            Append-only audit log (Postgres + JSONL fallback)
  db/               SQLAlchemy models and session handling
  webui_api/        FastAPI backend for the demo chat UI (:8000)
  webui-react/      React frontend (:3000 dev, built into :8000 and /admin)
  webui/            Older Jinja2 UI, superseded by webui-react
config/
  settings.py       Authoritative list of every env var
  api_keys.yaml     Proxy API key registry (demo values — replace)
docker/             Dockerfiles + compose for the full stack
scripts/            proxy.sh / stop.sh / launch_all.sh / start_proxy.sh
tests/              unit/, integration/, benchmark/
docs/               Deep-dives; see docs/INDEX.md
```

Per-subsystem READMEs exist in `src/audit/`, `src/webui_api/`, and `src/webui/`.
`SETUP.md`, `GUIDE.md`, and `DOCKER_DEPLOYMENT_GUIDE.md` predate this file and
describe an earlier LiteLLM-based deployment; where they disagree with this
README, trust this one and `config/settings.py`.

---

## Design notes

**Why fail-closed?** An unvalidated package is the exact attack this proxy
exists to prevent. Failing open would mean a Nexus outage silently disables
supply-chain protection at the moment an attacker most benefits. The cost is
the awkward default in Known issue 1 — a deliberate trade, though the missing
`NEXUS_FAIL_OPEN` escape hatch makes it harsher than intended.

**Why redact PII but block credentials?** Redaction keeps the assistant useful
— a developer debugging a customer record still gets help after the name is
masked. Credentials have no such middle ground: a leaked key is compromised the
moment it is transmitted, and silently redacting one hides an incident that
should be investigated. Hence `PII_ACTION=redact`, `CREDENTIAL_ACTION=block`.

**Why translate Anthropic → OpenAI instead of proxying natively?** One
canonical internal format means the security pipeline is written once. Adding a
third client format requires only a translation pair, not a second pipeline.

**Why is the audit log append-only JSONL as well as Postgres?** The JSONL file
is the fallback that survives a database outage; `init_db()` failures are
caught so the proxy keeps serving and keeps recording. An audit system that
takes the service down with it, or quietly stops recording, is worse than none.

**Why hash prompts instead of storing them?** `prompt_hash` supports
deduplication and correlation without turning the audit database into the
largest collection of leaked secrets in the building. Where prompt text *is*
stored for the admin view, it is the redacted version — blocked requests are
passed through `_redact_secrets()` first
([src/proxy/main.py:480-487](src/proxy/main.py#L480-L487)).

**Why does the proxy serve its own admin console?** The audit subsystem is a
property of the proxy, not of the demo UI. Serving `/admin` from port 8080
means the security team's view survives deleting the entire chat interface —
see `src/audit/README.md`.

**Why is the spaCy analyzer warmed at startup?** Under `--workers`, each
process lazily builds its own `AnalyzerEngine`. Left lazy, concurrent first
requests race inside spaCy's model loading and 500. Warming it moves that
one-time cost into container startup
([src/proxy/main.py:47-60](src/proxy/main.py#L47-L60)).
