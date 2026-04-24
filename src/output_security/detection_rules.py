"""
Detection Rules Module (Phase 4).

Provides a configurable rule engine for detecting suspicious behaviors
in code. Supports custom rules, severity levels, and rule categories.

This module complements the sandbox by providing:
- Pre-defined detection rules for common attack patterns
- Configurable rule sets per category
- Rule enable/disable functionality
- Custom rule registration
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Callable
from enum import Enum
from datetime import datetime
import json

from .sandbox import BehaviorType, BehaviorEvent
from src.proxy.logging import get_logger

logger = get_logger("detection_rules")


class RuleCategory(Enum):
    """Categories of detection rules."""
    NETWORK = "NETWORK"
    FILE_SYSTEM = "FILE_SYSTEM"
    PROCESS = "PROCESS"
    SYSTEM_INFO = "SYSTEM_INFO"
    PRIVILEGE = "PRIVILEGE"
    DATA = "DATA"
    ENCODING = "ENCODING"
    CRYPTO = "CRYPTO"
    DATABASE = "DATABASE"
    CUSTOM = "CUSTOM"


@dataclass
class DetectionRule:
    """Represents a single detection rule."""
    id: str
    name: str
    pattern: str
    category: RuleCategory
    severity: int  # 1-10
    description: str
    enabled: bool = True
    false_positive_indicators: List[str] = field(default_factory=list)
    
    def matches(self, code: str) -> bool:
        """Check if code matches this rule's pattern."""
        try:
            return bool(re.search(self.pattern, code, re.IGNORECASE | re.MULTILINE))
        except re.error as e:
            logger.error("regex_error", pattern=self.pattern, error=str(e))
            return False
    
    def get_matches(self, code: str) -> List[str]:
        """Get all matches for this rule's pattern."""
        try:
            return re.findall(self.pattern, code, re.IGNORECASE | re.MULTILINE)
        except re.error:
            return []
    
    def is_false_positive(self, code: str) -> bool:
        """Check if match is likely a false positive."""
        for indicator in self.false_positive_indicators:
            if indicator.lower() in code.lower():
                return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "pattern": self.pattern,
            "category": self.category.value,
            "severity": self.severity,
            "description": self.description,
            "enabled": self.enabled
        }


@dataclass
class RuleViolation:
    """Represents a rule violation."""
    rule: DetectionRule
    match_count: int
    first_match_position: int
    false_positive: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule.id,
            "rule_name": self.rule.name,
            "category": self.rule.category.value,
            "severity": self.rule.severity,
            "match_count": self.match_count,
            "false_positive": self.false_positive
        }


class RuleSet:
    """Collection of detection rules."""
    
    # Pre-defined rules
    DEFAULT_RULES = [
        # Network rules
        DetectionRule(
            id="NET001",
            name="HTTP Request",
            pattern=r"(requests\.(get|post|put|delete|patch)|"
                   r"urllib\.request|"
                   r"httpx\.(get|post|put|delete)|"
                   r"http\.client\.HTTPConnection)",
            category=RuleCategory.NETWORK,
            severity=3,
            description="HTTP request detected"
        ),
        DetectionRule(
            id="NET002",
            name="Socket Connection",
            pattern=r"socket\.socket\s*\(",
            category=RuleCategory.NETWORK,
            severity=6,
            description="Direct socket creation detected"
        ),
        DetectionRule(
            id="NET003",
            name="FTP/Telnet Access",
            pattern=r"(ftplib|telnetlib)\.",
            category=RuleCategory.NETWORK,
            severity=7,
            description="FTP or Telnet access detected"
        ),
        DetectionRule(
            id="NET004",
            name="SSH Connection",
            pattern=r"(paramiko|fabric|ssh\.SSHClient)",
            category=RuleCategory.NETWORK,
            severity=8,
            description="SSH connection attempt detected"
        ),
        
        # File system rules
        DetectionRule(
            id="FS001",
            name="File Write",
            pattern=r"(open\s*\([^)]*[wa]\)|"
                   r"\.write\s*\(|"
                   r"with\s+open\s*\([^)]*[wa])",
            category=RuleCategory.FILE_SYSTEM,
            severity=4,
            description="File write operation detected"
        ),
        DetectionRule(
            id="FS002",
            name="Sensitive File Access",
            pattern=r"(/\.ssh/|/\.aws/|/\.env|"
                   r"\~/\.ssh/|"
                   r"/etc/passwd|"
                   r"/etc/shadow)",
            category=RuleCategory.FILE_SYSTEM,
            severity=8,
            description="Access to sensitive files detected"
        ),
        DetectionRule(
            id="FS003",
            name="Directory Traversal",
            pattern=r"\.\./|\.\.\\\\",
            category=RuleCategory.FILE_SYSTEM,
            severity=5,
            description="Potential directory traversal attempt"
        ),
        
        # Process rules
        DetectionRule(
            id="PROC001",
            name="Shell Execution (os.system)",
            pattern=r"os\.system\s*\(",
            category=RuleCategory.PROCESS,
            severity=8,
            description="os.system() call detected"
        ),
        DetectionRule(
            id="PROC002",
            name="Subprocess Execution",
            pattern=r"subprocess\.(call|run|Popen|check_output)\s*\(",
            category=RuleCategory.PROCESS,
            severity=7,
            description="Subprocess execution detected"
        ),
        DetectionRule(
            id="PROC003",
            name="eval/exec Usage",
            pattern=r"\b(eval|exec)\s*\(",
            category=RuleCategory.PROCESS,
            severity=9,
            description="Dynamic code execution (eval/exec) detected"
        ),
        DetectionRule(
            id="PROC004",
            name="Dynamic Import",
            pattern=r"__import__\s*\(",
            category=RuleCategory.PROCESS,
            severity=6,
            description="Dynamic module import detected"
        ),
        DetectionRule(
            id="PROC005",
            name="PTY Spawn",
            pattern=r"pty\.spawn",
            category=RuleCategory.PROCESS,
            severity=8,
            description="PTY spawn detected"
        ),
        
        # System info rules
        DetectionRule(
            id="SYS001",
            name="System Information Gathering",
            pattern=r"platform\.(node|platform|version|release|system)",
            category=RuleCategory.SYSTEM_INFO,
            severity=3,
            description="System information gathering detected"
        ),
        DetectionRule(
            id="SYS002",
            name="Environment Variable Access",
            pattern=r"os\.environ|os\.getenv",
            category=RuleCategory.SYSTEM_INFO,
            severity=4,
            description="Environment variable access detected"
        ),
        
        # Privilege rules
        DetectionRule(
            id="PRIV001",
            name="Privilege Modification",
            pattern=r"os\.(chmod|chown|lchown|fchmod|fchown)",
            category=RuleCategory.PRIVILEGE,
            severity=7,
            description="File permission modification detected"
        ),
        DetectionRule(
            id="PRIV002",
            name="Sudo/Privilege Escalation",
            pattern=r"\bsudo\b",
            category=RuleCategory.PRIVILEGE,
            severity=9,
            description="Potential privilege escalation detected"
        ),
        
        # Data rules
        DetectionRule(
            id="DATA001",
            name="Large Data Transfer",
            pattern=r"(print.*len|data\s*=.*1024|"
                   r"response.*content.*1024)",
            category=RuleCategory.DATA,
            severity=5,
            description="Large data operations detected"
        ),
        DetectionRule(
            id="DATA002",
            name="Clipboard Access",
            pattern=r"(pyperclip|tkinter\.Clipboard|"
                   r"xclip|xsel)",
            category=RuleCategory.DATA,
            severity=6,
            description="Clipboard access detected"
        ),
        
        # Encoding rules
        DetectionRule(
            id="ENC001",
            name="Base64 Encoding",
            pattern=r"base64\.(encode|decode|b64encode|b64decode)",
            category=RuleCategory.ENCODING,
            severity=5,
            description="Base64 encoding/decoding detected"
        ),
        DetectionRule(
            id="ENC002",
            name="Binary/Hex Data",
            pattern=r"(binascii|hexlify|unhexlify)",
            category=RuleCategory.ENCODING,
            severity=5,
            description="Binary or hex data handling detected"
        ),
        
        # Database rules
        DetectionRule(
            id="DB001",
            name="Database Connection",
            pattern=r"(psycopg|mysql\.connector|pymongo|"
                   r"redis\.Redis|elasticsearch\.Elasticsearch)",
            category=RuleCategory.DATABASE,
            severity=4,
            description="Database connection attempt detected"
        ),
        
        # Crypto rules
        DetectionRule(
            id="CRYP001",
            name="Cryptographic Operations",
            pattern=r"(cryptography\.Fernet|"
                   r"cryptography\.hazmat|"
                   r"pycrypto|"
                   r"pycryptodome)",
            category=RuleCategory.CRYPTO,
            severity=3,
            description="Cryptographic operations detected"
        ),
    ]
    
    def __init__(self, rules: Optional[List[DetectionRule]] = None):
        """Initialize with optional custom rules."""
        self.rules: Dict[str, DetectionRule] = {}
        
        # Add default rules
        for rule in self.DEFAULT_RULES:
            self.rules[rule.id] = rule
        
        # Add custom rules
        if rules:
            for rule in rules:
                self.rules[rule.id] = rule
    
    def add_rule(self, rule: DetectionRule) -> None:
        """Add a custom rule."""
        self.rules[rule.id] = rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False
    
    def get_enabled_rules(self) -> List[DetectionRule]:
        """Get all enabled rules."""
        return [r for r in self.rules.values() if r.enabled]
    
    def get_rules_by_category(self, category: RuleCategory) -> List[DetectionRule]:
        """Get rules by category."""
        return [r for r in self.rules.values() if r.category == category]
    
    def scan_code(self, code: str) -> List[RuleViolation]:
        """Scan code for rule violations."""
        violations = []
        
        for rule in self.get_enabled_rules():
            if rule.matches(code):
                # Check for false positives
                is_fp = rule.is_false_positive(code)
                
                # Find first match position
                match = re.search(rule.pattern, code, re.IGNORECASE | re.MULTILINE)
                position = match.start() if match else -1
                
                # Count matches
                matches = rule.get_matches(code)
                
                violations.append(RuleViolation(
                    rule=rule,
                    match_count=len(matches),
                    first_match_position=position,
                    false_positive=is_fp
                ))
        
        # Sort by severity (highest first)
        violations.sort(key=lambda v: v.rule.severity, reverse=True)
        
        return violations
    
    def calculate_risk_score(self, violations: List[RuleViolation]) -> float:
        """Calculate risk score from violations."""
        score = 0.0
        
        for v in violations:
            if not v.false_positive:
                # Weight by match count (capped at 5 matches)
                weight = min(v.match_count, 5)
                score += v.rule.severity * (1 + (weight - 1) * 0.1)
        
        return min(score, 10.0)
    
    def to_dict(self) -> Dict:
        """Export rules to dictionary."""
        return {
            "rules": [r.to_dict() for r in self.rules.values()],
            "total_count": len(self.rules),
            "enabled_count": len(self.get_enabled_rules())
        }
    
    @classmethod
    def from_categories(
        cls,
        categories: Set[RuleCategory],
        custom_rules: Optional[List[DetectionRule]] = None
    ) -> 'RuleSet':
        """Create RuleSet from specific categories."""
        rules = [
            r for r in cls.DEFAULT_RULES
            if r.category in categories
        ]
        if custom_rules:
            rules.extend(custom_rules)
        return cls(rules)


# Global rule set
_default_rule_set: Optional[RuleSet] = None


def get_default_rule_set() -> RuleSet:
    """Get or create the default rule set."""
    global _default_rule_set
    if _default_rule_set is None:
        _default_rule_set = RuleSet()
    return _default_rule_set


def scan_with_default_rules(code: str) -> List[RuleViolation]:
    """Quick scan using default rules."""
    rule_set = get_default_rule_set()
    return rule_set.scan_code(code)


def create_minimal_rule_set() -> RuleSet:
    """Create a minimal rule set with only high-severity rules."""
    minimal_categories = {
        RuleCategory.PROCESS,
        RuleCategory.PRIVILEGE,
        RuleCategory.NETWORK
    }
    return RuleSet.from_categories(minimal_categories)


def create_strict_rule_set() -> RuleSet:
    """Create a strict rule set with all rules enabled."""
    return RuleSet()
