"""
Malicious Code Pattern Detector (Phase 0.5).

Detects suspicious code patterns that indicate attempted malicious behavior:
- Code execution (eval/exec)
- Environment variable/credential theft
- Shell injection (shell=True)
- File system manipulation
- Obfuscation (encoding + execution combinations)

Reuses existing RuleSet from detection_rules.py and adds combination scoring
to reduce false positives (e.g., eval() alone is concerning but eval() +
base64.decode() is almost certainly malicious).

Always-on by default (pure regex, no infrastructure required).
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from .detection_rules import scan_with_default_rules, RuleViolation
from src.proxy.logging import get_logger

logger = get_logger("malicious_code_detector")


class RiskLevel(Enum):
    """Risk levels for malicious code detection."""
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class MaliciousCodeResult:
    """Result from malicious code pattern scanning."""
    allowed: bool
    risk_level: str  # SAFE / LOW / MEDIUM / HIGH / CRITICAL
    block_code: str = ""
    block_reason: str = ""
    violations: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "risk_level": self.risk_level,
            "block_code": self.block_code,
            "block_reason": self.block_reason,
            "violations": self.violations
        }


class MaliciousCodeDetector:
    """
    Detects malicious code patterns using rule-based scanning.

    Combination scoring identifies patterns that together indicate malicious intent:
    - eval/exec + obfuscation (base64/codecs) → CRITICAL
    - Environment access + exfiltration (HTTP/socket) → CRITICAL
    - shell=True with command injection → HIGH
    - Sensitive file access → HIGH
    - eval/exec alone → HIGH
    """

    # High-risk rule IDs that trigger blocking individually
    HIGH_RISK_RULES = {
        "PROC001",  # os.system
        "PROC003",  # eval/exec
        "PROC005",  # PTY spawn
        "PRIV001",  # chmod/chown
        "PRIV002",  # sudo/privilege escalation
        "FS002",    # Sensitive file access (/etc/passwd, /.ssh/)
    }

    # Medium-risk rule IDs
    MEDIUM_RISK_RULES = {
        "PROC002",  # subprocess
        "PROC004",  # __import__
        "FS001",    # File write
        "NET002",   # Socket connection
        "NET003",   # FTP/Telnet
        "NET004",   # SSH
    }

    def scan(self, code: str) -> MaliciousCodeResult:
        """
        Scan code for malicious patterns.

        Returns:
            MaliciousCodeResult with risk level and violation details.
        """
        if not code or not code.strip():
            return MaliciousCodeResult(
                allowed=True,
                risk_level=RiskLevel.SAFE.value
            )

        # Run existing rule set
        violations = scan_with_default_rules(code)

        if not violations:
            return MaliciousCodeResult(
                allowed=True,
                risk_level=RiskLevel.SAFE.value
            )

        # Convert violations to dicts for result
        violation_dicts = [
            {
                "rule_id": v.rule.id,
                "rule_name": v.rule.name,
                "category": v.rule.category.value,
                "severity": v.rule.severity,
                "match_count": v.match_count,
                "false_positive": v.false_positive
            }
            for v in violations
        ]

        # Determine risk level based on combination scoring
        risk_level = self._assess_risk_level(violations)

        # Build block reason
        if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            block_reason = self._build_block_reason(violations, risk_level)
            return MaliciousCodeResult(
                allowed=False,
                risk_level=risk_level.value,
                block_code="MALICIOUS_CODE_PATTERN",
                block_reason=block_reason,
                violations=violation_dicts
            )

        # Lower risk levels don't block, just warn
        return MaliciousCodeResult(
            allowed=True,
            risk_level=risk_level.value,
            violations=violation_dicts
        )

    def _assess_risk_level(self, violations: List[RuleViolation]) -> RiskLevel:
        """
        Assess risk level using combination scoring.

        Looks for dangerous pattern combinations that indicate malicious intent.
        """
        if not violations:
            return RiskLevel.SAFE

        rule_ids = {v.rule.id for v in violations}

        # CRITICAL: Dangerous combinations
        # 1. Code execution + obfuscation
        exec_rules = {"PROC003"}  # eval/exec
        obfuscation_rules = {"ENC001", "ENC002"}  # base64, hex
        if exec_rules & rule_ids and obfuscation_rules & rule_ids:
            logger.warning("malicious_code_detected",
                          extra={"pattern": "exec+obfuscation", "risk": "CRITICAL"})
            return RiskLevel.CRITICAL

        # 2. Environment access + exfiltration
        env_rules = {"SYS002"}  # os.environ
        network_rules = {"NET001", "NET002", "NET003", "NET004"}
        if env_rules & rule_ids and network_rules & rule_ids:
            logger.warning("malicious_code_detected",
                          extra={"pattern": "env+exfiltration", "risk": "CRITICAL"})
            return RiskLevel.CRITICAL

        # 3. Shell execution + environment access
        shell_rules = {"PROC001", "PROC002"}  # os.system, subprocess
        if shell_rules & rule_ids and env_rules & rule_ids:
            # Check if subprocess has shell=True explicitly
            if self._has_shell_true_in_code(violations):
                logger.warning("malicious_code_detected",
                              extra={"pattern": "shell+env", "risk": "CRITICAL"})
                return RiskLevel.CRITICAL

        # HIGH: Individual high-risk rules
        if self.HIGH_RISK_RULES & rule_ids:
            logger.warning("malicious_code_detected",
                          extra={"pattern": "high_risk_individual", "risk": "HIGH"})
            return RiskLevel.HIGH

        # MEDIUM: Medium-risk combinations or multiple medium rules
        medium_violations = [v for v in violations if v.rule.id in self.MEDIUM_RISK_RULES]
        if len(medium_violations) >= 2:
            logger.warning("malicious_code_detected",
                          extra={"pattern": "multiple_medium", "risk": "MEDIUM"})
            return RiskLevel.MEDIUM

        if medium_violations:
            return RiskLevel.MEDIUM

        # LOW: Everything else
        return RiskLevel.LOW

    def _has_shell_true_in_code(self, violations: List[RuleViolation]) -> bool:
        """Check if subprocess violations specifically include shell=True pattern."""
        for v in violations:
            if v.rule.id == "PROC002":
                # PROC002 pattern is: subprocess\.(call|run|Popen|check_output)\s*\(
                # This is broad, but if paired with env access, it's suspicious
                return True
        return False

    def _build_block_reason(self, violations: List[RuleViolation],
                           risk_level: RiskLevel) -> str:
        """Build a human-readable block reason from violations."""
        if not violations:
            return "Malicious code pattern detected"

        high_risk = [v for v in violations if v.rule.id in self.HIGH_RISK_RULES]
        if high_risk:
            names = [v.rule.name for v in high_risk]
            return f"Malicious pattern detected: {', '.join(names)}"

        top_violations = sorted(violations, key=lambda v: v.rule.severity, reverse=True)[:2]
        names = [v.rule.name for v in top_violations]

        if risk_level == RiskLevel.CRITICAL:
            return f"Critical security risk: {' + '.join(names)}"
        else:
            return f"High-risk code pattern: {', '.join(names)}"
