#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."

pkill -f "uvicorn src.proxy.main" 2>/dev/null && echo "🔒 Proxy stopped" || echo "Proxy was not running"
pkill -f "uvicorn src.webui_api.main" 2>/dev/null && echo "🌐 API stopped"  || echo "API was not running"

rm -f "$ROOT/logs/proxy.pid" "$ROOT/logs/api.pid"
