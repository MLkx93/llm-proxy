"""
Output Security Engine.

Inspects LLM responses before they are returned to the client.
Orchestrates all 4 security phases for comprehensive protection:

Phase 1: Vulnerability Scanning (OSV/CVE databases)
Phase 2: Version Validation (specific version checks)
Phase 3: Dependency Tree Analysis (transitive dependencies)
Phase 4: Code Sandbox Validation (behavioral analysis)

Fail-closed: any unvalidated or unsafe dependency blocks the response.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import asyncio

from .code_parser import extract_code_blocks, CodeBlock
from .nexus import validate_package, ValidationResult
from .vulnerability_scanner import (
    scan_package_cached,
    should_block_package,
    VulnerabilityReport,
)
from .version_validator import validate_package_version
from .security_advisory import SecurityAdvisoryDatabase
from .dependency_resolver import (
    analyze_package_health,
    DependencyAnalysisResult,
)
from .sandbox import (
    analyze_code_sandbox,
    SandboxResult,
    SandboxStatus,
)
from .detection_rules import scan_with_default_rules, RuleViolation
from .risk_scorer import (
    assess_code_risk,
    RiskAssessment,
    RiskLevel,
)
from src.proxy.logging import get_logger
from config.settings import settings

logger = get_logger("output_security")


class SecurityPhase(Enum):
    """Security phases in execution order."""
    NEXUS = "NEXUS"
    VULNERABILITY = "VULNERABILITY"
    VERSION = "VERSION"
    DEPENDENCY = "DEPENDENCY"
    SANDBOX = "SANDBOX"


@dataclass
class PhaseResult:
    """Result from a single security phase."""
    phase: SecurityPhase
    passed: bool
    execution_time_ms: float
    details: Dict = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "phase": self.phase.value,
            "passed": self.passed,
            "execution_time_ms": self.execution_time_ms,
            "details": self.details,
            "error": self.error
        }


@dataclass
class SecurityCheckResult:
    """Complete result from all security checks."""
    allowed: bool
    block_code: str = ""
    block_reason: str = ""
    blocked_packages: List[str] = field(default_factory=list)
    phase_results: List[PhaseResult] = field(default_factory=list)
    total_execution_time_ms: float = 0.0
    security_grade: str = "A"
    risk_level: str = "NONE"
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "block_code": self.block_code,
            "block_reason": self.block_reason,
            "blocked_packages": self.blocked_packages,
            "phase_results": [p.to_dict() for p in self.phase_results],
            "total_execution_time_ms": self.total_execution_time_ms,
            "security_grade": self.security_grade,
            "risk_level": self.risk_level,
            "metadata": self.metadata
        }


@dataclass
class OutputPolicyResult:
    """Legacy result format for backward compatibility."""
    allowed: bool
    block_code: str = ""
    block_reason: str = ""
    blocked_packages: list[str] = field(default_factory=list)


class SecurityOrchestrator:
    """
    Orchestrates all security phases for comprehensive LLM response validation.
    
    Execution order:
    1. Nexus validation (repository check)
    2. Phase 1: Vulnerability scanning (if enabled)
    3. Phase 2: Version validation (if enabled)
    4. Phase 3: Dependency tree analysis (if enabled)
    5. Phase 4: Sandbox validation (if enabled)
    
    Early termination on blocking result (configurable).
    """
    
    def __init__(
        self,
        enable_vuln_scan: bool = True,
        enable_version_validation: bool = True,
        enable_dependency_scan: bool = True,
        enable_sandbox: bool = True,
        early_termination: bool = True,
        fail_safe: bool = True,
    ):
        self.enable_vuln_scan = enable_vuln_scan
        self.enable_version_validation = enable_version_validation
        self.enable_dependency_scan = enable_dependency_scan
        self.enable_sandbox = enable_sandbox
        self.early_termination = early_termination
        self.fail_safe = fail_safe
        self._advisory_db: Optional[SecurityAdvisoryDatabase] = None
    
    async def _get_advisory_db(self) -> SecurityAdvisoryDatabase:
        """Get or create advisory database."""
        if self._advisory_db is None:
            self._advisory_db = SecurityAdvisoryDatabase()
        return self._advisory_db
    
    async def check_package(
        self,
        package_name: str,
        version: str,
        ecosystem: str,
        source_type: str
    ) -> SecurityCheckResult:
        """Run all security checks on a single package."""
        start_time = datetime.now()
        phase_results: List[PhaseResult] = []
        
        # Phase 0: Nexus validation
        nexus_start = datetime.now()
        try:
            nexus_result: ValidationResult = await validate_package(package_name, source_type)
            nexus_time = (datetime.now() - nexus_start).total_seconds() * 1000
            
            if not nexus_result.approved:
                return SecurityCheckResult(
                    allowed=False,
                    block_code=nexus_result.block_code,
                    block_reason=nexus_result.reason,
                    blocked_packages=[package_name],
                    phase_results=[PhaseResult(
                        phase=SecurityPhase.NEXUS,
                        passed=False,
                        execution_time_ms=nexus_time,
                        details={"approved": False}
                    )],
                    total_execution_time_ms=nexus_time,
                    security_grade="F",
                    risk_level="CRITICAL"
                )
            
            phase_results.append(PhaseResult(
                phase=SecurityPhase.NEXUS,
                passed=True,
                execution_time_ms=nexus_time,
                details={"approved": True}
            ))
        except Exception as e:
            logger.error("nexus_validation_error", extra={"error": str(e)})
            if self.fail_safe:
                return SecurityCheckResult(
                    allowed=False,
                    block_code="NEXUS_ERROR",
                    block_reason=f"Nexus validation failed: {str(e)}",
                    blocked_packages=[package_name],
                    phase_results=[PhaseResult(
                        phase=SecurityPhase.NEXUS,
                        passed=False,
                        execution_time_ms=0,
                        error=str(e)
                    )],
                    security_grade="F",
                    risk_level="CRITICAL"
                )
        
        # Phase 1: Vulnerability scanning
        if self.enable_vuln_scan and settings.VULN_SCAN_ENABLED:
            vuln_start = datetime.now()
            try:
                vuln_report: VulnerabilityReport = await scan_package_cached(
                    package=package_name,
                    ecosystem=ecosystem
                )
                vuln_time = (datetime.now() - vuln_start).total_seconds() * 1000
                
                should_block, reason = should_block_package(
                    vuln_report,
                    min_severity=settings.VULN_MIN_SEVERITY
                )
                
                phase_results.append(PhaseResult(
                    phase=SecurityPhase.VULNERABILITY,
                    passed=not should_block,
                    execution_time_ms=vuln_time,
                    details={
                        "vulnerability_count": vuln_report.vulnerability_count,
                        "highest_severity": vuln_report.highest_severity,
                        "highest_cvss": vuln_report.highest_cvss
                    }
                ))
                
                if should_block:
                    return SecurityCheckResult(
                        allowed=False,
                        block_code="BLOCKED_VULNERABLE_PACKAGE",
                        block_reason=reason,
                        blocked_packages=[package_name],
                        phase_results=phase_results,
                        total_execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        security_grade="F",
                        risk_level="CRITICAL"
                    )
            except Exception as e:
                logger.error("vulnerability_scan_error", extra={"error": str(e)})
                phase_results.append(PhaseResult(
                    phase=SecurityPhase.VULNERABILITY,
                    passed=False,
                    execution_time_ms=(datetime.now() - vuln_start).total_seconds() * 1000,
                    details={},
                    error=str(e)
                ))
                if self.fail_safe:
                    return SecurityCheckResult(
                        allowed=False,
                        block_code="VULN_SCAN_ERROR",
                        block_reason=f"Vulnerability scan failed: {str(e)}",
                        blocked_packages=[package_name],
                        phase_results=phase_results,
                        security_grade="F",
                        risk_level="HIGH"
                    )
        
        # Phase 2: Version validation
        if self.enable_version_validation and settings.VERSION_VALIDATION_ENABLED:
            version_start = datetime.now()
            try:
                db = await self._get_advisory_db()
                version_result = await validate_package_version(package_name, version, ecosystem, db)
                version_time = (datetime.now() - version_start).total_seconds() * 1000
                
                phase_results.append(PhaseResult(
                    phase=SecurityPhase.VERSION,
                    passed=not version_result["is_vulnerable"],
                    execution_time_ms=version_time,
                    details={
                        "is_vulnerable": version_result["is_vulnerable"],
                        "advisories_found": len(version_result.get("advisories", []))
                    }
                ))
                
                if version_result["is_vulnerable"]:
                    advisories = version_result.get("advisories", [])
                    reason = f"Vulnerable version. {len(advisories)} advisory(ies) found."
                    return SecurityCheckResult(
                        allowed=False,
                        block_code="BLOCKED_VULNERABLE_VERSION",
                        block_reason=reason,
                        blocked_packages=[package_name],
                        phase_results=phase_results,
                        total_execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        security_grade="F",
                        risk_level="HIGH"
                    )
            except Exception as e:
                logger.error("version_validation_error", extra={"error": str(e)})
                if self.fail_safe:
                    return SecurityCheckResult(
                        allowed=False,
                        block_code="VERSION_VALIDATION_ERROR",
                        block_reason=f"Version validation failed: {str(e)}",
                        blocked_packages=[package_name],
                        phase_results=phase_results,
                        security_grade="F",
                        risk_level="MEDIUM"
                    )
        
        # Phase 3: Dependency tree analysis
        if self.enable_dependency_scan and settings.DEPENDENCY_SCAN_ENABLED:
            dep_start = datetime.now()
            try:
                dep_result: DependencyAnalysisResult = analyze_package_health(
                    package_name, version, ecosystem
                )
                dep_time = (datetime.now() - dep_start).total_seconds() * 1000
                
                phase_results.append(PhaseResult(
                    phase=SecurityPhase.DEPENDENCY,
                    passed=dep_result.security_grade not in ["D", "F"],
                    execution_time_ms=dep_time,
                    details={
                        "security_grade": dep_result.security_grade,
                        "vulnerabilities_found": dep_result.vulnerabilities_found,
                        "risk_score": dep_result.risk_score
                    }
                ))
                
                if dep_result.security_grade in ["D", "F"]:
                    return SecurityCheckResult(
                        allowed=False,
                        block_code="BLOCKED_DEPENDENCY_VULNERABILITY",
                        block_reason=f"Dependency tree has {dep_result.vulnerabilities_found} vulnerabilities",
                        blocked_packages=[package_name],
                        phase_results=phase_results,
                        total_execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        security_grade=dep_result.security_grade,
                        risk_level="HIGH" if dep_result.security_grade == "D" else "CRITICAL"
                    )
            except Exception as e:
                logger.error("dependency_scan_error", extra={"error": str(e)})
                if self.fail_safe:
                    return SecurityCheckResult(
                        allowed=False,
                        block_code="DEPENDENCY_SCAN_ERROR",
                        block_reason=f"Dependency scan failed: {str(e)}",
                        blocked_packages=[package_name],
                        phase_results=phase_results,
                        security_grade="F",
                        risk_level="MEDIUM"
                    )
        
        # All phases passed
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        return SecurityCheckResult(
            allowed=True,
            phase_results=phase_results,
            total_execution_time_ms=total_time,
            security_grade="A",
            risk_level="NONE"
        )
    
    async def check_code(self, code: str, language: str = "python") -> SecurityCheckResult:
        """Run sandbox validation on code."""
        start_time = datetime.now()
        phase_results: List[PhaseResult] = []
        
        if not self.enable_sandbox or not settings.SANDBOX_ENABLED:
            return SecurityCheckResult(
                allowed=True,
                phase_results=[],
                total_execution_time_ms=0,
                security_grade="N/A",
                risk_level="NONE",
                metadata={"sandbox_disabled": True}
            )
        
        sandbox_start = datetime.now()
        try:
            sandbox_result: SandboxResult = await analyze_code_sandbox(
                code,
                language=language,
                risk_threshold=settings.SANDBOX_RISK_THRESHOLD,
                block_on_high_risk=True
            )
            sandbox_time = (datetime.now() - sandbox_start).total_seconds() * 1000
            
            violations: List[RuleViolation] = scan_with_default_rules(code)
            risk_assessment: RiskAssessment = await assess_code_risk(
                code,
                sandbox_result=sandbox_result,
                violations=violations,
                block_threshold=settings.SANDBOX_RISK_THRESHOLD
            )
            
            phase_results.append(PhaseResult(
                phase=SecurityPhase.SANDBOX,
                passed=sandbox_result.status != SandboxStatus.BLOCKED,
                execution_time_ms=sandbox_time,
                details={
                    "status": sandbox_result.status.value,
                    "risk_score": sandbox_result.risk_score,
                    "security_grade": sandbox_result.security_grade,
                    "violation_count": len(violations),
                    "behavior_count": len(sandbox_result.behaviors)
                }
            ))
            
            total_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if sandbox_result.status == SandboxStatus.BLOCKED:
                return SecurityCheckResult(
                    allowed=False,
                    block_code="BLOCKED_SANDBOX",
                    block_reason=sandbox_result.blocked_reason or "Sandbox detected high-risk patterns",
                    phase_results=phase_results,
                    total_execution_time_ms=total_time,
                    security_grade=sandbox_result.security_grade,
                    risk_level="HIGH" if sandbox_result.risk_score < 8 else "CRITICAL"
                )
            
            return SecurityCheckResult(
                allowed=True,
                phase_results=phase_results,
                total_execution_time_ms=total_time,
                security_grade=sandbox_result.security_grade,
                risk_level=risk_assessment.risk_level.value
            )
        
        except Exception as e:
            logger.error("sandbox_error", extra={"error": str(e)})
            if self.fail_safe:
                return SecurityCheckResult(
                    allowed=False,
                    block_code="SANDBOX_ERROR",
                    block_reason=f"Sandbox execution failed: {str(e)}",
                    phase_results=phase_results,
                    security_grade="F",
                    risk_level="HIGH"
                )
            return SecurityCheckResult(
                allowed=True,
                phase_results=phase_results,
                total_execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                security_grade="B",
                risk_level="LOW",
                metadata={"sandbox_error": str(e)}
            )


_orchestrator: Optional[SecurityOrchestrator] = None


def get_orchestrator() -> SecurityOrchestrator:
    """Get or create the global security orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SecurityOrchestrator(
            enable_vuln_scan=settings.VULN_SCAN_ENABLED,
            enable_version_validation=settings.VERSION_VALIDATION_ENABLED,
            enable_dependency_scan=settings.DEPENDENCY_SCAN_ENABLED,
            enable_sandbox=settings.SANDBOX_ENABLED,
        )
    return _orchestrator


async def check(response_text: str) -> OutputPolicyResult:
    """Run output security checks on the LLM response text."""
    orchestrator = get_orchestrator()
    blocks = extract_code_blocks(response_text)

    if not blocks:
        return OutputPolicyResult(allowed=True)

    for block in blocks:
        if not block.dependencies:
            if block.code and settings.SANDBOX_ENABLED:
                code_result = await orchestrator.check_code(block.code, block.language)
                if not code_result.allowed:
                    return OutputPolicyResult(
                        allowed=False,
                        block_code=code_result.block_code,
                        block_reason=code_result.block_reason,
                    )
            continue

        for dep in block.dependencies:
            result = await orchestrator.check_package(
                package_name=dep.name,
                version=dep.version or "unknown",
                ecosystem=dep.source_type,
                source_type=dep.source_type
            )
            
            if not result.allowed:
                return OutputPolicyResult(
                    allowed=False,
                    block_code=result.block_code,
                    block_reason=result.block_reason,
                    blocked_packages=result.blocked_packages,
                )

    return OutputPolicyResult(allowed=True)


async def check_full(response_text: str) -> SecurityCheckResult:
    """Run full security checks on LLM response."""
    orchestrator = get_orchestrator()
    blocks = extract_code_blocks(response_text)
    all_results: List[SecurityCheckResult] = []
    all_phase_results: List[PhaseResult] = []
    start_time = datetime.now()

    if not blocks:
        return SecurityCheckResult(
            allowed=True,
            total_execution_time_ms=0,
            security_grade="A",
            risk_level="NONE"
        )

    for block in blocks:
        if block.code and settings.SANDBOX_ENABLED:
            code_result = await orchestrator.check_code(block.code, block.language)
            all_phase_results.extend(code_result.phase_results)
            if not code_result.allowed:
                return code_result

        if block.dependencies:
            for dep in block.dependencies:
                result = await orchestrator.check_package(
                    package_name=dep.name,
                    version=dep.version or "unknown",
                    ecosystem=dep.source_type,
                    source_type=dep.source_type
                )
                all_phase_results.extend(result.phase_results)
                if not result.allowed:
                    all_results.append(result)
                    if orchestrator.early_termination:
                        break
            else:
                continue
            if orchestrator.early_termination:
                break

    if all_results:
        return all_results[0]
    
    return SecurityCheckResult(
        allowed=True,
        phase_results=all_phase_results,
        total_execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        security_grade="A",
        risk_level="NONE"
    )


def extract_response_text(llm_response: dict) -> str:
    """Pull the assistant message content from a LiteLLM/OpenAI response dict."""
    try:
        return llm_response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def extract_response_text_anthropic(response: dict) -> str:
    """Pull text from an Anthropic Messages API response dict."""
    try:
        parts = []
        for block in response.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    except (TypeError, AttributeError):
        return ""
