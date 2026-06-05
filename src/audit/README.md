# Audit Subsystem — a Proxy-Level Capability

**This is part of the proxy product, not the demo UI.**

Auditing is intrinsic to the proxy. Every request that passes through the
security proxy is tracked — regardless of which client sent it (a browser, curl,
Claude Code, a CI pipeline, another chatbot, any integration). Delete the entire
web interface and this still works for every other client.

## What is tracked

`logger.py::emit()` is called on **every** request, on **both** proxy endpoints:

- `POST /v1/chat/completions` (OpenAI-compatible)
- `POST /v1/messages` (Anthropic-compatible)

Each event records: timestamp, request_id, app_id, action (ALLOWED / BLOCKED /
ERROR), block_code, model, prompt hash, latency, findings (PII/secret *types*),
and redaction metadata. Raw prompts and raw API keys are **never** stored.

## Where it goes

Two sinks, both written from the proxy:

1. **`logs/audit.jsonl`** — append-only JSONL (privacy-default, always on).
2. **Postgres** — best-effort structured sink for querying/visualisation.

## How it is queried

The proxy serves its own dashboard API (`src/proxy/audit_api.py`):

- `GET /v1/audit/stats` — aggregated metrics
- `GET /v1/audit/logs`  — paginated, filterable entries

Authorised by the proxy's own API-key registry (`config/api_keys.yaml`). Any
client can consume these — the React dashboard is just **one** renderer.

## Identity attribution

- **Always:** by API key → `app_id`. Tracked for every client, no exceptions.
- **Optional enrichment:** a client may pass `X-User-Identity` (JSON with
  sub/name/role) to attribute events to an end-user. The demo UI does this; other
  integrations may or may not. The proxy records it when present.

## The product / demo boundary

```
PROXY (the product)                         DEMO (one client)
├── security pipeline                        ├── chat interface  ("Demo Client")
├── audit tracking + storage   ──────────►   └── renders the proxy's audit API
└── audit query API /v1/audit/*                  ("Proxy Admin Console")
```

The dashboard ships with the proxy. The UI merely visualises data the proxy
already owns and serves.
