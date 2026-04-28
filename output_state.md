# Output Security Layer — Deep Dive

## 1 Security Pipeline

```
Code Block Detected
        │
        ▼
┌───────────────────┐
│ Phase 0: Nexus    │──── Package in approved repo? ──── No ──→ BLOCK
└───────┬───────────┘                                    (BLOCKED_UNVALIDATED_DEP)
        │ Yes
        ▼
┌───────────────────┐
│ Phase 1: Vuln     │──── Known vulnerabilities? ──── Yes (≥threshold) ──→ BLOCK
│ Scan (OSV/CVE)    │                                    (BLOCKED_VULNERABLE_PACKAGE)
└───────┬───────────┘
        │ Clean
        ▼
┌───────────────────┐
│ Phase 2: Version  │──── Specific version vulnerable? ──── Yes ──→ BLOCK
│ Validation        │                                    (BLOCKED_VULNERABLE_VERSION)
└───────┬───────────┘
        │ Clean
        ▼
┌───────────────────┐
│ Phase 3: Dep Tree │──── Transitive deps vulnerable? ──── Yes (grade D/F) ──→ BLOCK
│ Analysis          │                                    (BLOCKED_DEPENDENCY_VULNERABILITY)
└───────┬───────────┘
        │ Clean
        ▼
┌───────────────────┐
│ Phase 4: Sandbox  │──── High-risk behavior? ──── Yes ──→ BLOCK
│ + Risk Scoring     │                                    (BLOCKED_SANDBOX)
└───────┬───────────┘
        │ Clean
        ▼
      ALLOW
```

## 2 Phase Details

#### Phase 0: Nexus Validation
- **Purpose:** Verify package exists in enterprise Nexus repository
- **Implementation:** HTTP call to Nexus REST API v1
- **Circuit Breaker:** 3 failures → open for 30s, then half-open probe
- **Fail-safe:** Nexus unreachable → BLOCK (fail-closed)
- **Repo mapping:** python→pypi-proxy, javascript→npm-proxy, java→maven-central-proxy, ruby→rubygems-proxy, go→go-proxy

#### Phase 1: Vulnerability Scanning
- **Sources:** OSV (Google) + NVD/CVE (MITRE), optional Snyk
- **Concurrent:** OSV + CVE queries run in parallel via `asyncio.gather`
- **Caching:** In-memory cache with 3600s TTL (version-agnostic queries only)
- **Circuit Breaker:** Separate circuit breaker for vuln scanning services
- **Blocking threshold:** Configurable via `VULN_MIN_SEVERITY` (default: HIGH)
- **CVSS scoring:** CRITICAL ≥9.0, HIGH ≥7.0, MEDIUM ≥4.0, LOW ≥0.1

#### Phase 2: Version Validation
- **Database:** SQLite (`security_advisories.db`)
- **Version matching:** Custom semver parser supporting npm (^, ~), PyPI (>=, ==, !=), Maven ([1.0,2.0)), Go (v1.0.0)
- **Sample data:** 6 pre-loaded advisories (Log4Shell, OpenSSL, Django, Lodash, Requests, Moment.js)
- **⚠️ Bug:** `validate_package_version()` in `engine.py` is called with 4 args but only accepts 3

#### Phase 3: Dependency Tree Analysis
- **Resolvers:** Python (pip), JavaScript (npm), Java (Maven)
- **Max depth:** Configurable (default: 3)
- **Tree features:** Version conflict detection, upgrade recommendations, risk scoring
- **Health check:** `analyze_package_health()` provides quick check without full resolution

#### Phase 4: Sandbox + Risk Scoring
- **Execution:** Docker container with resource limits (512m RAM, 1 CPU, 30s timeout, no network)
- **Security:** `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit 50`, read-only filesystem
- **Fallback:** Simulation mode when Docker unavailable
- **Detection rules:** 18 rules across 9 categories (Network, File System, Process, System Info, Privilege, Data, Encoding, Database, Crypto)
- **Risk scoring:** Weighted multi-factor calculation (sandbox 30%, violations 25%, status 20%, behavior 15%, complexity 10%)
- **Grading:** A (0-2), B (2-4), C (4-6), D (6-8), F (8-10)

## 3 Code Parser Language Support

| Language | Import Detection | Install Detection | Stdlib Filtering |
|----------|-----------------|-------------------|------------------|
| Python | `import X`, `from X import Y` | `pip install X` | ✅ 60+ modules |
| JavaScript | `require('X')`, `import from 'X'` | `npm install X` | ❌ |
| TypeScript | `require('X')`, `import from 'X'` | — | ❌ |
| Java | `import com.x.Y` | — | ✅ (java.*, javax.*) |
| Go | `"pkg"` in import() | — | ✅ (fmt, os, net, etc.) |
| Ruby | `require 'X'`, `gem 'X'` | — | ❌ |
| Shell/Bash | `pip install`, `npm install` | ✅ (tagged to ecosystem) | ✅ (Python stdlib) |

---