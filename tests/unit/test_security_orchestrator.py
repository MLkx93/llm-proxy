"""
Integration tests for Security Orchestrator.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.output_security.engine import (
    SecurityOrchestrator,
    SecurityPhase,
    PhaseResult,
    SecurityCheckResult,
    get_orchestrator,
)
from src.output_security.nexus import ValidationResult


class TestSecurityOrchestrator:
    """Test SecurityOrchestrator class."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator for testing."""
        return SecurityOrchestrator(
            enable_vuln_scan=False,
            enable_version_validation=False,
            enable_dependency_scan=False,
            enable_sandbox=False,
            early_termination=True,
            fail_safe=True,
        )
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        orch = SecurityOrchestrator()
        assert orch.enable_vuln_scan is True
        assert orch.enable_version_validation is True
        assert orch.enable_dependency_scan is True
        assert orch.enable_sandbox is True
        assert orch.early_termination is True
        assert orch.fail_safe is True
    
    @pytest.mark.asyncio
    async def test_check_package_nexus_approved(self, orchestrator):
        """Test package check when Nexus approves."""
        with patch('src.output_security.engine.validate_package') as mock_validate:
            mock_validate.return_value = ValidationResult(
                approved=True,
                block_code="",
                reason=""
            )
            
            result = await orchestrator.check_package(
                package_name="requests",
                version="2.25.0",
                ecosystem="pypi",
                source_type="pypi"
            )
            
            assert result.allowed is True
            assert len(result.phase_results) == 1
            assert result.phase_results[0].phase == SecurityPhase.NEXUS
            assert result.phase_results[0].passed is True
    
    @pytest.mark.asyncio
    async def test_check_package_nexus_blocked(self, orchestrator):
        """Test package check when Nexus blocks."""
        with patch('src.output_security.engine.validate_package') as mock_validate:
            mock_validate.return_value = ValidationResult(
                approved=False,
                block_code="BLOCKED_REPOSITORY",
                reason="Package not in approved repository"
            )
            
            result = await orchestrator.check_package(
                package_name="malicious-package",
                version="1.0.0",
                ecosystem="pypi",
                source_type="pypi"
            )
            
            assert result.allowed is False
            assert result.block_code == "BLOCKED_REPOSITORY"
            assert result.blocked_packages == ["malicious-package"]
            assert result.security_grade == "F"
    
    @pytest.mark.asyncio
    async def test_check_package_nexus_error_failsafe(self, orchestrator):
        """Test that Nexus error triggers fail-safe blocking."""
        with patch('src.output_security.engine.validate_package') as mock_validate:
            mock_validate.side_effect = Exception("Nexus connection failed")
            
            result = await orchestrator.check_package(
                package_name="requests",
                version="2.25.0",
                ecosystem="pypi",
                source_type="pypi"
            )
            
            # With fail_safe=True, should block
            assert result.allowed is False
            assert result.block_code == "NEXUS_ERROR"
            assert result.security_grade == "F"
    
    @pytest.mark.asyncio
    async def test_check_package_nexus_error_non_failsafe(self):
        """Test that Nexus error is allowed with fail_safe=False."""
        orchestrator = SecurityOrchestrator(fail_safe=False)
        
        with patch('src.output_security.engine.validate_package') as mock_validate:
            mock_validate.side_effect = Exception("Nexus connection failed")
            
            result = await orchestrator.check_package(
                package_name="requests",
                version="2.25.0",
                ecosystem="pypi",
                source_type="pypi"
            )
            
            # With fail_safe=False, should allow (degraded mode)
            assert result.allowed is True


class TestPhaseResults:
    """Test phase result handling."""
    
    def test_phase_result_to_dict(self):
        """Test PhaseResult serialization."""
        result = PhaseResult(
            phase=SecurityPhase.VULNERABILITY,
            passed=True,
            execution_time_ms=150.5,
            details={"vulnerability_count": 0}
        )
        
        d = result.to_dict()
        assert d["phase"] == "VULNERABILITY"
        assert d["passed"] is True
        assert d["execution_time_ms"] == 150.5
        assert d["details"]["vulnerability_count"] == 0
    
    def test_security_check_result_to_dict(self):
        """Test SecurityCheckResult serialization."""
        result = SecurityCheckResult(
            allowed=True,
            phase_results=[
                PhaseResult(
                    phase=SecurityPhase.NEXUS,
                    passed=True,
                    execution_time_ms=50.0,
                    details={}
                )
            ],
            total_execution_time_ms=200.0,
            security_grade="A",
            risk_level="NONE"
        )
        
        d = result.to_dict()
        assert d["allowed"] is True
        assert len(d["phase_results"]) == 1
        assert d["security_grade"] == "A"
        assert d["risk_level"] == "NONE"


class TestGetOrchestrator:
    """Test global orchestrator singleton."""
    
    def test_get_orchestrator_returns_same_instance(self):
        """Test that get_orchestrator returns the same instance."""
        import src.output_security.engine as engine
        
        # Reset global orchestrator
        engine._orchestrator = None
        
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        
        assert orch1 is orch2


class TestSecurityPhases:
    """Test SecurityPhase enum."""
    
    def test_all_phases_defined(self):
        """Test all security phases are defined."""
        assert SecurityPhase.NEXUS is not None
        assert SecurityPhase.VULNERABILITY is not None
        assert SecurityPhase.VERSION is not None
        assert SecurityPhase.DEPENDENCY is not None
        assert SecurityPhase.SANDBOX is not None
    
    def test_phase_order(self):
        """Test phases are in correct order."""
        phases = list(SecurityPhase)
        assert phases[0] == SecurityPhase.NEXUS
        assert phases[1] == SecurityPhase.VULNERABILITY
        assert phases[2] == SecurityPhase.VERSION
        assert phases[3] == SecurityPhase.DEPENDENCY
        assert phases[4] == SecurityPhase.SANDBOX


class TestEarlyTermination:
    """Test early termination behavior."""
    
    @pytest.mark.asyncio
    async def test_early_termination_on_nexus_block(self):
        """Test that early termination stops on Nexus block."""
        orchestrator = SecurityOrchestrator(
            enable_vuln_scan=True,
            enable_version_validation=True,
            early_termination=True,
            fail_safe=False
        )
        
        with patch('src.output_security.engine.validate_package') as mock_validate:
            with patch('src.output_security.engine.scan_package_cached') as mock_scan:
                # Nexus blocks
                mock_validate.return_value = ValidationResult(
                    approved=False,
                    block_code="BLOCKED",
                    reason="Blocked"
                )
                
                result = await orchestrator.check_package(
                    package_name="test",
                    version="1.0.0",
                    ecosystem="pypi",
                    source_type="pypi"
                )
                
                # Should not even try vulnerability scan
                mock_scan.assert_not_called()
                assert result.allowed is False


class TestErrorHandling:
    """Test error handling in orchestrator."""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_on_phase_failure(self):
        """Test graceful degradation when a phase fails."""
        orchestrator = SecurityOrchestrator(fail_safe=False)
        
        with patch('src.output_security.engine.validate_package') as mock_validate:
            mock_validate.return_value = ValidationResult(
                approved=True,
                block_code="",
                reason=""
            )
            
            # Vulnerability scan fails
            with patch('src.output_security.engine.scan_package_cached') as mock_scan:
                with patch('src.output_security.engine.settings') as mock_settings:
                    mock_settings.VULN_SCAN_ENABLED = True
                    mock_scan.side_effect = Exception("Vulnerability API down")
                    
                    result = await orchestrator.check_package(
                        package_name="requests",
                        version="2.25.0",
                        ecosystem="pypi",
                        source_type="pypi"
                    )
                    
                    # Should still allow (degraded mode)
                    assert result.allowed is True
                    # Check that error was recorded
                    assert any(p.error is not None for p in result.phase_results)


class TestIntegrationFlow:
    """Test complete integration flow."""
    
    @pytest.mark.asyncio
    async def test_full_security_flow(self):
        """Test complete security check flow."""
        orchestrator = SecurityOrchestrator(
            enable_vuln_scan=False,
            enable_version_validation=False,
            enable_dependency_scan=False,
            enable_sandbox=False,
            early_termination=True,
            fail_safe=True
        )
        
        with patch('src.output_security.engine.validate_package') as mock_validate:
            mock_validate.return_value = ValidationResult(
                approved=True,
                block_code="",
                reason=""
            )
            
            result = await orchestrator.check_package(
                package_name="requests",
                version="2.25.0",
                ecosystem="pypi",
                source_type="pypi"
            )
            
            assert result.allowed is True
            assert result.security_grade == "A"
            assert result.risk_level == "NONE"
            assert len(result.phase_results) == 1
            assert result.total_execution_time_ms > 0


class TestCodeSandboxIntegration:
    """Test code sandbox integration."""
    
    @pytest.mark.asyncio
    async def test_check_code_when_disabled(self):
        """Test check_code when sandbox is disabled."""
        orchestrator = SecurityOrchestrator(
            enable_sandbox=False,
            fail_safe=True
        )
        
        result = await orchestrator.check_code(
            code="print('hello')",
            language="python"
        )
        
        assert result.allowed is True
        assert result.metadata.get("sandbox_disabled") is True


class TestBackwardCompatibility:
    """Test backward compatibility with legacy interface."""
    
    @pytest.mark.asyncio
    async def test_legacy_check_function(self):
        """Test legacy check() function works."""
        from src.output_security.engine import check
        
        with patch('src.output_security.engine.extract_code_blocks') as mock_extract:
            mock_extract.return_value = []
            
            result = await check("No code here")
            
            assert result.allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
