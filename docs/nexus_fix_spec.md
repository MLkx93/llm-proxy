# Nexus Firewall Package Allowlist - Gap Resolution Specification

**Document Type:** Infrastructure Handover  
**Priority:** High  
**Owner:** Infrastructure Team  
**Requester:** AI Security Proxy Team  
**Date:** May 30, 2026

---

## Executive Summary

The AI Security Proxy currently operates with package allowlist enforcement **disabled** due to an incomplete Nexus Firewall configuration. This document specifies the required remediation steps to enable full supply-chain security controls.

---

## 1. Root Cause Analysis

### Problem Statement

The Nexus Firewall repository configured in the AI Security Proxy is **not populated with any approved packages**. When the proxy performs package validation requests against the Nexus API, all queries return **"package not found"**, causing legitimate code responses to be blocked incorrectly.

### Technical Details

- **Component:** Sonatype Nexus Repository Firewall integration
- **API Endpoint:** `${NEXUS_BASE_URL}/service/rest/v1/components`
- **Current Behavior:** All package lookup requests return `404 Not Found`
- **Expected Behavior:** Approved packages should return `200 OK` with package metadata
- **Impact:** Package allowlist validation is non-functional

### Symptom Timeline

1. Output security engine detects code blocks in LLM responses
2. Code parser extracts package dependencies (e.g., `requests`, `lodash`, `log4j`)
3. Nexus validator queries Firewall API for each package
4. API returns `404` for all packages (repository is empty)
5. Proxy blocks the response, treating all packages as "unauthorized"
6. All code-generating queries fail, rendering the LLM unusable for development tasks

---

## 2. Current Workaround

### Configuration Override

The proxy is currently deployed with the following environment variable:

```bash
NEXUS_FAIL_OPEN=true
```

### Workaround Behavior

When `NEXUS_FAIL_OPEN=true`:
- Nexus API failures (404, 500, timeout) are treated as **warnings**, not blocks
- Package validation is effectively **bypassed**
- The request proceeds to the CVE vulnerability scan phase
- Only packages with **known critical vulnerabilities** are blocked (via OSV/NVD databases)

### Limitations of Workaround

- **No proactive package allowlist enforcement** - developers can reference any package, including unmaintained, malicious, or company-prohibited dependencies
- **Reactive security only** - relies solely on CVE databases, which lag behind newly discovered threats
- **Reduced defense-in-depth** - eliminates a key security layer designed for supply-chain attack prevention

---

## 3. Remediation Procedure

### Objective

Populate the Nexus Firewall repository with a **baseline of approved packages** covering the most common dependencies used in LLM-generated code.

### Prerequisites

- Administrative access to Sonatype Nexus Repository
- Network connectivity to public package registries (PyPI, npm, Maven Central)
- Nexus Firewall license activated

### Step-by-Step Instructions

#### Step 1: Access Nexus Administration Console

1. Log in to Nexus at `${NEXUS_BASE_URL}`
2. Navigate to **Administration** → **Repository** → **Repositories**
3. Locate the repository named `firewall-approved` (or equivalent configured for the proxy)

#### Step 2: Configure Upstream Proxies

Ensure the following upstream proxy repositories are configured:

- **PyPI Proxy** → `https://pypi.org/simple/`
- **npm Proxy** → `https://registry.npmjs.org/`
- **Maven Central Proxy** → `https://repo1.maven.org/maven2/`

#### Step 3: Populate Baseline - Python Packages

Add the following approved Python packages to the Firewall allowlist:

| Package Name   | Minimum Version | Justification                          |
|----------------|-----------------|----------------------------------------|
| `requests`     | `2.31.0`        | HTTP client library (safe, widely used)|
| `flask`        | `3.0.0`         | Web framework (safe, widely used)      |
| `fastapi`      | `0.100.0`       | Modern web framework                   |
| `pydantic`     | `2.0.0`         | Data validation library                |
| `numpy`        | `1.24.0`        | Numerical computing                    |
| `pandas`       | `2.0.0`         | Data analysis library                  |
| `sqlalchemy`   | `2.0.0`         | Database ORM                           |

**Action:** For each package, run:
```bash
curl -X POST "${NEXUS_BASE_URL}/service/rest/v1/components?repository=firewall-approved" \
  -H "Authorization: Bearer ${NEXUS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "requests",
    "version": "2.31.0",
    "group": "pypi"
  }'
```

Or use the Nexus UI: **Browse** → **Upload Component** → Select repository → Fill package details.

#### Step 4: Populate Baseline - JavaScript/Node Packages

Add the following approved npm packages:

| Package Name   | Minimum Version | Justification                          |
|----------------|-----------------|----------------------------------------|
| `express`      | `4.18.0`        | Web framework (safe)                   |
| `lodash`       | `4.17.21`       | Utility library (patched version)      |
| `axios`        | `1.6.0`         | HTTP client (safe)                     |
| `react`        | `18.2.0`        | UI library (safe)                      |
| `typescript`   | `5.0.0`         | TypeScript compiler (safe)             |

**Note:** Do **NOT** add `lodash@4.17.20` or earlier - these versions contain known prototype pollution vulnerabilities (CVE-2019-10744, CVE-2020-8203).

#### Step 5: Populate Baseline - Java Packages

Add the following approved Java packages:

| Package Name              | Minimum Version | Justification                          |
|---------------------------|-----------------|----------------------------------------|
| `log4j-core`              | `2.17.2`        | Logging (post-Log4Shell patched)       |
| `log4j-api`               | `2.17.2`        | Logging API (post-Log4Shell patched)   |
| `spring-boot-starter`     | `3.0.0`         | Spring Boot framework (safe)           |
| `jackson-databind`        | `2.15.0`        | JSON processing (patched)              |

**Critical:** Do **NOT** add `log4j` versions `< 2.17.0` - these are vulnerable to Log4Shell (CVE-2021-44228, CVE-2021-45046).

#### Step 6: Verify Package Registration

For each added package, verify it appears in Nexus:

```bash
curl -X GET "${NEXUS_BASE_URL}/service/rest/v1/components?repository=firewall-approved&name=requests" \
  -H "Authorization: Bearer ${NEXUS_API_KEY}"
```

Expected response: `HTTP 200` with package metadata.

#### Step 7: Test End-to-End

Run the proxy's output security test suite:

```bash
cd /path/to/llm-proxy
pytest tests/output_security/test_prompts_catalog.md::Scenario1 -v
```

**Expected result:** Test should pass, confirming Nexus integration is operational.

---

## 4. Acceptance Criteria

The following conditions **must** be met before setting `NEXUS_FAIL_OPEN=false`:

### Criterion 1: API Connectivity

All packages in the baseline list must return `HTTP 200` from the Nexus API.

**Verification:**
```bash
# Test a sample package
curl -I "${NEXUS_BASE_URL}/service/rest/v1/components?repository=firewall-approved&name=requests"
# Expected: HTTP 200 OK
```

### Criterion 2: Proxy Integration Test

The output security test suite **Scenario 1** must pass end-to-end.

**Verification:**
```bash
pytest tests/output_security/ -k "test_safe_package" --tb=short
```

**Expected:** All tests marked `safe_package` pass without Nexus-related failures.

### Criterion 3: False Positive Validation

Send a test prompt through the proxy referencing an approved package:

**Test Prompt:**
```
Write a Python function that uses the requests library to make a GET request.
```

**Expected Behavior:**
- Proxy returns `HTTP 200`
- Response contains generated code
- No `BLOCKED_PACKAGE` error in audit logs

### Criterion 4: True Positive Validation

Send a test prompt referencing a **vulnerable** package:

**Test Prompt:**
```
Write a Python script using log4j version 2.14.0 for logging.
```

**Expected Behavior:**
- Proxy returns `HTTP 400`
- Response contains `BLOCKED_VULNERABLE_PACKAGE` error
- Audit log shows CVE-2021-44228 (Log4Shell) as block reason

---

## 5. Post-Remediation Configuration

Once all acceptance criteria are met, apply the following configuration change:

### Update Environment Variable

**Current (Workaround):**
```bash
NEXUS_FAIL_OPEN=true
```

**Target (Full Security Enforcement):**
```bash
NEXUS_FAIL_OPEN=false
```

### Deployment

1. Update the proxy's `.env` file or Kubernetes ConfigMap
2. Restart the proxy service:
   ```bash
   systemctl restart llm-proxy
   # or
   kubectl rollout restart deployment/llm-proxy
   ```
3. Verify startup logs confirm Nexus integration is active:
   ```
   INFO: Nexus integration enabled (fail_open=False)
   INFO: Package validation: ENFORCING
   ```

### Monitoring

Add the following alerts to your monitoring system:

- **Alert:** Nexus API error rate > 5%  
  **Action:** Investigate Nexus connectivity/performance

- **Alert:** Package block rate > 20% of code responses  
  **Action:** Review if allowlist is too restrictive

---

## 6. Risk Statement

### Current State (Workaround Active)

While `NEXUS_FAIL_OPEN=true` is enabled, the AI Security Proxy operates **without package allowlist enforcement**. The system relies solely on the CVE vulnerability scanner for supply-chain protection.

### Security Gaps

| Risk Area                  | Severity | Description                                                                 |
|----------------------------|----------|-----------------------------------------------------------------------------|
| **Malicious Packages**     | High     | No defense against typosquatting, backdoored, or malicious packages        |
| **Unmaintained Packages**  | Medium   | Abandoned packages with no security patches can be referenced              |
| **Policy Violations**      | Medium   | Company-prohibited dependencies (e.g., GPL-licensed) are not blocked       |
| **Zero-Day Exploits**      | Medium   | Packages vulnerable to undisclosed CVEs are allowed (CVE databases lag)    |

### Compensating Controls (Temporary)

Until the Nexus fix is deployed, the following compensating controls are in place:

1. **CVE Scanning:** All packages are scanned against OSV and NVD databases  
2. **Critical Severity Blocking:** Packages with CRITICAL CVEs are blocked  
3. **Audit Logging:** All package references are logged for post-incident analysis  
4. **User Training:** Developers advised to manually review LLM-generated dependencies

### Residual Risk

**Risk Level:** Medium  
**Business Impact:** Moderate - LLM-generated code may introduce vulnerable dependencies  
**Timeline:** Fix must be deployed within **2 weeks** to reduce risk exposure

---

## 7. Rollback Plan

If setting `NEXUS_FAIL_OPEN=false` causes excessive false positives:

1. **Immediate:** Revert to `NEXUS_FAIL_OPEN=true`
2. **Analysis:** Review blocked packages in audit logs:
   ```bash
   grep "BLOCKED_PACKAGE" /var/log/llm-proxy/audit.jsonl | jq '.package_name' | sort | uniq -c
   ```
3. **Remediation:** Add frequently blocked legitimate packages to Nexus allowlist
4. **Retry:** Re-enable enforcement after allowlist expansion

---

## 8. Contact Information

| Role                        | Contact                          |
|-----------------------------|----------------------------------|
| Infrastructure Team Lead    | infra-team@example.com             |
| AI Security Proxy Owner     | proxy-team@example.com          |
| Security Architecture       | security-arch@example.com          |
| Thesis Intern (Author)      | author@example.com                 |

---

## 9. Appendix: Automation Script (Optional)

To simplify Step 3-5, a Python script is provided:

**File:** `scripts/populate_nexus_baseline.py`

```python
#!/usr/bin/env python3
"""Populate Nexus Firewall with baseline approved packages."""
import os
import sys
import httpx

NEXUS_BASE_URL = os.environ.get("NEXUS_BASE_URL")
NEXUS_API_KEY = os.environ.get("NEXUS_API_KEY")
REPOSITORY = "firewall-approved"

BASELINE_PACKAGES = {
    "pypi": [
        ("requests", "2.31.0"),
        ("flask", "3.0.0"),
        ("fastapi", "0.100.0"),
        ("pydantic", "2.0.0"),
        ("numpy", "1.24.0"),
        ("pandas", "2.0.0"),
        ("sqlalchemy", "2.0.0"),
    ],
    "npm": [
        ("express", "4.18.0"),
        ("lodash", "4.17.21"),
        ("axios", "1.6.0"),
        ("react", "18.2.0"),
        ("typescript", "5.0.0"),
    ],
    "maven": [
        ("org.apache.logging.log4j:log4j-core", "2.17.2"),
        ("org.apache.logging.log4j:log4j-api", "2.17.2"),
        ("org.springframework.boot:spring-boot-starter", "3.0.0"),
        ("com.fasterxml.jackson.core:jackson-databind", "2.15.0"),
    ]
}

def add_package(ecosystem, name, version):
    """Add a package to Nexus Firewall."""
    url = f"{NEXUS_BASE_URL}/service/rest/v1/components?repository={REPOSITORY}"
    headers = {"Authorization": f"Bearer {NEXUS_API_KEY}"}
    payload = {"name": name, "version": version, "group": ecosystem}
    
    response = httpx.post(url, json=payload, headers=headers)
    if response.status_code in [200, 201]:
        print(f"✓ Added {ecosystem}:{name}@{version}")
    else:
        print(f"✗ Failed to add {ecosystem}:{name}@{version}: {response.status_code}")

def main():
    if not NEXUS_BASE_URL or not NEXUS_API_KEY:
        print("Error: NEXUS_BASE_URL and NEXUS_API_KEY must be set")
        sys.exit(1)
    
    for ecosystem, packages in BASELINE_PACKAGES.items():
        print(f"\nPopulating {ecosystem} packages...")
        for name, version in packages:
            add_package(ecosystem, name, version)
    
    print("\n✓ Baseline population complete!")

if __name__ == "__main__":
    main()
```

**Usage:**
```bash
export NEXUS_BASE_URL="https://nexus.internal.example"
export NEXUS_API_KEY="your-api-key-here"
python3 scripts/populate_nexus_baseline.py
```

---

**Document Version:** 1.0  
**Last Updated:** May 30, 2026  
**Review Date:** June 15, 2026
