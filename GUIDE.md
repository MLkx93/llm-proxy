# LLM Proxy — Complete Project Guide

> **Background/onboarding reading, written against an earlier LiteLLM-based
> deployment.** For current setup and how to run the stack, see
> [README.md](README.md).

**Who this is for:** Someone with beginner-to-intermediate coding skills, no prior AI/ML experience, doing a cybersecurity internship focused on AI security and governance.

**What this teaches:** How every file in this project works, why each technology was chosen, and how to navigate the codebase independently.

---

## Table of Contents

1. [The Big Picture — What Are We Building and Why?](#1-the-big-picture)
2. [Technology Stack — What Tools We Use and Why](#2-technology-stack)
3. [Project Structure — The Map of the Codebase](#3-project-structure)
4. [The Request Lifecycle — Tracing One Request End-to-End](#4-the-request-lifecycle)
5. [File-by-File Breakdown](#5-file-by-file-breakdown)
6. [Security Decisions Explained](#6-security-decisions-explained)
7. [How to Read Python If You're New To It](#7-how-to-read-python)
8. [Concepts You Should Know](#8-concepts-you-should-know)
9. [Cheat Sheet — What to Look At When Things Go Wrong](#9-cheat-sheet)

---

## 1. The Big Picture

### The Problem We're Solving

In a company, developers use AI tools (like Claude Code, ChatGPT, etc.) by calling them through a LiteLLM server. Normally they set two environment variables and the requests go straight to LiteLLM:

```
Developer's tool                              LiteLLM Server
(Claude Code)  ──────────────────────────────► (litellm.internal.example:3115)
                   (no control, no visibility)     │
                                                   ▼
                                              AI Provider
                                         (Anthropic / OpenAI)
```

**Problems with this setup:**
- A developer might accidentally paste a password into a prompt — it gets sent to the AI
- An attacker might trick the AI into ignoring its safety rules (prompt injection)
- The AI might suggest code that uses a malicious or vulnerable library
- No record of what was sent or received (audit trail)
- No way to enforce company security policies

### Our Solution: A Transparent Gateway

We built a **gateway proxy** that sits between the developer's tools and the LiteLLM server. The key word is **transparent** — the developer doesn't know it exists. They set two environment variables and use their tools normally:

```bash
# Instead of pointing directly to LiteLLM:
export ANTHROPIC_BASE_URL="http://litellm.internal.example:3115/api"

# They point to the proxy:
export ANTHROPIC_BASE_URL="http://proxy-server:8080"
export ANTHROPIC_AUTH_TOKEN="their-proxy-key"
```

The full flow:

```
Developer's tool                    Our Proxy                  LiteLLM Server
(Claude Code)  ────────────────►  (localhost:8080)  ────────►  (litellm.internal.example:3115)
                                       │                            │
                                  Scans input                       ▼
                                  Scans output                 AI Provider
                                  Logs everything
```

Every prompt is scanned before it reaches the AI. Every response is scanned before it reaches the user. If something is unsafe, the proxy blocks it and logs it. The developer never notices any of this — it just works.

### Two Endpoints

The proxy exposes two API endpoints:

| Endpoint | Format | Used by | Auth header |
|----------|--------|---------|-------------|
| `POST /v1/messages` | Anthropic format | Claude Code, Anthropic SDK | `x-api-key: <key>` |
| `POST /v1/chat/completions` | OpenAI format | Other tools, OpenAI SDK | `Authorization: Bearer <key>` |

### Two-Tier Authentication

Users never get the real LiteLLM key. Instead:

```
User authenticates to proxy  →  with a proxy key (from config/api_keys.yaml)
Proxy authenticates to LiteLLM → with the real LiteLLM key (from .env)
```

This means the proxy controls all access. You can revoke a user's proxy key without affecting anyone else, and without changing the upstream LiteLLM key.

---

## 2. Technology Stack

### Python

**What it is:** The programming language the entire project is written in.

**Why Python:** The main AI routing library (LiteLLM) is written in Python. Python is also the dominant language in AI/ML tooling, so all the best libraries for this kind of work exist in Python.

---

### FastAPI

**What it is:** A Python web framework for building HTTP APIs.

**What it does for us:** It receives HTTP requests from client apps, runs them through our security checks, and sends back responses.

**Why FastAPI (not Flask, Django):**
- **Async-native:** It can handle many requests at the same time without freezing. This matters because our proxy spends a lot of time waiting — waiting for OpenAI to respond, waiting for Nexus to respond. While waiting on one request, it can process others.
- **Automatic validation:** We define what a valid request looks like using Pydantic models. If a client sends the wrong format, FastAPI rejects it automatically before our code even runs.
- **OpenAI-compatible:** We expose `/v1/chat/completions` — the exact same URL path that OpenAI uses. Any app already talking to OpenAI can point to our proxy with zero code changes.

---

### LiteLLM

**What it is:** A Python library that works as a universal adapter for 100+ AI providers.

**What it does:** You call one function (`litellm.acompletion()`), and it translates your request into the correct format for whichever provider you're using (OpenAI, Anthropic, Google, etc.).

**Why it matters:** Without LiteLLM, we'd need separate code for every AI provider. LiteLLM also manages the provider API keys — so those keys live only inside our proxy, never exposed to client applications.

---

### Presidio

**What it is:** Microsoft's open-source PII (Personally Identifiable Information) detection library.

**What it does:** It reads text and identifies personal data — email addresses, credit card numbers, social security numbers, names, phone numbers, etc.

**How it works inside:** Presidio uses two approaches at the same time:
1. **Regex patterns** — for structured data that always follows a pattern (credit cards look like `4111 1111 1111 1111`, emails have `@` in them)
2. **NLP (Natural Language Processing)** — for unstructured data like human names. A regex can catch `john.doe@example.com` but it can't catch "my name is John Doe." NLP understands the meaning of words in context, not just their shape.

This NLP part uses a pre-trained model called `en_core_web_sm` provided by spaCy (see below).

---

### spaCy

**What it is:** The NLP engine that Presidio uses under the hood.

**What it does:** Reads a sentence and labels each word/phrase with what it is — "PERSON", "ORG", "DATE", "EMAIL", etc. This is called Named Entity Recognition (NER).

**You don't interact with spaCy directly.** Presidio calls it for you. But this is why you see `en_core_web_sm` mentioned in the setup — that's the English language model spaCy needs.

---

### Pydantic

**What it is:** A Python data validation library.

**What it does:** Defines the exact shape that data must have. If incoming data doesn't match, it's automatically rejected with a clear error.

**Example from our code:**
```python
class ChatCompletionRequest(BaseModel):
    model: str                       # must be a string, required
    messages: List[Message]          # must be a list of Message objects
    temperature: Optional[float] = None  # optional, float or absent
```

If someone sends `{"model": 123}` (number instead of string), Pydantic rejects it before our function even runs.

---

### httpx

**What it is:** An HTTP client library for Python.

**What it does:** Makes outbound HTTP requests — in our case, from the proxy to the Nexus server to check if a software package is safe.

**Why httpx (not `requests`):** The standard `requests` library blocks — while it waits for a response, nothing else can happen. `httpx` is async — while it waits for Nexus to respond, our proxy continues handling other requests. This is important for performance.

---

### YAML

**What it is:** A human-readable configuration file format (`.yaml` or `.yml` files).

**What it does for us:** Stores our API key registry — the list of which apps are allowed to use the proxy.

**Why YAML (not JSON):** JSON doesn't support comments. We want to be able to annotate our config files with explanations.

---

### Docker

**What it is:** A tool that packages the app and all its dependencies into an isolated container.

**Why we use it:**
- **Runs as a non-root user** (uid 1001) — if the container is compromised, the attacker has limited permissions, not root access
- **Read-only filesystem** — the container can't write files except to the logs volume
- **Reproducible** — the same image runs identically on any machine
- **No dependency conflicts** — everything the app needs is inside the container

---

## 3. Project Structure

```
LLM-proxy/
│
├── src/                        ← All application source code
│   ├── __init__.py             ← Makes src/ a Python package
│   ├── proxy/                  ← Core proxy (entry point, auth, rate limiting)
│   │   ├── __init__.py
│   │   ├── main.py             ← THE central file — the whole request pipeline
│   │   ├── models.py           ← Data shapes (what a request/response looks like)
│   │   ├── logging.py          ← Structured JSON logger
│   │   ├── auth.py             ← API key validation
│   │   └── rate_limiter.py     ← Token bucket rate limiter
│   │
│   ├── input_policy/           ← Checks the PROMPT (before it reaches the AI)
│   │   ├── __init__.py
│   │   ├── engine.py           ← Runs all input checks in order
│   │   ├── patterns.py         ← Regex patterns for secrets/credentials
│   │   └── injection.py        ← Prompt injection detection patterns
│   │
│   ├── output_security/        ← Checks the RESPONSE (after the AI replies)
│   │   ├── __init__.py
│   │   ├── engine.py           ← Runs all output checks in order
│   │   ├── code_parser.py      ← Extracts code blocks and dependency names
│   │   └── nexus.py            ← Nexus Firewall client + circuit breaker
│   │
│   └── audit/
│       ├── __init__.py
│       └── logger.py           ← Writes audit events to logs/audit.jsonl
│
├── config/
│   ├── settings.py             ← Loads configuration from environment variables
│   └── api_keys.yaml           ← Which apps can use the proxy (test keys)
│
├── tests/
│   ├── integration/
│   │   ├── test_proxy.py       ← Core pass-through tests
│   │   └── test_e2e.py         ← Full end-to-end scenario tests
│   └── unit/
│       ├── test_input_policy.py
│       ├── test_output_security.py
│       ├── test_auth.py
│       ├── test_audit.py
│       └── test_resilience.py
│
├── docker/
│   ├── Dockerfile              ← How to build the container image
│   └── docker-compose.yml      ← How to run everything together locally
│
├── logs/                       ← Runtime audit logs (not tracked by git)
├── .env.example                ← Template for secrets (never commit .env itself)
├── .gitignore                  ← Files git should never track
├── .dockerignore               ← Files excluded from Docker image
├── requirements.txt            ← All Python packages the project depends on
├── Context.md                  ← Original architecture specification
├── SETUP.md                    ← Step-by-step first-time setup guide
├── GUIDE.md                    ← This file
└── tasks/
    ├── todo.md                 ← Implementation plan
    └── lessons.md              ← Lessons learned
```

---

## 4. The Request Lifecycle

This is the most important section. Understanding this flow means you understand the entire system.

Both endpoints (`/v1/messages` and `/v1/chat/completions`) follow the same pipeline. The Anthropic endpoint (`/v1/messages`) is shown here because it's what Claude Code uses.

```
Claude Code sends POST /v1/messages
(user has ANTHROPIC_BASE_URL pointed to the proxy)
            │
            ▼
┌─────────────────────────────┐
│   Step 1: Assign UUID       │  Every request gets a unique ID for tracing
│   request_id = uuid4()      │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│   Step 2: Authentication    │  Is the x-api-key header valid?
│   validate_api_key(header)  │  Looked up against config/api_keys.yaml
│                             │  If NO → 401 UNAUTHORIZED + audit log
└─────────────┬───────────────┘
              │ YES
              ▼
┌─────────────────────────────┐
│   Step 3: Rate Limiting     │  Has this app sent too many requests?
│   is_allowed(app_id)        │  If NO → 429 RATE_LIMITED + audit log
└─────────────┬───────────────┘
              │ YES
              ▼
┌─────────────────────────────┐
│   Step 4: Input Policy      │  Scan the prompt for:
│   1. Secrets/credentials    │    - API keys, passwords, private keys
│   2. Prompt injection       │    - "ignore instructions", jailbreaks
│   3. PII (Presidio)         │    - emails, names, credit cards
│                             │  If ANY found → 400 BLOCKED_* + audit log
│                             │  The AI is NEVER called
└─────────────┬───────────────┘
              │ CLEAN
              ▼
┌─────────────────────────────┐
│   Step 5: Forward to        │  Send request to LiteLLM server via httpx
│   upstream LiteLLM          │  URL: LITELLM_API_BASE/v1/messages
│                             │  Auth: x-api-key: LITELLM_API_KEY
│                             │  If streaming: buffer SSE, return as single response
│                             │  60 second timeout
│                             │  If timeout → 504 LLM_TIMEOUT
│                             │  If error   → 502 LLM_ERROR
└─────────────┬───────────────┘
              │ GOT RESPONSE
              ▼
┌─────────────────────────────┐
│   Step 6: Output Security   │  Scan the AI's response:
│   1. Find code blocks       │    - Look for ```code``` blocks
│   2. Extract dependencies   │    - Pull out package names (requests, flask…)
│   3. Validate via Nexus     │    - Ask Nexus: is this package safe?
│                             │  If unsafe → 400 BLOCKED_UNVALIDATED_DEP
│                             │  If Nexus down → 400 NEXUS_UNAVAILABLE
└─────────────┬───────────────┘
              │ SAFE
              ▼
┌─────────────────────────────┐
│   Step 7: Return + Log      │  Send response to Claude Code
│                             │  Write ALLOWED event to audit log
│                             │  (User sees the AI response normally)
└─────────────────────────────┘
```

**Key point:** Every exit — whether it's a block or a success — writes an audit event. You can always answer "what happened to request X?" by searching `logs/audit.jsonl`.

**Streaming:** When Claude Code sends `stream: true`, the proxy accepts it, buffers the full streamed response from LiteLLM internally, runs output checks on the complete text, then returns it as a single non-streamed response. The user's tool still works — it just doesn't see the response token-by-token.

---

## 5. File-by-File Breakdown

### `src/proxy/main.py` — The Central File

This is the most important file. It defines the entire request pipeline and contains **two endpoints**:

| Endpoint | Function | Format | How it forwards |
|----------|----------|--------|----------------|
| `POST /v1/messages` | `anthropic_messages()` | Anthropic | Direct httpx pass-through to LiteLLM |
| `POST /v1/chat/completions` | `chat_completions()` | OpenAI | Via `litellm.acompletion()` |

The Anthropic endpoint (`/v1/messages`) is the primary one — it's what Claude Code uses. It receives the raw request, runs security checks, then forwards it to the upstream LiteLLM server using httpx (an HTTP client). If the request is streaming, it buffers the full response internally before returning it.

The OpenAI endpoint (`/v1/chat/completions`) uses the LiteLLM library to translate and route. It can work with or without an upstream LiteLLM server.

**Key code patterns you'll see:**

```python
@app.middleware("http")
async def attach_request_id(request: Request, call_next):
```
- `@app.middleware("http")` — This function runs for EVERY request before any endpoint function runs. It's a preprocessing step.
- `async def` — This function is asynchronous. When it waits for something (like an AI response), other requests can still be processed.
- `call_next` — Passes the request to the next handler in the chain.

```python
@app.post("/v1/messages")
async def anthropic_messages(request: Request):
```
- `@app.post(...)` — This function handles HTTP POST requests to that specific URL.
- The body is parsed manually with `await request.json()` because Anthropic requests have a different shape than OpenAI ones.

```python
async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT_S)) as client:
    upstream_resp = await client.post(upstream_url, json=body, headers=upstream_headers)
```
- This is how the Anthropic endpoint forwards requests to LiteLLM — it makes an HTTP POST request, just like curl does, but from Python code.
- `async with` ensures the HTTP connection is properly closed when done.

```python
await asyncio.wait_for(
    litellm.acompletion(...),
    timeout=LLM_TIMEOUT_S,
)
```
- `await` — "Wait for this to finish, but let other requests run in the meantime."
- `asyncio.wait_for(..., timeout=60)` — If the AI doesn't respond within 60 seconds, stop waiting and raise a `TimeoutError`.

---

### `src/proxy/auth.py` — API Key Validation

**How it works step by step:**

1. At startup, reads `config/api_keys.yaml` and loads all enabled keys
2. For each key, computes a SHA-256 hash and stores ONLY the hash in memory
3. When a request arrives, hashes the key from the `Authorization` header and looks up that hash

```python
def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
```

**Why store hashes instead of the raw keys?**
If an attacker somehow reads the process memory (via a crash dump, debug endpoint, etc.), they'd see hashes — not usable keys. Hashes are one-way: you can't reverse them back to the original key. This is the same principle used for password storage.

---

### `src/proxy/rate_limiter.py` — Token Bucket

**How the algorithm works:**

Think of a bucket that holds 60 tokens. Every request costs 1 token. Tokens refill at a rate of 1 per second (so 60 per minute sustained).

```
Bucket:     [████████████████████████] 60 tokens
Request 1:  [███████████████████████ ] 59 tokens  ✓ allowed
Request 2:  [██████████████████████  ] 58 tokens  ✓ allowed
...
Request 60: [                        ]  0 tokens  ✓ allowed
Request 61: [                        ]  0 tokens  ✗ denied → 429
(1 second passes, 1 token refills)
Request 62: [                        ]  0 tokens  ✓ allowed
```

**Why per `app_id` (not per IP)?**
Multiple users or services might share the same IP address. If we limited by IP, one misbehaving app would block other legitimate apps on the same IP. Limiting by `app_id` means each application has its own independent quota.

---

### `src/input_policy/engine.py` — Prompt Scanner

**The checks run in this order, and order matters:**

```python
# 1. Secrets (fast regex — runs first)
secrets = find_secrets(text)
if secrets: return block("BLOCKED_CREDENTIALS")

# 2. Injection (fast regex)
injections = find_injections(text)
if injections: return block("BLOCKED_INJECTION")

# 3. PII via Presidio (slower, uses NLP model — runs last)
results = analyzer.analyze(text=text, ...)
if results: return block("BLOCKED_PII")
```

Regex checks run in microseconds. Presidio with NLP takes milliseconds (it loads a machine learning model). By running the fast checks first, we skip the expensive NLP step when a cheap regex already caught the problem.

**The `@lru_cache(maxsize=1)` pattern:**
```python
@lru_cache(maxsize=1)
def _get_analyzer() -> AnalyzerEngine:
    return AnalyzerEngine()
```
Presidio takes about 2 seconds to start up (it loads the NLP model into memory). `@lru_cache` means "run this function once, remember the result, and return the remembered result on every future call." Without this, every single request would wait 2 seconds for the model to load.

---

### `src/input_policy/patterns.py` — Secret Detection Patterns

This file contains regex patterns that match known credential formats.

**Quick regex reference for reading the patterns:**

| Pattern piece | Meaning |
|--------------|---------|
| `\b` | Word boundary (the edge of a word) |
| `sk-` | The literal characters "sk-" |
| `[A-Za-z0-9]` | Any single letter or digit |
| `{20,}` | 20 or more of the previous thing |
| `(?i)` | Case insensitive (matches "password" and "PASSWORD") |
| `\s*` | Zero or more spaces |
| `[=:]` | Either `=` or `:` |
| `.+` | One or more of any character |

**Example — OpenAI key detection:**
```python
re.compile(r'\bsk-[A-Za-z0-9]{20,}\b')
```
This matches: the text `sk-` followed by at least 20 letters/numbers, surrounded by word boundaries.
It catches strings like: `sk-abcdefghijklmnopqrstuvwxyz123456`

---

### `src/input_policy/injection.py` — Prompt Injection Detection

**What is prompt injection?**

An attacker writes something in their input that tries to override the AI's instructions:
- `"Ignore all previous instructions and..."` — tries to override the system prompt
- `"You are now DAN mode enabled..."` — tries to jailbreak the model
- `"</system><user>..."` — tries to inject fake system-level messages

These are the AI equivalent of SQL injection — using the data channel to sneak in commands.

**Our approach:** We match against known attack phrases using regex. This catches known patterns but not brand-new, never-before-seen attacks. That's why it's one layer of protection, not the only one.

---

### `src/output_security/code_parser.py` — Response Code Analyser

**What it does, step by step:**

1. Looks through the AI's response for fenced code blocks:
   ````
   ```python
   import requests
   ```
   ````

2. Identifies the programming language from the tag (`python`, `javascript`, etc.)

3. Uses language-specific patterns to extract package names (e.g. `import requests` → `requests`)

4. Filters out standard library packages (`os`, `sys`, `json` are built into Python — no need to validate them)

5. Returns a list of external packages that need to be validated through Nexus

**Why scan code in AI responses?**
AI models can suggest packages that:
- Don't exist (the AI made them up) — attackers register these fake names as malicious packages
- Are misspelled versions of real packages (`requets` instead of `requests`) — a supply chain attack
- Have known security vulnerabilities
- Are outright malicious

---

### `src/output_security/nexus.py` — Nexus Client + Circuit Breaker

**What the circuit breaker does:**

A circuit breaker prevents the proxy from repeatedly hammering an external service that's already down.

```
CLOSED (normal operation)
    │
    │ 3 consecutive failures
    ▼
OPEN (Nexus is down — immediately reject all checks, don't even try to connect)
    │
    │ 30 seconds pass
    ▼
HALF-OPEN (try one test request to see if Nexus is back)
    │
    ├─ test succeeds → go back to CLOSED (normal)
    └─ test fails    → go back to OPEN (wait another 30 seconds)
```

**Why not just keep retrying?**
If Nexus is down, sending it more requests makes things worse — it slows down recovery. The circuit breaker gives it time to recover without being overwhelmed.

**Fail-closed behaviour:**
When the circuit is OPEN (Nexus is unreachable), we **block** any response that contains code. We chose this in Phase 0. The alternative (allowing unvalidated code through) would mean a Nexus outage silently disables a security control — unacceptable.

---

### `src/audit/logger.py` — Audit Trail

**What gets logged for every request:**
```json
{
  "timestamp": "2026-03-18T09:46:08.415020+00:00",
  "request_id": "dab3863f-353c-4d86-a2b7-b33f370ea928",
  "app_id": "local-dev",
  "action": "BLOCKED",
  "block_code": "BLOCKED_PII",
  "model": "gpt-4o",
  "prompt_hash": "a3f2c1d4e5b6...",
  "latency_ms": 145
}
```

**Why hash the prompt instead of logging it?**
1. **Privacy** — Prompts may contain sensitive business information. Storing them in logs creates another place attackers could steal data from.
2. **Compliance** — GDPR and similar regulations restrict storing personal data. A hash can prove "this same prompt was sent twice" (same input always gives the same hash) without storing the actual content.

**JSONL format** = one JSON object per line. Each line is independently valid JSON. You can search it with `grep`, pipe it to tools, or feed it into log analysis platforms. Unlike a single big JSON array, you can append new entries without rewriting the whole file.

---

### `config/settings.py` — Configuration Loader

```python
class Settings:
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    LITELLM_API_BASE: str = os.environ.get("LITELLM_API_BASE", "")
    LITELLM_API_KEY: str = os.environ.get("LITELLM_API_KEY", "")
```

`os.environ.get("KEY", "")` — read the environment variable named "KEY". If it doesn't exist, return empty string as the default.

The most important settings here are `LITELLM_API_BASE` and `LITELLM_API_KEY` — these tell the proxy where the upstream LiteLLM server is and how to authenticate to it.

**Why environment variables instead of a config file?**
- Config files get committed to git accidentally → credential leak
- Environment variables are set at runtime by the deployment platform
- Different environments (dev/staging/production) use different values without changing code
- This is an industry-standard practice

---

### `config/api_keys.yaml` — Key Registry

```yaml
keys:
  - key: "dev-local-key-1234"
    app_id: "local-dev"
    team: "Development"
    enabled: true
```

**To add a new application:**
1. Generate a random key: `openssl rand -hex 32`
2. Add an entry to this file with `enabled: true`
3. Restart the proxy (keys load at startup)
4. Give the key to the application team securely

**To revoke access:**
Set `enabled: false` and restart. The key is rejected but the entry stays for audit history.

---

### `docker/Dockerfile` — Container Build

```dockerfile
FROM python:3.12-slim AS builder     # Stage 1: install everything
...
FROM python:3.12-slim AS runtime     # Stage 2: copy only what's needed
```

**Multi-stage build:** The first stage has compilers, build tools, and pip. The second stage has only the final installed packages. The result is a smaller, more secure image with fewer unnecessary tools.

```dockerfile
RUN groupadd --gid 1001 proxy \
 && useradd --uid 1001 --gid proxy --no-create-home --shell /sbin/nologin proxy
USER proxy
```
Creates and switches to a non-root user. If the app is exploited, the attacker has limited permissions — not root.

---

## 6. Security Decisions Explained

### Why block instead of redact?

We block requests containing PII or credentials rather than removing the sensitive parts and forwarding a cleaned version. Reason: redaction is hard to do perfectly. A redaction system that misses one pattern sends real data to the AI. For v1, blocking is the safer choice.

### Why fail-closed on Nexus?

If the dependency validation service is unreachable, we reject responses containing code. The alternative (fail-open: allow unvalidated code) would mean a Nexus outage silently disables a security control. Operators would never notice. Fail-closed is noisy on purpose — users report the issue, operators investigate, and the security posture is never silently degraded.

### Why hash prompts in the audit log?

SHA-256 is a one-way function — you cannot recover the original text from the hash. But the same input always produces the same hash. This means:
- You can tell if the same prompt was sent twice (correlation)
- You can verify a specific prompt against a hash ("was this what you sent?")
- But nobody can read stored prompts — privacy by design

### Why token bucket over fixed window rate limiting?

Fixed window: "allow 60 requests per minute." At 12:00:59 you send 60 requests, at 12:01:00 you send 60 more. That's 120 requests in 2 seconds — the limit is useless.

Token bucket: tokens refill continuously. You can burst up to the bucket size, but the sustained rate is strictly controlled regardless of timing tricks.

---

## 7. How to Read Python

Quick reference for the Python patterns you'll encounter in this project.

### Imports
```python
from fastapi import FastAPI, Request    # "from this library, import these specific things"
import litellm                          # "import the whole library"
```

### Type hints (the stuff after colons)
```python
def validate(authorization_header: Optional[str]) -> Optional[ApiKeyEntry]:
#                                   ↑ input type      ↑ return type
```
These are documentation — they tell you what a function expects and returns. Python doesn't enforce them at runtime, but editors use them for autocomplete and error checking.

### Dataclasses
```python
@dataclass
class PolicyResult:
    allowed: bool
    block_code: str = ""
```
A dataclass is a simple container for related data. The `@dataclass` decorator auto-generates the constructor, so you can write `PolicyResult(allowed=True)`. The `= ""` is a default value.

### `async` / `await`
```python
async def chat_completions(...):
    response = await litellm.acompletion(...)
```
`async def` = "this function might need to wait for external things."
`await` = "wait for this to finish, but let other work happen in the meantime."
Without `await`, the server would freeze while waiting for the AI to respond.

### Decorators (`@` symbol)
```python
@app.post("/v1/chat/completions")
def chat_completions(...):
```
`@` means "register or wrap this function." Here, it tells FastAPI "when someone sends a POST to `/v1/chat/completions`, run this function."

### `Optional[str]`
```python
from typing import Optional
def foo(x: Optional[str]) -> None:
```
`Optional[str]` = "this can be a string OR `None` (absent/missing)."

### List comprehension
```python
messages_raw = [m.model_dump() for m in body.messages]

# This is a shorter way to write:
messages_raw = []
for m in body.messages:
    messages_raw.append(m.model_dump())
```

### f-strings
```python
url = f"{base}/service/rest/v1/search?name={package}"
# Variables inside {} get replaced with their values
```

---

## 8. Concepts You Should Know

### REST API
Our proxy exposes a REST API — it communicates over HTTP using JSON. Each request is self-contained (stateless). The main endpoint is `POST /v1/chat/completions`.

### HTTP status codes used in this project

| Code | Name | When we use it |
|------|------|---------------|
| 200 | OK | Request allowed, response returned |
| 400 | Bad Request | Blocked by policy (PII, injection, unsafe code, streaming) |
| 401 | Unauthorized | Missing or invalid API key |
| 429 | Too Many Requests | Rate limit exceeded |
| 502 | Bad Gateway | LLM provider returned an error |
| 503 | Service Unavailable | Proxy not ready (`/ready` endpoint) |
| 504 | Gateway Timeout | LLM provider didn't respond in 60 seconds |

### Unit test vs Integration test vs E2E test

| Type | What it tests | Example from our project |
|------|--------------|------------------------|
| Unit | One function in isolation | "does `find_secrets()` catch an OpenAI key?" |
| Integration | Multiple components together | "does a POST to the endpoint return a response?" |
| E2E | The full request pipeline | "does a request with PII get blocked AND logged?" |

In our project, the actual AI and Nexus are always replaced with fakes ("mocked") in tests. We test our logic, not external services. This means tests run fast and don't need real API keys.

### Mocking
```python
with patch("src.proxy.main.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
    mock_llm.return_value = FAKE_RESPONSE
```
`patch` temporarily replaces `litellm.acompletion` with a fake version. The fake always returns `FAKE_RESPONSE`. After the `with` block ends, the real function is restored. This lets us test our code without calling real AI providers.

### Virtual environment (`.venv/`)
Python projects use virtual environments to keep their packages separate from the system Python. Instead of installing packages globally (which causes conflicts between projects), they're installed in `.venv/`. **Always use `.venv/bin/python` and `.venv/bin/pytest`, not the system `python3`.**

---

## 9. Cheat Sheet

### Running tests
```bash
# All tests
.venv/bin/python -m pytest tests/ -v

# One specific file
.venv/bin/python -m pytest tests/unit/test_auth.py -v

# One specific test
.venv/bin/python -m pytest tests/unit/test_auth.py::TestValidate::test_valid_key_returns_entry -v
```

### Starting the server
```bash
# Load environment variables
export $(grep -v '^#' .env | xargs)

# Start with auto-reload (dev only)
.venv/bin/uvicorn src.proxy.main:app --port 8080 --reload
```

### Sending a test request (Anthropic format — what Claude Code uses)
```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "x-api-key: dev-local-key-1234" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-6", "max_tokens": 100, "messages": [{"role": "user", "content": "Hello"}]}'
```

### Sending a test request (OpenAI format)
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-1234" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Reading the audit log
```bash
# Pretty-print
cat logs/audit.jsonl | python3 -m json.tool

# Live tail
tail -f logs/audit.jsonl | python3 -m json.tool

# Filter blocked requests only
grep '"action":"BLOCKED"' logs/audit.jsonl | python3 -m json.tool
```

### Where to look when something goes wrong

| Symptom | File to check | What to look for |
|---------|--------------|-----------------|
| 401 Unauthorized | `src/proxy/auth.py` + `config/api_keys.yaml` | Is the key present? Is `enabled: true`? |
| 429 Rate Limited | `src/proxy/rate_limiter.py` | `MAX_TOKENS` and `REFILL_RATE` constants |
| BLOCKED_PII | `src/input_policy/engine.py` | `PII_ENTITIES` list, `PRESIDIO_SCORE_THRESHOLD` |
| BLOCKED_CREDENTIALS | `src/input_policy/patterns.py` | `SECRET_PATTERNS` list |
| BLOCKED_INJECTION | `src/input_policy/injection.py` | `INJECTION_PATTERNS` list |
| BLOCKED_UNVALIDATED_DEP | `src/output_security/nexus.py` | Is `NEXUS_BASE_URL` set in `.env`? |
| NEXUS_UNAVAILABLE | `src/output_security/nexus.py` | `FAILURE_THRESHOLD`, `RECOVERY_TIMEOUT` |
| 504 LLM_TIMEOUT | `src/proxy/main.py` | `LLM_TIMEOUT_S` constant |

---

## How to Build a Mental Model of This Project

The best way to truly understand this codebase:

1. Open `src/proxy/main.py`
2. Start at the first line of the `anthropic_messages()` function (this is the primary endpoint)
3. Every time it calls another function, open that file and read what it does
4. When that function returns, go back to `main.py` and see what happens next
5. Follow the flow all the way to the final response

By the end of one trace, you will have visited every file in the project. Do this once, and you'll be able to navigate independently.

### How Users Connect

When a user (developer with Claude Code) runs this:
```bash
export ANTHROPIC_BASE_URL="http://proxy-server:8080"
export ANTHROPIC_AUTH_TOKEN="their-proxy-key"
```

The Anthropic SDK inside Claude Code reads those variables. When Claude Code makes a request, the SDK sends it to `http://proxy-server:8080/v1/messages` with `x-api-key: their-proxy-key` instead of sending it to Anthropic directly. The proxy does its work, forwards to LiteLLM, and returns the result. Claude Code doesn't know anything changed.
