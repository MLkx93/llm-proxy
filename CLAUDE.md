# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## SESSION START

1. Read tasks/lessons.md — apply all lessons before touching anything

2. Read tasks/todo.md — understand current state

3. If neither exists, create them before starting

 

## WORKFLOW

 

### 1. Plan First

- Enter plan mode for any non-trivial task (3+ steps)

- Write plan to tasks/todo.md before implementing

- If something goes wrong, STOP and re-plan — never push through

 

### 2. Subagent Strategy

- Use subagents to keep main context clean

- One task per subagent

- Throw more compute at hard problems

 

### 3. Self-Improvement Loop

- After any correction: update tasks/lessons.md

- Format: [date] | what went wrong | rule to prevent it

- Review lessons at every session start

 

### 4. Verification Standard

- Never mark complete without proving it works

- Run tests, check logs, diff behavior

- Ask: "Would a staff engineer approve this?"

 

### 5. Demand Elegance

- For non-trivial changes: is there a more elegant solution?

- If a fix feels hacky: rebuild it properly

- Don't over-engineer simple things

 

### 6. Autonomous Bug Fixing

- When given a bug: just fix it

- Go to logs, find root cause, resolve it

- No hand-holding needed

 

## CORE PRINCIPLES

- Simplicity First — touch minimal code

- No Laziness — root causes only, no temp fixes

- Never Assume — verify paths, APIs, variables before using

- Ask Once — one question upfront if unclear, never interrupt mid-task

 

## TASK MANAGEMENT

1. Plan → tasks/todo.md

2. Verify → confirm before implementing

3. Track → mark complete as you go

4. Explain → high-level summary each step

5. Learn → tasks/lessons.md after corrections

 

## LEARNED

(Claude fills this in over time)

---

## COMMON DEVELOPMENT COMMANDS

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy from .env.example)
export $(grep -v '^#' .env | xargs)
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run security modules tests
pytest tests/unit/test_vulnerability_scanner.py tests/unit/test_version_validation.py tests/unit/test_dependency_tree.py tests/unit/test_sandbox.py tests/unit/test_security_orchestrator.py -v

# Run specific test file
pytest tests/unit/test_input_policy.py -v

# Run with coverage
pytest tests/ --cov=src/ --cov-report=html

# Run specific test function
pytest tests/unit/test_input_policy.py::test_secret_detection -v
```

### Development Servers
```bash
# Start proxy server
uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080 --reload

# Start webui API server
uvicorn src.webui_api.main:app --host 0.0.0.0 --port 8000 --reload

# Start React frontend (separate terminal)
cd src/webui-react
npm start

# Complete development setup (3 terminals needed)
# Terminal 1: Proxy
uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080 --reload
# Terminal 2: Webui API
uvicorn src.webui_api.main:app --host 0.0.0.0 --port 8000 --reload  
# Terminal 3: React
cd src/webui-react && npm start
```

### Production Build
```bash
# Build React frontend
cd src/webui-react
npm run build

# Start production API server (serves static files)
uvicorn src.webui_api.main:app --host 0.0.0.0 --port 8000

# Docker build and run
docker build -f docker/Dockerfile -t llm-proxy .
docker run -p 8080:8080 --env-file .env -v $(pwd)/logs:/app/logs llm-proxy

# Docker Compose
docker-compose -f docker/docker-compose.yml up
```

### Code Quality
```bash
# Format code
black src/

# Lint code
flake8 src/

# Type check
mypy src/
```

---

## ARCHITECTURE OVERVIEW

### System Architecture
```
Client Applications
       ↓
┌─────────────────────────────┐
│   Web UI (React)           │  → port 3000 (dev) / 8000 (prod)
├─────────────────────────────┤
│   API Server (FastAPI)     │  → port 8000  
├─────────────────────────────┤
│ LLM Security Proxy         │  → port 8080
│   • Input Policy Engine     │
│   • Output Security Engine  │
│   • Rate Limiting          │
│   • Authentication         │
├─────────────────────────────┤
│   LiteLLM / OpenRouter    │
├─────────────────────────────┤
│  LLM Providers (OpenAI,    │
│       Anthropic, etc.)     │
```

### Proxy Components
The proxy serves dual endpoints:
1. **OpenAI-compatible** (`/v1/chat/completions`) - Standard OpenAI format
2. **Anthropic-compatible** (`/v1/messages`) - Translates Anthropic ↔ OpenAI format

Both endpoints follow the same security pipeline:
1. Authentication & Rate Limiting
2. Input Policy Engine (PII/Injection/Secret detection)
3. LLM call (via LiteLLM or OpenRouter)
4. Output Security Engine (Dependency validation)
5. Response Audit Logging

### Security Pipeline (Multi-Phase Architecture)

#### Phase 1: Input Policy Engine
- **File:** `src/input_policy/engine.py`
- **Purpose:** Scans input prompts for violations
- **Checks:** PII, prompt injection, secrets/credentials
- **Tech:** Presidio analyzer, custom regex patterns
- **Notable:** Strips XML tool tags to avoid false positives

#### Phase 2: Output Security Engine  
- **File:** `src/output_security/engine.py`
- **Purpose:** Validates LLM output for security risks
- **Core Focus:** Code dependency validation via Nexus
- **Architecture:** Multi-phase security pipeline with optional phases

### Output Security Phases (Configurable)

#### Phase 1: Enhanced Vulnerability Scanning
- **Files:** `src/output_security/vulnerability_scanner.py`
- **Purpose:** OSV/CVE database queries
- **Env vars:** `VULN_SCAN_ENABLED`, `VULN_MIN_SEVERITY`

#### Phase 2: Advanced Version Validation
- **Files:** `src/output_security/version_parser.py`, `version_validator.py`
- **Purpose:** Version-range validation against known vulnerabilities
- **Tech:** Semantic version parsing, SQLite advisory database

#### Phase 3: Dependency Tree Analysis
- **Files:** `src/output_security/dependency_resolver.py`
- **Purpose:** Transitive dependency scanning
- **Key:** Recursive dependency graph analysis

#### Phase 4: Code Sandbox Validation
- **Files:** `src/output_security/sandbox.py`
- **Purpose:** Behavioral analysis via containerized execution
- **Key:** Docker execution with resource limits

### Main Orchestration
- **SecurityOrchestrator:** Coordinates all output security phases
- **Configuration:** Phases can be enabled/disabled via env vars
- **Execution:** Configurable early termination or comprehensive analysis

### Provider Integration
#### OpenRouter (Primary)
- Direct API calls to OpenRouter
- Model name transformation (Claude Code format → OpenRouter format)
- Rate limiting handled by OpenRouter

#### LiteLLM (Legacy)
- Pass-through mode to existing LiteLLM servers
- Authentication delegation to upstream
- Maintained for backward compatibility

### Frontend Components
1. **React UI** (`src/webui-react/`)
   - Model testing interface
   - Dashboard with security metrics
   
2. **API Backend** (`src/webui_api/`)
   - FastAPI server serving React build + REST endpoints
   
3. **Simple Web UI** (`src/webui/`)
   - Jinja2 template interface for basic testing

---

## KEY CONFIGURATION

### Environment Variables
Key variables in `.env`:
- `OPENROUTER_API_KEY` - OpenRouter authentication
- `LITELLM_API_BASE` - LiteLLM server URL (if used)
- `NEXUS_BASE_URL` - Repository firewall integration
- Security phase flags (`VULN_SCAN_ENABLED`, etc.)

### Python Virtual Environment
- Located at `.venv/`
- Created with system Python (venv is externally managed)
- All dependencies installed here

### Model Naming
- Claude Code uses format: `claude-3.5-sonnet-20241022`
- Proxy transforms to: `anthropic/claude-3.5-sonnet`

### Configuration Files
- `config/settings.py` - Application configuration
- `.env.example` - Template environment variables
- `requirements.txt` - Python dependencies

---

## DATA FLOW EXAMPLES

### Normal Request Flow
1. Client sends request to proxy
2. Proxy validates API key and rate limits
3. Input policy scans for PII/injection
4. Translated request sent to LLM provider
5. Response validated for security risks
6. Clean response returned to client

### Anthropic ↔ OpenAI Translation
```python
# Anthropic input → OpenAI
messages = convert_anthropic_to_openai(anthropic_body)
openai_response = call_llm(messages)
anthropic_response = convert_openai_to_anthropic(openai_response)
```

### Security Pipeline Execution
```python
# Output security check
output_policy = await output_security.check(response_text)
if not output_policy.allowed:
    block_with_reason(output_policy.block_code)
```

---

## TESTING STRATEGY

### Unit Tests
- Coverage for all core components
- Mock external services (Nexus, OSV, etc.)
- Test edge cases and error conditions

### Integration Tests
- E2E testing with real LLM calls
- Proxy integration with OpenRouter/LiteLLM
- Security pipeline validation

### Security Testing
- Mock vulnerability data for safe testing
- Validate policy enforcement
- Test both blocking and whitelisting behavior

---

## DEPLOYMENT NOTES

### Docker Security
- Multi-stage build for small final image
- Non-root user (`proxy:proxy`)
- Read-only filesystem except `/logs`
- Health checks included

### Production Considerations
- Audit log volume mount required
- Environment variables must be set
- HTTPS recommended for production
- Resource limits configurable via docker-compose