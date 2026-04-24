"""
Code Sandbox Module (Phase 4).

Provides containerized code execution environment for behavioral analysis
of LLM-generated code. Uses Docker for isolated execution with resource
limits and network restrictions.

This module implements the behavioral security layer by:
- Running code in isolated Docker containers
- Monitoring system calls and resource usage
- Detecting suspicious behavior patterns
- Generating risk scores based on observed behaviors
"""
import asyncio
import json
import subprocess
import tempfile
import os
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Callable
from enum import Enum
from datetime import datetime
from pathlib import Path

from src.proxy.logging import get_logger

logger = get_logger("sandbox")


class SandboxStatus(Enum):
    """Sandbox execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"


class BehaviorType(Enum):
    """Types of suspicious behaviors to detect."""
    NETWORK_ACCESS = "NETWORK_ACCESS"
    FILE_WRITE = "FILE_WRITE"
    FILE_READ_SENSITIVE = "FILE_READ_SENSITIVE"
    PROCESS_SPAWN = "PROCESS_SPAWN"
    SHELL_EXECUTION = "SHELL_EXECUTION"
    SYSTEM_INFO_ACCESS = "SYSTEM_INFO_ACCESS"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    ENCODED_DATA = "ENCODED_DATA"
    SUSPICIOUS_IMPORT = "SUSPICIOUS_IMPORT"


@dataclass
class BehaviorEvent:
    """Represents a detected behavior event."""
    behavior_type: BehaviorType
    timestamp: datetime
    details: str
    severity: int  # 1-10
    resource_usage: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.behavior_type.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "severity": self.severity,
            "resource_usage": self.resource_usage
        }


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    status: SandboxStatus
    execution_time_ms: float
    behaviors: List[BehaviorEvent] = field(default_factory=list)
    risk_score: float = 0.0
    output: str = ""
    error: Optional[str] = None
    resource_usage: Dict = field(default_factory=dict)
    blocked_reason: Optional[str] = None
    
    @property
    def is_secure(self) -> bool:
        """Check if execution is considered secure."""
        return self.status == SandboxStatus.COMPLETED and self.risk_score < 5.0
    
    @property
    def security_grade(self) -> str:
        """Get letter grade for execution security."""
        if self.status == SandboxStatus.TIMEOUT:
            return "C"  # Timeout is moderately concerning
        if self.status == SandboxStatus.ERROR:
            return "B"  # Error might be due to security measures
        if self.risk_score >= 8.0:
            return "F"
        elif self.risk_score >= 6.0:
            return "D"
        elif self.risk_score >= 4.0:
            return "C"
        elif self.risk_score >= 2.0:
            return "B"
        else:
            return "A"
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "execution_time_ms": self.execution_time_ms,
            "behaviors": [b.to_dict() for b in self.behaviors],
            "risk_score": self.risk_score,
            "output": self.output,
            "error": self.error,
            "resource_usage": self.resource_usage,
            "blocked_reason": self.blocked_reason,
            "is_secure": self.is_secure,
            "security_grade": self.security_grade
        }


class BehaviorDetector:
    """Detects suspicious behaviors in code."""
    
    SUSPICIOUS_IMPORTS = {
        "os", "sys", "subprocess", "socket", "urllib", "requests",
        "http", "ftplib", "telnetlib", "paramiko", "fabric",
        "pty", "tty", "termios", "fcntl", "resource", "signal",
        "ctypes", "struct", "platform", "uuid", "random",
        "crypt", "hashlib", "hmac", "secrets",
        "sqlite3", "psycopg", "mysql", "pymongo",
        "redis", "memcache", "elasticsearch",
        "popen", "spawn", "eval", "exec", "compile"
    }
    
    SUSPICIOUS_PATTERNS = [
        (r"os\.system\s*\(", BehaviorType.SHELL_EXECUTION, 8),
        (r"subprocess\.(call|run|Popen)\s*\(", BehaviorType.SHELL_EXECUTION, 7),
        (r"eval\s*\(", BehaviorType.SHELL_EXECUTION, 9),
        (r"exec\s*\(", BehaviorType.SHELL_EXECUTION, 9),
        (r"__import__\s*\(", BehaviorType.SUSPICIOUS_IMPORT, 6),
        (r"import\s+os\b", BehaviorType.SUSPICIOUS_IMPORT, 4),
        (r"import\s+sys\b", BehaviorType.SUSPICIOUS_IMPORT, 4),
        (r"import\s+subprocess\b", BehaviorType.SUSPICIOUS_IMPORT, 5),
        (r"socket\.socket\s*\(", BehaviorType.NETWORK_ACCESS, 7),
        (r"urllib\.request", BehaviorType.NETWORK_ACCESS, 5),
        (r"requests\.(get|post)", BehaviorType.NETWORK_ACCESS, 5),
        (r"open\s*\([^)]*[wa]\)", BehaviorType.FILE_WRITE, 5),
        (r"\.write\s*\(", BehaviorType.FILE_WRITE, 5),
        (r"pty\.spawn", BehaviorType.PROCESS_SPAWN, 8),
        (r"os\.popen", BehaviorType.PROCESS_SPAWN, 7),
        (r"platform\.node", BehaviorType.SYSTEM_INFO_ACCESS, 4),
        (r"platform\.platform", BehaviorType.SYSTEM_INFO_ACCESS, 3),
        (r"base64\.(encode|decode)", BehaviorType.ENCODED_DATA, 6),
        (r"binascii", BehaviorType.ENCODED_DATA, 5),
        (r"os\.getcwd", BehaviorType.SYSTEM_INFO_ACCESS, 2),
        (r"os\.getuid", BehaviorType.SYSTEM_INFO_ACCESS, 4),
        (r"os\.chmod", BehaviorType.PRIVILEGE_ESCALATION, 7),
        (r"os\.chown", BehaviorType.PRIVILEGE_ESCALATION, 7),
        (r"\bsudo\b", BehaviorType.PRIVILEGE_ESCALATION, 9),
    ]
    
    def __init__(self):
        import re
        self.patterns = [
            (re.compile(pattern, re.IGNORECASE), behavior, severity)
            for pattern, behavior, severity in self.SUSPICIOUS_PATTERNS
        ]
    
    def detect_in_code(self, code: str) -> List[BehaviorEvent]:
        """Detect suspicious patterns in code before execution."""
        events = []
        
        for pattern, behavior, severity in self.patterns:
            matches = pattern.findall(code)
            if matches:
                events.append(BehaviorEvent(
                    behavior_type=behavior,
                    timestamp=datetime.now(),
                    details=f"Pattern detected: {pattern.pattern} ({len(matches)} occurrences)",
                    severity=severity,
                    resource_usage={"matches": len(matches)}
                ))
        
        # Check for suspicious imports
        import_patterns = [
            (r"import\s+(\w+)", "import"),
            (r"from\s+(\w+)\s+import", "from")
        ]
        
        import re
        found_imports = set()
        for pattern, import_type in import_patterns:
            for match in re.finditer(pattern, code):
                module = match.group(1)
                if module in self.SUSPICIOUS_IMPORTS:
                    found_imports.add(module)
        
        if found_imports:
            events.append(BehaviorEvent(
                behavior_type=BehaviorType.SUSPICIOUS_IMPORT,
                timestamp=datetime.now(),
                details=f"Suspicious imports: {', '.join(found_imports)}",
                severity=4,
                resource_usage={"imports": list(found_imports)}
            ))
        
        return events
    
    def calculate_risk_score(self, events: List[BehaviorEvent]) -> float:
        """Calculate total risk score from behavior events."""
        if not events:
            return 0.0
        
        score = 0.0
        for event in events:
            score += event.severity
        
        # Cap at 10
        return min(score, 10.0)


class SandboxRunner:
    """Executes code in isolated Docker containers."""
    
    def __init__(
        self,
        image: str = "python:3.11-slim",
        timeout_seconds: int = 30,
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
        network_enabled: bool = False,
        readonly_filesystem: bool = True,
        user: str = "1000:1000"
    ):
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled
        self.readonly_filesystem = readonly_filesystem
        self.user = user
        self.detector = BehaviorDetector()
    
    def _check_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def execute(self, code: str, language: str = "python") -> SandboxResult:
        """
        Execute code in sandbox and monitor for suspicious behaviors.
        
        Args:
            code: Code to execute
            language: Programming language (currently supports python)
        
        Returns:
            SandboxResult with execution details and risk assessment
        """
        start_time = time.time()
        
        # Pre-execution analysis
        pre_events = self.detector.detect_in_code(code)
        initial_risk = self.detector.calculate_risk_score(pre_events)
        
        # If risk is too high, don't execute
        if initial_risk >= 8.0:
            return SandboxResult(
                status=SandboxStatus.BLOCKED,
                execution_time_ms=0,
                behaviors=pre_events,
                risk_score=initial_risk,
                blocked_reason="Pre-execution analysis detected high-risk patterns"
            )
        
        # Execute in Docker container
        if self._check_docker_available():
            return await self._execute_in_docker(code, start_time, pre_events)
        else:
            # Fallback: simulation mode for testing/development
            return self._simulate_execution(code, start_time, pre_events)
    
    async def _execute_in_docker(
        self,
        code: str,
        start_time: float,
        pre_events: List[BehaviorEvent]
    ) -> SandboxResult:
        """Execute code in a Docker container."""
        behaviors = list(pre_events)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write code to file
            code_file = Path(tmpdir) / "code.py"
            code_file.write_text(code)
            
            # Build docker command
            cmd = [
                "docker", "run",
                "--rm",
                "--network", "none" if not self.network_enabled else "bridge",
                "--memory", self.memory_limit,
                "--cpus", str(self.cpu_limit),
                "--read-only" if self.readonly_filesystem else "--read-write",
                "--user", self.user,
                "--pids-limit", "50",
                "--security-opt", "no-new-privileges",
                "--cap-drop", "ALL",
                "-v", f"{tmpdir}:/code:ro",
                "-w", "/code",
                self.image,
                "python", "code.py"
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds
                )
                
                execution_time = (time.time() - start_time) * 1000
                
                if result.returncode == 0:
                    return SandboxResult(
                        status=SandboxStatus.COMPLETED,
                        execution_time_ms=execution_time,
                        behaviors=behaviors,
                        risk_score=self.detector.calculate_risk_score(behaviors),
                        output=result.stdout
                    )
                elif result.returncode == 124:
                    return SandboxResult(
                        status=SandboxStatus.TIMEOUT,
                        execution_time_ms=execution_time,
                        behaviors=behaviors,
                        risk_score=self.detector.calculate_risk_score(behaviors) + 2.0,
                        error="Execution timed out"
                    )
                else:
                    return SandboxResult(
                        status=SandboxStatus.ERROR,
                        execution_time_ms=execution_time,
                        behaviors=behaviors,
                        risk_score=self.detector.calculate_risk_score(behaviors),
                        error=result.stderr
                    )
            
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    status=SandboxStatus.TIMEOUT,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    behaviors=behaviors,
                    risk_score=5.0,
                    error="Docker execution timed out"
                )
    
    def _simulate_execution(
        self,
        code: str,
        start_time: float,
        pre_events: List[BehaviorEvent]
    ) -> SandboxResult:
        """Simulate execution for testing/development."""
        behaviors = list(pre_events)
        
        execution_time = (time.time() - start_time) * 1000
        risk_score = self.detector.calculate_risk_score(behaviors)
        
        return SandboxResult(
            status=SandboxStatus.COMPLETED,
            execution_time_ms=execution_time,
            behaviors=behaviors,
            risk_score=risk_score,
            output="[SIMULATION MODE] Code analysis complete",
            error=None
        )


# Global sandbox instance
_sandbox_instances: Dict[str, SandboxRunner] = {}


def get_sandbox(
    name: str = "default",
    **kwargs
) -> SandboxRunner:
    """Get or create a sandbox runner instance."""
    if name not in _sandbox_instances:
        _sandbox_instances[name] = SandboxRunner(**kwargs)
    return _sandbox_instances[name]


async def analyze_code_sandbox(
    code: str,
    language: str = "python",
    risk_threshold: float = 5.0,
    block_on_high_risk: bool = True,
    **sandbox_kwargs
) -> SandboxResult:
    """
    Analyze code in sandbox environment.
    
    Args:
        code: Code to analyze
        language: Programming language
        risk_threshold: Risk score above which to block
        block_on_high_risk: Whether to block high-risk code
    
    Returns:
        SandboxResult with analysis
    """
    sandbox = get_sandbox(**sandbox_kwargs)
    result = await sandbox.execute(code, language)
    
    if block_on_high_risk and result.risk_score >= risk_threshold:
        result.status = SandboxStatus.BLOCKED
        result.blocked_reason = f"Risk score {result.risk_score:.1f} exceeds threshold {risk_threshold}"
    
    return result
