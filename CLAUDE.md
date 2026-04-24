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

## SECURITY ARCHITECTURE

The LLM-proxy implements a multi-phase security architecture for validating packages in LLM responses.

### Implemented Phases

#### Phase 1: Enhanced Vulnerability Scanning
- **Files:** `src/output_security/vulnerability_scanner.py`
- **Purpose:** Query OSV and CVE databases for known vulnerabilities
- **Key classes:** Vulnerability, VulnerabilityReport, should_block_package
- **Env vars:** VULN_SCAN_ENABLED, VULN_MIN_SEVERITY, VULN_OSV_ENABLED, VULN_CVE_ENABLED

#### Phase 2: Advanced Version Validation
- **Files:** `src/output_security/version_parser.py`, `security_advisory.py`, `version_validator.py`
- **Purpose:** Check specific versions against vulnerable ranges
- **Key classes:** Version, VersionConstraint, SecurityAdvisoryDatabase, validate_package_version
- **Env vars:** VERSION_VALIDATION_ENABLED, VERSION_ADVISORY_DB_PATH

#### Phase 3: Dependency Tree Analysis
- **Files:** `src/output_security/dependency_tree.py`, `dependency_resolver.py`
- **Purpose:** Analyze transitive dependencies for vulnerabilities
- **Key classes:** DependencyNode, DependencyTree, DependencyAnalysisResult
- **Env vars:** DEPENDENCY_SCAN_ENABLED, DEPENDENCY_MAX_DEPTH, DEPENDENCY_RISK_THRESHOLD

#### Phase 4: Code Sandbox Validation
- **Files:** `src/output_security/sandbox.py`, `detection_rules.py`, `risk_scorer.py`
- **Purpose:** Behavioral analysis with isolated code execution
- **Key classes:** SandboxRunner, BehaviorDetector, RiskScorer, RuleSet
- **Env vars:** SANDBOX_ENABLED, SANDBOX_IMAGE, SANDBOX_TIMEOUT_SECONDS, SANDBOX_RISK_THRESHOLD

### Security Module Structure (Complete)

```
src/output_security/
├── __init__.py
├── code_parser.py       # Extract dependencies from code
├── engine.py            # Main validation orchestrator
├── nexus.py             # Nexus Firewall integration
├── vulnerability_scanner.py   # Phase 1: OSV/CVE scanning
├── version_parser.py          # Phase 2: Constraint parsing
├── security_advisory.py      # Phase 2: Advisory database
├── version_validator.py      # Phase 2: Range validation
├── dependency_tree.py         # Phase 3: Tree data structures
├── dependency_resolver.py    # Phase 3: Resolver implementations
├── sandbox.py                # Phase 4: Containerized execution
├── detection_rules.py        # Phase 4: Rule engine
└── risk_scorer.py           # Phase 4: Risk calculation
```

### Security Module Structure

```
src/output_security/
├── __init__.py
├── code_parser.py       # Extract dependencies from code
├── engine.py            # Main validation orchestrator
├── nexus.py             # Nexus Firewall integration
├── vulnerability_scanner.py   # Phase 1: OSV/CVE scanning
├── version_parser.py          # Phase 2: Constraint parsing
├── security_advisory.py      # Phase 2: Advisory database
├── version_validator.py      # Phase 2: Range validation
├── dependency_tree.py         # Phase 3: Tree data structures
└── dependency_resolver.py    # Phase 3: Resolver implementations
```

### Configuration Pattern

Each security phase follows this pattern:
1. Feature-specific env vars in `config/settings.py`
2. Documented in `.env.example`
3. Environment configuration in `SETUP.md` Security Phases section
4. Unit tests in `tests/unit/test_*.py`

### Security Orchestration (Integration Phase)

The security engine (`src/output_security/engine.py`) orchestrates all phases:

**Key Classes:**
- `SecurityOrchestrator` - Main orchestrator for all security phases
- `SecurityCheckResult` - Comprehensive result with all phase details
- `PhaseResult` - Individual phase result with timing and details
- `SecurityPhase` - Enum for phase identification

**Execution Flow:**
1. Nexus validation (repository check)
2. Phase 1: Vulnerability scanning
3. Phase 2: Version validation
4. Phase 3: Dependency tree analysis
5. Phase 4: Sandbox execution

**Configuration Options:**
- `early_termination`: Stop on first blocking result
- `fail_safe`: Block if any phase fails
- Individual phase enable/disable flags

### Testing Security Features

```bash
# Run all security tests
python -m pytest tests/unit/test_vulnerability_scanner.py tests/unit/test_version_validation.py tests/unit/test_dependency_tree.py tests/unit/test_sandbox.py tests/unit/test_security_orchestrator.py -v

# Quick security check
from src.output_security.dependency_resolver import analyze_package_health
result = analyze_package_health("requests", "2.25.0", "python")

# Full security analysis
from src.output_security.engine import check_full
result = await check_full(response_text)
```
