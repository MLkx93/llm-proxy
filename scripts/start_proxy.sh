#!/bin/bash
# Start the LLM Security Proxy with all demo features enabled.
# Streaming, vulnerability scanning, and malicious-code detection are turned on
# so the live chat demo behaves correctly.
set -a
[ -f .env ] && source .env          # load OPENROUTER_API_KEY etc. from .env
set +a
export STREAMING_ENABLED=true
export VULN_SCAN_ENABLED=true
export MALICIOUS_CODE_ENABLED=true
source .venv/bin/activate
exec uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080
