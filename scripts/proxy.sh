#!/usr/bin/env bash
set -e

# Activate virtual environment
source "$(dirname "$0")/../.venv/bin/activate"

# Create logs directory if not exists
mkdir -p "$(dirname "$0")/../logs"

# Start proxy server in background
nohup uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080 --reload > "$(dirname "$0")/../logs/proxy.log" 2>&1 &
PROXY_PID=$!

# Start API server in background
nohup uvicorn src.webui_api.main:app --host 0.0.0.0 --port 8000 --reload > "$(dirname "$0")/../logs/api.log" 2>&1 &
API_PID=$!

echo "✅ Proxy and API servers started. Open a new terminal and run:"
echo "   cd src/webui-react && npm start"

# Trap to clean up background jobs on script exit
cleanup() {
    echo "Shutting down background processes..."
    kill $PROXY_PID $API_PID 2>/dev/null || true
    wait $PROXY_PID $API_PID 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT

exit 0