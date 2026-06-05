# Quick Start — LLM Security Proxy

## One Command

```bash
bash scripts/launch_all.sh
```

This starts everything in order:
1. **PostgreSQL** (Postgres:5433) — audit data persistence
2. **LLM Security Proxy** (port 8080) — the product
3. **WebUI API** (port 8000) — demo gateway

Then open your browser.

---

## Access Points

### 📊 Admin Console (Port 8080)
**For security teams to monitor proxy traffic.**

- **URL:** http://localhost:8080/admin
- **Login:** `admin` / `admin` (or `user` / `user` for read-only view)
- **Shows:**
  - Security Overview (charts, metrics, block reasons)
  - Audit Log (paginated, filterable request history)
  - Real-time auto-refresh (5-second polling)

### 💬 Demo Chat UI (Port 8000)
**To test the proxy with a sample chat interface.**

- **URL:** http://localhost:8000
- **Login:** `admin` / `admin` (or `user` / `user`)
- **Shows:**
  - Chat interface (sends requests through the proxy)
  - Dashboard (basic metrics)
  - **No admin pages** — security console is only on port 8080

### 🔌 Raw API (Port 8080)
**For automation, CI/CD, or CLI usage.**

```bash
# Send a request
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "say hello"}]
  }'

# Query audit stats
curl -H "Authorization: Bearer dev-local-key-1234" \
  http://localhost:8080/v1/audit/stats?time_range=24h
```

---

## Architecture

```
┌─────────────────────────────┐
│ Admin Console (port 8080)   │  ← Security team panel
│ (Security Overview + Logs)  │     (proxy-served)
└──────────────┬──────────────┘
               │
               ▼
        ┌──────────────┐
        │ LLM Proxy    │  ← The product
        │ (port 8080)  │     (all security logic)
        └──────────────┘
               ▲
               │
     ┌─────────┴──────────┐
     │                    │
┌────┴─────┐      ┌──────┴────┐
│ WebUI API │      │ Raw API   │
│ (8000)    │      │ (curl etc)│
│  Demo     │      │ (Automation)
└──────────┘      └───────────┘
```

---

## Monitor Logs

```bash
# Proxy logs (security scanning, LLM calls)
tail -f /tmp/proxy.log

# WebUI API logs
tail -f /tmp/webui_api.log

# Database (Postgres in Docker)
docker compose -f docker/docker-compose.yml logs -f postgres
```

---

## Stop Everything

```bash
# Kill the services (use the PIDs printed at startup)
kill <PROXY_PID> <WEBUI_PID>

# Or stop from docker
docker compose -f docker/docker-compose.yml down
```

---

## Test Workflow

1. **Open admin console:** http://localhost:8080/admin
2. **Send a request:**
   ```bash
   curl -X POST http://localhost:8080/v1/chat/completions \
     -H "Authorization: Bearer dev-local-key-1234" \
     -H "Content-Type: application/json" \
     -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"test"}]}'
   ```
3. **Watch the dashboard update** (5-second refresh)
4. **Click into a log entry** to see full details

---

## Configuration

Key settings in `config/settings.py`:
- `STREAMING_ENABLED` — real-time response streaming
- `MALICIOUS_CODE_ENABLED`, `VULN_SCAN_ENABLED` — security phases
- `OIDC_ENABLED` — Keycloak/SSO (currently false, set to true when you have realm details)

To change, edit `.env` before running the script.

---

## Next Steps

- **Write test prompts:** See `docs/DEMO_CHAT_SCRIPT.md`
- **Set up Keycloak SSO:** See `docs/KEYCLOAK_ADMIN_SETUP.md`
- **Read the project digest:** `docs/PROJECT_DIGEST.md`
