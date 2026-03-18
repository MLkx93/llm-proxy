# LLM Proxy — Complete Guide for the Cybersecurity Intern

**Who this is for:** A network/cybersecurity engineer with solid networking fundamentals,
beginner-to-intermediate coding skills, and no prior AI/ML experience.

**What this teaches:** How every file in this project works, why each technology was chosen,
and how to read and navigate the codebase independently.

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

In a company, developers use AI tools (like ChatGPT, Claude, etc.) by calling them directly
from their applications. This is dangerous for several reasons:

```
Developer app ──────────────────────────────► OpenAI / Anthropic
                   (no control, no visibility)
```

**Problems with direct access:**
- A developer might accidentally paste a password into the prompt → it gets sent to OpenAI
- An attacker might trick the AI into ignoring its safety rules (prompt injection)
- The AI might suggest code that uses a malicious or vulnerable library
- No record of what was sent or received (audit trail)
- No way to enforce company policies

### Our Solution: A Proxy (Security Gateway)

We built a **proxy** — a middleman that sits between all applications and the AI providers.
Nothing gets through without our inspection.

```
Developer app ──► [Our Proxy] ──► OpenAI / Anthropic
                      │
                 Checks BOTH
                 input & output
```

Think of it like a **corporate firewall**, but instead of filtering TCP/IP packets,
it filters AI prompts and responses.

### Network Analogy (for your background)

| Network concept | Our proxy equivalent |
|----------------|---------------------|
| Firewall rule | Input/Output policy |
| Packet inspection (DPI) | Prompt content analysis |
| IDS/IPS | Injection detection |
| NAT gateway | Proxy entry point |
| ACL | API key authentication |
| Rate limiting (QoS) | Token bucket rate limiter |
| Syslog / SIEM feed | Audit log (audit.jsonl) |
| Circuit breaker (TCP) | Circuit breaker (Nexus client) |

---

## 2. Technology Stack

### Python

**What it is:** The programming language the entire project is written in.

**Why Python (not Java, Go, etc.):** The main AI routing library (LiteLLM) is Python-native.
Python is also the dominant language in AI/ML tooling, so all the best libraries exist here.

**Your analogy:** Like how Cisco IOS is the "language" for Cisco routers — you can configure
a Juniper switch too, but IOS is where all the Cisco-specific features live.

---

### FastAPI

**What it is:** A Python web framework for building HTTP APIs.

**What it does:** Receives HTTP requests, routes them to the right function, sends responses.

**Why FastAPI (not Flask, Django):**
- **Async-native:** Handles many simultaneous requests without blocking (like event-driven
  networking). Critical for a proxy that waits on external APIs.
- **Automatic validation:** Pydantic models validate incoming JSON automatically — if a field
  is missing or wrong type, FastAPI rejects it before your code even runs.
- **OpenAI-compatible:** We expose `/v1/chat/completions` — the exact same URL path that
  OpenAI uses. Any app already talking to OpenAI can point to our proxy with zero code changes.

**Your analogy:** FastAPI is like a Layer 7 load balancer with built-in input sanitization.

---

### LiteLLM

**What it is:** A Python library that acts as a universal adapter for 100+ AI providers.

**What it does:** You call one function (`litellm.acompletion()`), and it translates your
request into the correct format for whatever provider you're using (OpenAI, Anthropic, etc.).

**Why it matters for security:** Without LiteLLM, we'd need separate code for every AI provider.
LiteLLM also manages API keys — so provider keys live only inside our proxy, never exposed to
client applications.

**Your analogy:** LiteLLM is like a protocol translator/converter. Clients speak one protocol
(OpenAI format), LiteLLM translates to whatever the backend needs.

---

### Presidio

**What it is:** Microsoft's open-source PII (Personally Identifiable Information) detection library.

**What it does:** Analyses text and identifies personal data — email addresses, credit card numbers,
social security numbers, names, etc.

**How it works internally:** Presidio uses two approaches simultaneously:
1. **Regex patterns** — for structured data (credit cards always look like `4111 1111 1111 1111`)
2. **NLP (Natural Language Processing)** — for unstructured data like names and locations.
   This uses a trained model called `en_core_web_lg` (the spaCy model).

**Why NLP matters:** A regex can catch `john.doe@example.com` but not "my name is John Doe."
NLP understands language context, not just patterns.

**Your analogy:** Presidio is like a DLP (Data Loss Prevention) sensor that inspects payload
content — similar to what Symantec DLP or Forcepoint does, but open-source.

---

### spaCy

**What it is:** The NLP engine that Presidio uses under the hood.

**What it does:** Reads a sentence and labels each word with its meaning ("PERSON", "ORG",
"DATE", "EMAIL", etc.). This is called Named Entity Recognition (NER).

**You don't interact with spaCy directly** — Presidio calls it for you. But it's why you see
`en_core_web_lg` mentioned — that's the pre-trained English language model spaCy uses.

---

### Pydantic

**What it is:** A Python data validation library. Every "model" in the code uses it.

**What it does:** Defines the exact shape that data must have. If a request doesn't match,
it's automatically rejected with a clear error message.

**Example from our code:**
```python
class ChatCompletionRequest(BaseModel):
    model: str           # must be a string, required
    messages: List[Message]  # must be a list of Message objects
    temperature: Optional[float] = None  # optional, float or absent
```

If someone sends `{"model": 123}` (number instead of string), Pydantic rejects it before
your function even runs.

**Your analogy:** Like an input validation rule in a Web Application Firewall (WAF).

---

### httpx

**What it is:** An async-capable HTTP client library.

**What it does:** Makes outbound HTTP requests (from the proxy to Nexus, for example).

**Why httpx (not requests):** The standard `requests` library is synchronous — it blocks while
waiting for a response. `httpx` is async — while waiting for Nexus to respond, our proxy can
handle other requests. Critical for performance.

**Your analogy:** Like the difference between a blocking socket call and an epoll/select
non-blocking socket in C networking.

---

### YAML

**What it is:** A human-readable configuration file format (`.yaml` or `.yml` files).

**What it does:** Stores configuration that humans need to edit (like our API key registry).

**Why YAML (not JSON, not .env):** JSON doesn't support comments. `.env` files are flat
key-value pairs — can't represent a list of key objects. YAML is structured and readable.

---

### Docker

**What it is:** A containerisation platform — packages the app and all its dependencies
into a portable, isolated image.

**Why it matters for security:**
- Runs as a **non-root user** (uid 1001) — if the container is compromised, the attacker
  has no root privileges
- **Read-only filesystem** — the container can't write files except to the `/app/logs` volume
- **No new privileges** — prevents privilege escalation inside the container
- Reproducible builds — same image runs identically in dev, staging, and production

**Your analogy:** Like a chroot jail or a network namespace, but more comprehensive.

---

## 3. Project Structure

```
LLM-proxy/
│
├── src/                        ← All application source code
│   ├── proxy/                  ← Core proxy (entry point, auth, rate limiting)
│   │   ├── main.py             ← THE central file — request pipeline lives here
│   │   ├── models.py           ← Data shapes (what a request/response looks like)
│   │   ├── logging.py          ← Structured JSON logger
│   │   ├── auth.py             ← API key validation
│   │   └── rate_limiter.py     ← Token bucket rate limiter
│   │
│   ├── input_policy/           ← Everything that checks the PROMPT (before LLM)
│   │   ├── engine.py           ← Orchestrator — runs all input checks
│   │   ├── patterns.py         ← Custom regex patterns for secrets/credentials
│   │   └── injection.py        ← Prompt injection detection patterns
│   │
│   ├── output_security/        ← Everything that checks the RESPONSE (after LLM)
│   │   ├── engine.py           ← Orchestrator — runs all output checks
│   │   ├── code_parser.py      ← Extracts code blocks and dependency names
│   │   └── nexus.py            ← Nexus Firewall client + circuit breaker
│   │
│   └── audit/
│       └── logger.py           ← Writes audit events to logs/audit.jsonl
│
├── config/
│   ├── settings.py             ← Loads env vars (API keys, paths, URLs)
│   └── api_keys.yaml           ← API key registry (which apps can use the proxy)
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
│   ├── Dockerfile              ← Container build instructions
│   └── docker-compose.yml      ← Local dev orchestration
│
├── logs/                       ← Runtime audit logs (git-ignored)
├── .env.example                ← Template for secrets (never commit .env)
├── .gitignore                  ← Files git should never track
├── .dockerignore               ← Files that should never go into the Docker image
├── requirements.txt            ← Python dependency list
├── Context.md                  ← Original architecture specification
└── tasks/
    ├── todo.md                 ← Implementation plan (all phases)
    └── lessons.md              ← Session lessons learned
```

---

## 4. The Request Lifecycle

This is the most important section. Understanding this flow means you understand the entire system.

```
Client sends POST /v1/chat/completions
            │
            ▼
┌─────────────────────────────┐
│   Middleware: attach UUID   │  ← Every request gets a unique ID for tracing
│   request_id = uuid4()      │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│   Authentication            │  ← Is the Authorization: Bearer <key> valid?
│   validate(header)          │    If NO → 401 UNAUTHORIZED + audit log
└─────────────┬───────────────┘
              │ YES
              ▼
┌─────────────────────────────┐
│   Rate Limiting             │  ← Has this app sent too many requests?
│   is_allowed(app_id)        │    If NO → 429 RATE_LIMITED + audit log
└─────────────┬───────────────┘
              │ YES
              ▼
┌─────────────────────────────┐
│   Streaming Guard           │  ← Did they set stream=true? Block it.
└─────────────┬───────────────┘
              │ NO STREAM
              ▼
┌─────────────────────────────┐
│   Input Policy Engine       │  ← Analyse the prompt
│   1. Secrets/credentials    │    If ANY violation found:
│   2. Prompt injection       │    → 400 BLOCKED_* + audit log
│   3. PII (Presidio)         │    LLM is NEVER called
└─────────────┬───────────────┘
              │ CLEAN
              ▼
┌─────────────────────────────┐
│   LiteLLM → LLM Provider   │  ← Forward to OpenAI/Anthropic (60s timeout)
│   acompletion(model, msgs)  │    If timeout → 504 LLM_TIMEOUT
│                             │    If error   → 502 LLM_ERROR
└─────────────┬───────────────┘
              │ RESPONSE
              ▼
┌─────────────────────────────┐
│   Output Security Engine    │  ← Analyse the response
│   1. Find code blocks       │    If unsafe dep found:
│   2. Extract dependencies   │    → 400 BLOCKED_UNVALIDATED_DEP
│   3. Validate vs Nexus      │    If Nexus unreachable:
│      (10s timeout)          │    → 400 NEXUS_UNAVAILABLE (fail-closed)
└─────────────┬───────────────┘
              │ SAFE
              ▼
┌─────────────────────────────┐
│   Audit Log + Response      │  ← Write ALLOWED event, return response to client
└─────────────────────────────┘
```

**Key insight:** Every exit point — whether it's a block or an allow — writes an audit event.
You can always answer "what happened to request X?" by searching `logs/audit.jsonl`.

---

## 5. File-by-File Breakdown

### `src/proxy/main.py` — The Central Nervous System

This is the most important file. It defines the request pipeline.

**Key concepts you'll see:**

```python
@app.middleware("http")
async def attach_request_id(request: Request, call_next):
```
- `@app.middleware("http")` — This function runs for EVERY request before any endpoint
  function. Think of it like a network pre-processing hook.
- `async def` — This function is asynchronous (non-blocking). When it waits, other
  requests can be processed.
- `call_next` — "Pass control to the next handler in the chain." Like `next()` in
  middleware chains or `pass` in a firewall rule.

```python
@app.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
```
- `@app.post(...)` — This function handles HTTP POST requests to that URL.
- `body: ChatCompletionRequest` — FastAPI automatically parses and validates the JSON body
  against the `ChatCompletionRequest` Pydantic model before this function runs.

```python
await asyncio.wait_for(
    litellm.acompletion(...),
    timeout=LLM_TIMEOUT_S,
)
```
- `await` — "Wait for this async operation to finish, but let other tasks run while waiting."
- `asyncio.wait_for(..., timeout=60)` — If the operation takes longer than 60 seconds,
  raise a `TimeoutError` instead of waiting forever.

---

### `src/proxy/auth.py` — API Key Gate

**How it works:**

1. At startup, reads `config/api_keys.yaml` and loads all enabled keys.
2. For each key, computes SHA-256 hash and stores ONLY the hash in memory.
3. When a request arrives, hashes the provided key and looks up the hash.

```python
def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
```

**Why store hashes and not the raw key?**
If an attacker dumps the process memory or crashes the app in a way that exposes variables,
they'd see hashes — not usable keys. This is the same principle as password storage.

**Why not just compare strings directly?**
String comparison in Python (`==`) can leak timing information — if the strings match early
characters, it returns True faster. Hash comparison is always constant-length.

---

### `src/proxy/rate_limiter.py` — Token Bucket

**The algorithm:**

Imagine a bucket that holds 60 tokens. Every request consumes 1 token.
Tokens refill at 1 per second (= 60/minute sustained rate).
If the bucket is empty: request is denied.

```
Bucket state:  [████████████████████████] 60 tokens
Request 1:     [███████████████████████ ] 59 tokens  ✓
Request 2:     [██████████████████████  ] 58 tokens  ✓
...
Request 60:    [                        ]  0 tokens  ✓
Request 61:    [                        ]  0 tokens  ✗ → 429
(1 second later) [█                    ]  1 token
Request 62:    [                        ]  0 tokens  ✓
```

**Why per `app_id` (not per IP)?**
Behind a corporate proxy or NAT, many users share the same IP. Rate limiting by IP would
punish all users when one app misbehaves. `app_id` is per application, so one misbehaving
app doesn't affect others.

---

### `src/input_policy/engine.py` — Prompt Inspector

**Check order matters:**

```python
# 1. Secrets (fast regex — runs first)
secrets = find_secrets(text)
if secrets: return block("BLOCKED_CREDENTIALS")

# 2. Injection (fast regex)
injections = find_injections(text)
if injections: return block("BLOCKED_INJECTION")

# 3. PII via Presidio (slow NLP — runs last)
results = analyzer.analyze(text=text, ...)
if results: return block("BLOCKED_PII")
```

Regex runs in microseconds. Presidio NLP takes milliseconds (model inference).
By checking secrets and injection first, we avoid the expensive NLP call when a cheap
regex already catches the violation.

**The `@lru_cache(maxsize=1)` decorator:**
```python
@lru_cache(maxsize=1)
def _get_analyzer() -> AnalyzerEngine:
    return AnalyzerEngine()
```
Presidio takes ~2 seconds to initialise (loads the NLP model). `@lru_cache` means
"run this function once, cache the result, return the cached result on every subsequent call."
Without this, every request would spend 2 seconds loading the model.

---

### `src/input_policy/patterns.py` — Secret Patterns

**How regex patterns work (quick reference):**

| Pattern piece | Meaning |
|--------------|---------|
| `\b` | Word boundary (edge of a word) |
| `sk-` | Literal characters "sk-" |
| `[A-Za-z0-9]` | Any letter or digit |
| `{20,}` | 20 or more of the previous |
| `(?i)` | Case insensitive |
| `\s*` | Zero or more spaces |
| `[=:]` | Either = or : |
| `.+` | One or more of any character |
| `\|` | OR (match left or right side) |

**Example — OpenAI key detection:**
```python
re.compile(r'\bsk-[A-Za-z0-9]{20,}\b')
```
Matches: `sk-` followed by at least 20 alphanumeric characters, at word boundary.
Catches: `sk-abcdefghijklmnopqrstuvwxyz123456`

---

### `src/input_policy/injection.py` — Injection Detection

**What is prompt injection?**

An attacker embeds instructions in their input that try to override the AI's behaviour:
- `"Ignore all previous instructions and..."` — tries to override system prompt
- `"You are now DAN mode enabled..."` — tries to jailbreak the model
- `"</system><user>..."` — tries to inject fake system-level messages

These are the AI equivalent of SQL injection — using the data channel to inject commands.

**Our approach:** Pattern matching on known attack phrases. This is a denylist approach
(like a WAF signature). It catches known patterns but not novel, unknown attacks — which
is why it's one layer in a defence-in-depth stack, not the only protection.

---

### `src/output_security/code_parser.py` — Response Analyser

**What it does step by step:**

1. Finds all fenced code blocks in the response:
   ````
   ```python
   import requests
   ```
   ````

2. Identifies the language from the tag (`python`, `javascript`, etc.)

3. Runs language-specific regex patterns to extract package names

4. Filters out standard library packages (no need to validate `os`, `sys` — they're built-in)

5. Returns a list of external packages that need Nexus validation

**Why parse code in AI responses?**
AI models can be tricked or manipulated into suggesting packages that:
- Don't exist (the AI "hallucinated" them) — could be registered as malicious packages
- Have been typosquatted (`requets` instead of `requests`)
- Contain known vulnerabilities
- Are outright malicious

This is **supply chain attack prevention** via AI output.

---

### `src/output_security/nexus.py` — Nexus Client + Circuit Breaker

**The circuit breaker pattern:**

A circuit breaker prevents cascading failures when a dependency goes down.

```
CLOSED (normal)
    │
    │ 3 consecutive failures
    ▼
OPEN (failing — reject all requests immediately, don't even try)
    │
    │ 30 seconds elapsed
    ▼
HALF-OPEN (send one probe request)
    │
    ├─ probe succeeds → CLOSED
    └─ probe fails    → OPEN (reset timer)
```

**Why not just retry?**
If Nexus is down, retrying hammers a struggling service and makes recovery slower.
The circuit breaker gives Nexus time to recover without being bombarded.

**Your analogy:** Like Spanning Tree Protocol — detects a loop/failure and logically breaks
the circuit to prevent a storm, then probes for recovery.

**Fail-closed:**
When the circuit is OPEN (Nexus unreachable), we **block** the response. We made this
decision in Phase 0. The alternative (fail-open) would mean unvalidated code reaches users
whenever Nexus is slow — unacceptable for a security control.

---

### `src/audit/logger.py` — Audit Trail

**The audit log schema:**
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
Two reasons:
1. **Privacy** — Prompts may contain sensitive business information. Storing them in logs
   creates another attack surface.
2. **GDPR/Compliance** — In Europe, storing personal data requires justification and controls.
   A hash satisfies auditability (same prompt = same hash, you can correlate) without storing the data.

**JSONL format (one JSON object per line):**
Each line is valid JSON. You can grep it, pipe it to `jq`, feed it to Splunk/ELK.
Unlike a single large JSON array, JSONL can be appended to without rewriting the whole file.

**How to query the audit log:**
```bash
# Show all blocked requests
grep '"action":"BLOCKED"' logs/audit.jsonl | jq .

# Show all requests from a specific app
grep '"app_id":"local-dev"' logs/audit.jsonl | jq .

# Count blocks by type
jq -r '.block_code' logs/audit.jsonl | sort | uniq -c
```

---

### `config/settings.py` — Environment Variable Loader

```python
class Settings:
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
```

`os.environ.get("KEY", "")` — read the environment variable named "KEY". If it doesn't
exist, return empty string as default.

**Why env vars and not a config file?**
- Config files get committed to git accidentally → credential leak
- Env vars are injected at runtime by the deployment platform
- Different environments (dev/staging/prod) can have different values without code changes
- This is the [12-Factor App](https://12factor.net/config) principle, widely used in industry

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
1. Generate a random key (e.g. `openssl rand -hex 32`)
2. Add an entry here with `enabled: true`
3. Restart the proxy (it loads keys at startup)
4. Give the key to the application team securely (not by email!)

**To revoke access:**
Set `enabled: false` and restart. The key is rejected but the entry stays for audit purposes.

---

### `docker/Dockerfile` — Container Build

```dockerfile
FROM python:3.12-slim AS builder     # Stage 1: install everything
...
FROM python:3.12-slim AS runtime     # Stage 2: copy only what's needed
```

**Multi-stage build:** The builder stage has compilers, build tools, pip. The runtime stage
has only the final installed packages. This means the final image is smaller and has fewer
attack surface components.

```dockerfile
RUN groupadd --gid 1001 proxy \
 && useradd --uid 1001 --gid proxy --no-create-home --shell /sbin/nologin proxy
USER proxy
```
Creates and switches to a non-root user. If the app is exploited, the attacker has
the same limited permissions as this user — not root.

---

## 6. Security Decisions Explained

### Why block instead of redact?

We block requests containing PII or credentials rather than removing/masking the sensitive parts
and forwarding a sanitised version. Reason: redaction is hard to get right. A redaction system
that misses one pattern sends real data to the LLM. For v1, blocking is safer. Redaction is
listed as a future enhancement.

### Why fail-closed on Nexus?

If the dependency validation service is unreachable, we **reject** responses containing code.
The alternative (fail-open: allow unvalidated code) would mean a Nexus outage silently
disables a security control. Operators would never know. Fail-closed is loud — users notice,
operators get alerted, and the security posture is never silently degraded.

### Why hash prompts in the audit log?

A SHA-256 hash is a one-way function — you cannot recover the original text from the hash.
However, the same input always produces the same hash. This means:
- You can tell if the same prompt was sent twice (correlation)
- You can ask a user "was this the prompt you sent?" and verify against the hash
- But you cannot read stored prompts — privacy is preserved by design

### Why token bucket over fixed window rate limiting?

Fixed window: "allow 60 requests per minute" — at 12:00:59 you send 60, at 12:01:00 you send
60 more. That's 120 requests in 2 seconds, defeating the limit.

Token bucket: tokens refill continuously. Burst is allowed (up to the bucket capacity) but
the sustained rate is strictly controlled regardless of timing tricks.

---

## 7. How to Read Python

Quick reference for the Python patterns you'll see most often.

### Imports
```python
from fastapi import FastAPI, Request    # "from library import thing"
import litellm                          # "import whole library"
```

### Type hints (after the colon)
```python
def validate(authorization_header: Optional[str]) -> Optional[ApiKeyEntry]:
#                                   ^type of input    ^type of output
```
These are documentation hints — Python doesn't enforce them at runtime, but they tell you
what a function expects and returns.

### Dataclasses
```python
@dataclass
class PolicyResult:
    allowed: bool
    block_code: str = ""
```
A dataclass is a simple container for related data. `@dataclass` auto-generates `__init__`
so you can do `PolicyResult(allowed=True)`. The `= ""` means default value if not provided.

### `async` / `await`
```python
async def chat_completions(...):
    response = await litellm.acompletion(...)
```
`async def` = "this function might need to wait for things."
`await` = "wait for this, but let other tasks run while I wait."
Without `await`, you'd freeze the server while waiting for the LLM response.

### Decorators (`@`)
```python
@app.post("/v1/chat/completions")
def chat_completions(...):
```
`@` means "wrap this function with that decorator." Here, it registers the function
as the handler for `POST /v1/chat/completions`. Decorators modify or register functions.

### `Optional[str]`
```python
from typing import Optional
def foo(x: Optional[str]) -> None:
```
`Optional[str]` = "this can be a string OR None (absent)."

### List comprehension
```python
messages_raw = [m.model_dump() for m in body.messages]
# Same as:
messages_raw = []
for m in body.messages:
    messages_raw.append(m.model_dump())
```

### `f-strings`
```python
url = f"{base}/service/rest/v1/search?name={package}"
# Embeds variables directly into strings using curly braces
```

---

## 8. Concepts You Should Know

### REST API
Our proxy exposes a REST API — HTTP-based, uses JSON for data, stateless (each request
is self-contained). The key endpoint is `POST /v1/chat/completions`.

### HTTP status codes used in this project

| Code | Name | When we use it |
|------|------|---------------|
| 200 | OK | Request allowed, response returned |
| 400 | Bad Request | Blocked by policy (PII, injection, unsafe code) |
| 401 | Unauthorized | Missing or invalid API key |
| 429 | Too Many Requests | Rate limit exceeded |
| 400 | Bad Request | Streaming rejected |
| 502 | Bad Gateway | LLM provider returned an error |
| 503 | Service Unavailable | Proxy not ready (/ready endpoint) |
| 504 | Gateway Timeout | LLM provider didn't respond in 60s |

### Unit test vs Integration test vs E2E test

| Type | What it tests | External calls |
|------|--------------|---------------|
| Unit | One function in isolation | None (mocked) |
| Integration | Multiple components together | None (mocked) |
| E2E (end-to-end) | Full request pipeline | None (all mocked) |

In our project, the LLM and Nexus are always mocked in tests — we test the logic, not
the external services. This means tests run fast and don't need real API keys.

### Mocking
```python
with patch("src.proxy.main.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
    mock_llm.return_value = FAKE_RESPONSE
```
`patch` replaces `litellm.acompletion` with a fake version for the duration of the `with` block.
The fake always returns `FAKE_RESPONSE`. After the `with` block, the real function is restored.

### Virtual environment (`.venv/`)
Python projects use virtual environments to isolate dependencies. Instead of installing
packages system-wide (which causes conflicts), they're installed in `.venv/`.
**Always use `.venv/bin/python` and `.venv/bin/pytest`, not the system `python3`.**

---

## 9. Cheat Sheet

### Running the tests
```bash
# All tests
.venv/bin/python -m pytest tests/ -v

# One specific file
.venv/bin/python -m pytest tests/unit/test_auth.py -v

# One specific test
.venv/bin/python -m pytest tests/unit/test_auth.py::TestValidate::test_valid_key_returns_entry -v
```

### Starting the server locally
```bash
.venv/bin/uvicorn src.proxy.main:app --port 8080 --reload
# --reload: auto-restarts when you save a file (dev only)
```

### Sending a test request
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-1234" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Reading the audit log
```bash
tail -f logs/audit.jsonl | python3 -m json.tool
# Or with jq installed:
tail -f logs/audit.jsonl | jq .
```

### Adding a new API key
1. Open `config/api_keys.yaml`
2. Add entry under `keys:`
3. Restart the server

### Tracing a request by ID
Every response includes `X-Request-Id` header. Use it to find the audit event:
```bash
grep "REQUEST_ID_HERE" logs/audit.jsonl | jq .
```

### Where to look when something is blocked

| Symptom | File to look at | What to check |
|---------|----------------|---------------|
| 401 | `src/proxy/auth.py` | Is the key in api_keys.yaml? Is enabled: true? |
| 429 | `src/proxy/rate_limiter.py` | MAX_TOKENS, REFILL_RATE constants |
| BLOCKED_PII | `src/input_policy/engine.py` | PII_ENTITIES list, PRESIDIO_SCORE_THRESHOLD |
| BLOCKED_CREDENTIALS | `src/input_policy/patterns.py` | SECRET_PATTERNS list |
| BLOCKED_INJECTION | `src/input_policy/injection.py` | INJECTION_PATTERNS list |
| BLOCKED_UNVALIDATED_DEP | `src/output_security/nexus.py` | NEXUS_BASE_URL in .env |
| NEXUS_UNAVAILABLE | `src/output_security/nexus.py` | FAILURE_THRESHOLD, RECOVERY_TIMEOUT |
| 504 LLM_TIMEOUT | `src/proxy/main.py` | LLM_TIMEOUT_S constant |

---

## Final Note

The best way to understand this project deeply is to **trace one request manually**:

1. Open `src/proxy/main.py`
2. Start at line 1 of `chat_completions()`
3. Follow every function call into its file
4. Check what it returns
5. Come back to `main.py` and see what happens next

You will touch every file in the project by the end of one trace. That's the fastest way
to build a mental model of how everything connects.

Good luck with the internship. This is real enterprise security engineering.
