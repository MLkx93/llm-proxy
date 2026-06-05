#!/bin/bash
# Launch script for the full LLM Security Proxy stack
# Starts: Postgres → Proxy (8080) → WebUI API (8000)

set -e

cd "$(dirname "$0")/.."

echo "🚀 Starting LLM Security Proxy..."
echo ""

# 1. Start Postgres
echo "1️⃣  Starting PostgreSQL..."
docker compose -f docker/docker-compose.yml up -d postgres
sleep 2

# 2. Start Proxy (port 8080)
echo "2️⃣  Starting LLM Security Proxy (port 8080)..."
source .venv/bin/activate
bash scripts/start_proxy.sh > /tmp/proxy.log 2>&1 &
PROXY_PID=$!
echo "   Proxy PID: $PROXY_PID"
sleep 3

# 3. Start WebUI API (port 8000)
echo "3️⃣  Starting WebUI API Server (port 8000)..."
uvicorn src.webui_api.main:app --port 8000 > /tmp/webui_api.log 2>&1 &
WEBUI_PID=$!
echo "   WebUI API PID: $WEBUI_PID"
sleep 2

echo ""
echo "✅ All services started!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Access Points:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Admin Console (Security Team)"
echo "   URL:     http://localhost:8080/admin"
echo "   Login:   admin / admin"
echo "   Shows:   Security Overview + Audit Log"
echo ""
echo "💬 Demo Chat UI"
echo "   URL:     http://localhost:8000"
echo "   Login:   admin / admin (or user / user)"
echo "   Shows:   Chat Interface + Dashboard"
echo ""
echo "🔌 Proxy API (CLI / Automation)"
echo "   URL:     http://localhost:8080/v1/chat/completions"
echo "   Header:  Authorization: Bearer dev-local-key-1234"
echo "   Audit:   http://localhost:8080/v1/audit/stats"
echo ""
echo "📝 Log Files:"
echo "   Proxy:    tail -f /tmp/proxy.log"
echo "   WebUI:    tail -f /tmp/webui_api.log"
echo ""
echo "🧪 Test Request:"
echo "   curl -X POST http://localhost:8080/v1/chat/completions \\"
echo "     -H 'Authorization: Bearer dev-local-key-1234' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"say hello\"}]}'"
echo ""
echo "⏹️  To stop:"
echo "   kill $PROXY_PID $WEBUI_PID"
echo "   docker compose -f docker/docker-compose.yml down"
echo ""
