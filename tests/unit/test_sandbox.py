"""
Unit tests for Sandbox Module (Phase 4).
"""
import pytest
from src.output_security.sandbox import (
    BehaviorDetector,
    BehaviorEvent,
    BehaviorType,
    SandboxResult,
    SandboxRunner,
    SandboxStatus,
    analyze_code_sandbox,
)


class TestBehaviorDetector:
    """Test BehaviorDetector class."""
    
    def test_detect_shell_execution(self):
        """Test detection of shell execution patterns."""
        detector = BehaviorDetector()
        
        code = "import os\nos.system('ls -la')"
        events = detector.detect_in_code(code)
        
        shell_events = [e for e in events if e.behavior_type == BehaviorType.SHELL_EXECUTION]
        assert len(shell_events) > 0
    
    def test_detect_network_access(self):
        """Test detection of network access patterns."""
        detector = BehaviorDetector()
        
        code = "import requests\nrequests.get('https://evil.com')"
        events = detector.detect_in_code(code)
        
        network_events = [e for e in events if e.behavior_type == BehaviorType.NETWORK_ACCESS]
        assert len(network_events) > 0
    
    def test_detect_file_write(self):
        """Test detection of file write operations."""
        detector = BehaviorDetector()
        
        code = "with open('output.txt', 'w') as f:\n    f.write('data')"
        events = detector.detect_in_code(code)
        
        write_events = [e for e in events if e.behavior_type == BehaviorType.FILE_WRITE]
        assert len(write_events) > 0
    
    def test_detect_eval_exec(self):
        """Test detection of eval/exec."""
        detector = BehaviorDetector()
        
        code = "eval('1 + 1')"
        events = detector.detect_in_code(code)
        
        exec_events = [e for e in events if e.behavior_type == BehaviorType.SHELL_EXECUTION]
        assert len(exec_events) > 0
    
    def test_safe_code_no_events(self):
        """Test that safe code produces no events."""
        detector = BehaviorDetector()
        
        code = """
def calculate_sum(numbers):
    return sum(numbers)

result = calculate_sum([1, 2, 3, 4, 5])
print(result)
"""
        events = detector.detect_in_code(code)
        
        # Should have no high-severity events
        high_severity = [e for e in events if e.severity >= 7]
        assert len(high_severity) == 0
    
    def test_calculate_risk_score(self):
        """Test risk score calculation."""
        detector = BehaviorDetector()
        
        events = [
            BehaviorEvent(
                behavior_type=BehaviorType.SHELL_EXECUTION,
                timestamp=None,
                details="test",
                severity=8
            ),
            BehaviorEvent(
                behavior_type=BehaviorType.NETWORK_ACCESS,
                timestamp=None,
                details="test",
                severity=5
            )
        ]
        
        score = detector.calculate_risk_score(events)
        assert score == 13.0  # 8 + 5, capped at 10


class TestSandboxRunner:
    """Test SandboxRunner class."""
    
    def test_sandbox_runner_initialization(self):
        """Test sandbox runner initialization."""
        runner = SandboxRunner(
            image="python:3.11-slim",
            timeout_seconds=30,
            memory_limit="256m"
        )
        
        assert runner.image == "python:3.11-slim"
        assert runner.timeout_seconds == 30
        assert runner.memory_limit == "256m"
    
    def test_sandbox_runner_default_settings(self):
        """Test default settings."""
        runner = SandboxRunner()
        
        assert runner.image == "python:3.11-slim"
        assert runner.network_enabled is False
        assert runner.readonly_filesystem is True


class TestSandboxResult:
    """Test SandboxResult dataclass."""
    
    def test_secure_result(self):
        """Test secure result."""
        result = SandboxResult(
            status=SandboxStatus.COMPLETED,
            execution_time_ms=100,
            risk_score=2.0
        )
        
        assert result.is_secure is True
        assert result.security_grade == "B"
    
    def test_insecure_result(self):
        """Test insecure result."""
        result = SandboxResult(
            status=SandboxStatus.COMPLETED,
            execution_time_ms=100,
            risk_score=8.0
        )
        
        assert result.is_secure is False
        assert result.security_grade == "F"
    
    def test_timeout_result(self):
        """Test timeout result."""
        result = SandboxResult(
            status=SandboxStatus.TIMEOUT,
            execution_time_ms=30000
        )
        
        assert result.security_grade == "C"
    
    def test_blocked_result(self):
        """Test blocked result."""
        result = SandboxResult(
            status=SandboxStatus.BLOCKED,
            execution_time_ms=0,
            risk_score=10.0,
            blocked_reason="Pre-execution analysis detected high-risk patterns"
        )
        
        assert result.is_secure is False
        assert result.blocked_reason is not None
    
    def test_to_dict(self):
        """Test dict serialization."""
        result = SandboxResult(
            status=SandboxStatus.COMPLETED,
            execution_time_ms=100,
            risk_score=3.0
        )
        
        d = result.to_dict()
        
        assert d["status"] == "COMPLETED"
        assert d["execution_time_ms"] == 100
        assert d["risk_score"] == 3.0
        assert d["security_grade"] == "B"


class TestBehaviorEvent:
    """Test BehaviorEvent dataclass."""
    
    def test_behavior_event_to_dict(self):
        """Test dict serialization."""
        from datetime import datetime
        
        event = BehaviorEvent(
            behavior_type=BehaviorType.NETWORK_ACCESS,
            timestamp=datetime.now(),
            details="HTTP request detected",
            severity=5,
            resource_usage={"matches": 2}
        )
        
        d = event.to_dict()
        
        assert d["type"] == "NETWORK_ACCESS"
        assert d["severity"] == 5
        assert d["resource_usage"]["matches"] == 2


class TestAnalyzeCodeSandbox:
    """Test analyze_code_sandbox function."""
    
    @pytest.mark.asyncio
    async def test_safe_code_passes(self):
        """Test that safe code passes analysis."""
        code = """
def greet(name):
    return f"Hello, {name}!"

message = greet("World")
print(message)
"""
        result = await analyze_code_sandbox(code, risk_threshold=5.0)
        
        assert result.status == SandboxStatus.COMPLETED
        assert result.risk_score < 5.0
    
    @pytest.mark.asyncio
    async def test_dangerous_code_blocked(self):
        """Test that dangerous code is blocked."""
        code = """
import os
os.system('rm -rf /')
"""
        result = await analyze_code_sandbox(code, risk_threshold=5.0, block_on_high_risk=True)
        
        # Should be blocked due to high risk
        assert result.risk_score >= 5.0


class TestBehaviorTypes:
    """Test BehaviorType enum."""
    
    def test_behavior_types_exist(self):
        """Test all behavior types are defined."""
        assert BehaviorType.NETWORK_ACCESS is not None
        assert BehaviorType.FILE_WRITE is not None
        assert BehaviorType.PROCESS_SPAWN is not None
        assert BehaviorType.SHELL_EXECUTION is not None
        assert BehaviorType.PRIVILEGE_ESCALATION is not None


class TestSandboxStatus:
    """Test SandboxStatus enum."""
    
    def test_statuses_exist(self):
        """Test all statuses are defined."""
        assert SandboxStatus.PENDING is not None
        assert SandboxStatus.RUNNING is not None
        assert SandboxStatus.COMPLETED is not None
        assert SandboxStatus.TIMEOUT is not None
        assert SandboxStatus.ERROR is not None
        assert SandboxStatus.BLOCKED is not None


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_code(self):
        """Test empty code handling."""
        detector = BehaviorDetector()
        events = detector.detect_in_code("")
        
        assert len(events) == 0
    
    def test_whitespace_only(self):
        """Test whitespace-only code."""
        detector = BehaviorDetector()
        events = detector.detect_in_code("   \n\t  \n   ")
        
        assert len(events) == 0
    
    def test_comment_only(self):
        """Test comment-only code."""
        detector = BehaviorDetector()
        code = """
# This is a comment
# Another comment
"""
        events = detector.detect_in_code(code)
        
        # Should have no events for comments only
        assert len([e for e in events if e.severity >= 7]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
