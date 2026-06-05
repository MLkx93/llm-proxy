#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."

source "$ROOT/.venv/bin/activate"

mkdir -p "$ROOT/logs"

# Kill any existing instances
pkill -f "uvicorn src.proxy.main" 2>/dev/null || true
pkill -f "uvicorn src.webui_api.main" 2>/dev/null || true
sleep 1

# Start proxy server (port 8080)
nohup uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080 \
    > "$ROOT/logs/proxy.log" 2>&1 &
PROXY_PID=$!
echo "🔒 Proxy started (PID $PROXY_PID) → http://localhost:8080"

# Start API server (port 8000)
nohup uvicorn src.webui_api.main:app --host 0.0.0.0 --port 8000 \
    > "$ROOT/logs/api.log" 2>&1 &
API_PID=$!
echo "🌐 API started   (PID $API_PID) → http://localhost:8000"

# Save PIDs so they can be killed later
echo "$PROXY_PID" > "$ROOT/logs/proxy.pid"
echo "$API_PID"   > "$ROOT/logs/api.pid"

echo ""
echo "✅ Both servers running. Start the React frontend with:"
echo "   cd src/webui-react && npm start"
echo ""
echo "To stop: bash scripts/stop.sh"
