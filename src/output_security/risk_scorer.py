"""
Risk Scoring Module (Phase 4).

Provides comprehensive risk scoring and aggregation logic for code security analysis.
Combines outputs from sandbox execution and detection rules to generate overall
risk assessments.

This module implements:
- Weighted risk calculation across multiple factors
- Configurable thresholds for blocking
- Risk level categorization
- Risk aggregation for analysis pipelines
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import json

from .sandbox import SandboxResult, SandboxStatus, BehaviorEvent, BehaviorType
from .detection_rules import RuleSet, RuleViolation
from src.proxy.logging import get_logger

logger = get_logger("risk_scorer")


class RiskLevel(Enum):
    """Risk level categories."""
    CRITICAL = "CRITICAL"  # Score 8-10
    HIGH = "HIGH"          # Score 6-8
    MEDIUM = "MEDIUM"      # Score 4-6
    LOW = "LOW"            # Score 2-4
    NONE = "NONE"          # Score 0-2


@dataclass
class RiskFactor:
    """Individual risk factor contributing to overall score."""
    name: str
    value: float
    weight: float
    category: str
    details: Optional[Dict] = None
    
    @property
    def contribution(self) -> float:
        """Calculate weighted contribution."""
        return self.value * self.weight


@dataclass
class RiskAssessment:
    """Complete risk assessment result."""
    overall_score: float
    risk_level: RiskLevel
    factors: List[RiskFactor] = field(default_factory=list)
    should_block: bool = False
    block_reason: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    @property
    def grade(self) -> str:
        """Get letter grade."""
        if self.overall_score >= 8.0:
            return "F"
        elif self.overall_score >= 6.0:
            return "D"
        elif self.overall_score >= 4.0:
            return "C"
        elif self.overall_score >= 2.0:
            return "B"
        else:
            return "A"
    
    def to_dict(self) -> Dict:
        return {
            "overall_score": self.overall_score,
            "risk_level": self.risk_level.value,
            "grade": self.grade,
            "should_block": self.should_block,
            "block_reason": self.block_reason,
            "recommendations": self.recommendations,
            "execution_time_ms": self.execution_time_ms,
            "factors": [
                {
                    "name": f.name,
                    "value": f.value,
                    "weight": f.weight,
                    "contribution": f.contribution,
                    "category": f.category
                }
                for f in self.factors
            ],
            "metadata": self.metadata
        }


class RiskScorer:
    """
    Calculates risk scores based on multiple factors.
    
    Supports configurable weights and thresholds.
    """
    
    # Default weights for each factor
    DEFAULT_WEIGHTS = {
        "sandbox_risk": 0.3,
        "detection_violations": 0.25,
        "execution_status": 0.2,
        "behavior_severity": 0.15,
        "pattern_complexity": 0.1
    }
    
    # Severity mappings
    SEVERITY_LEVELS = {
        "CRITICAL": 10.0,
        "HIGH": 7.0,
        "MEDIUM": 4.0,
        "LOW": 2.0,
        "NONE": 0.0
    }
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        block_threshold: float = 6.0,
        critical_severity: float = 8.0
    ):
        """
        Initialize risk scorer.
        
        Args:
            weights: Custom weights for risk factors
            block_threshold: Score above which to block
            critical_severity: Score for CRITICAL risk level
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.block_threshold = block_threshold
        self.critical_severity = critical_severity
    
    def calculate(
        self,
        sandbox_result: Optional[SandboxResult] = None,
        violations: Optional[List[RuleViolation]] = None,
        additional_factors: Optional[List[RiskFactor]] = None
    ) -> RiskAssessment:
        """
        Calculate comprehensive risk assessment.
        
        Args:
            sandbox_result: Result from sandbox execution
            violations: Rule violations from detection
            additional_factors: Custom risk factors
        
        Returns:
            RiskAssessment with complete analysis
        """
        factors: List[RiskFactor] = []
        start_time = datetime.now()
        
        # Sandbox risk factor
        sandbox_risk = 0.0
        if sandbox_result:
            sandbox_risk = sandbox_result.risk_score
            factors.append(RiskFactor(
                name="sandbox_risk",
                value=sandbox_risk,
                weight=self.weights.get("sandbox_risk", 0.3),
                category="execution",
                details={
                    "status": sandbox_result.status.value,
                    "behavior_count": len(sandbox_result.behaviors)
                }
            ))
        
        # Detection violations factor
        violation_score = 0.0
        if violations:
            violation_score = self._calculate_violation_score(violations)
            factors.append(RiskFactor(
                name="detection_violations",
                value=violation_score,
                weight=self.weights.get("detection_violations", 0.25),
                category="rule_violations",
                details={
                    "count": len(violations),
                    "categories": list(set(v.category.value for v in violations))
                }
            ))
        
        # Execution status factor
        status_score = 0.0
        if sandbox_result:
            status_score = self._calculate_status_score(sandbox_result.status)
            factors.append(RiskFactor(
                name="execution_status",
                value=status_score,
                weight=self.weights.get("execution_status", 0.2),
                category="execution",
                details={"status": sandbox_result.status.value}
            ))
        
        # Behavior severity factor
        behavior_score = 0.0
        if sandbox_result and sandbox_result.behaviors:
            behavior_score = self._calculate_behavior_score(sandbox_result.behaviors)
            factors.append(RiskFactor(
                name="behavior_severity",
                value=behavior_score,
                weight=self.weights.get("behavior_severity", 0.15),
                category="behaviors",
                details={
                    "behavior_types": [b.behavior_type.value for b in sandbox_result.behaviors],
                    "max_severity": max(b.severity for b in sandbox_result.behaviors)
                }
            ))
        
        # Pattern complexity factor
        complexity_score = 0.0
        if violations:
            complexity_score = self._calculate_complexity_score(violations)
            factors.append(RiskFactor(
                name="pattern_complexity",
                value=complexity_score,
                weight=self.weights.get("pattern_complexity", 0.1),
                category="pattern_analysis",
                details={"unique_patterns": len(set(v.rule.id for v in violations))}
            ))
        
        # Add additional factors
        if additional_factors:
            factors.extend(additional_factors)
        
        # Calculate overall score
        overall_score = sum(f.contribution for f in factors)
        overall_score = min(overall_score, 10.0)  # Cap at 10
        
        # Determine risk level
        risk_level = self._get_risk_level(overall_score)
        
        # Determine if should block
        should_block = overall_score >= self.block_threshold
        block_reason = None
        if should_block:
            block_reason = self._generate_block_reason(
                factors, overall_score, violations, sandbox_result
            )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            factors, violations, sandbox_result
        )
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return RiskAssessment(
            overall_score=overall_score,
            risk_level=risk_level,
            factors=factors,
            should_block=should_block,
            block_reason=block_reason,
            recommendations=recommendations,
            execution_time_ms=execution_time,
            metadata={
                "sandbox_available": sandbox_result is not None,
                "violation_count": len(violations) if violations else 0,
                "behavior_count": len(sandbox_result.behaviors) if sandbox_result else 0
            }
        )
    
    def _calculate_violation_score(
        self,
        violations: List[RuleViolation]
    ) -> float:
        """Calculate score from rule violations."""
        if not violations:
            return 0.0
        
        score = 0.0
        for v in violations:
            if not v.false_positive:
                # Weight by match count (cap at 5)
                weight = min(v.match_count, 5)
                score += v.rule.severity * (1 + (weight - 1) * 0.2)
        
        return min(score, 10.0)
    
    def _calculate_status_score(self, status: SandboxStatus) -> float:
        """Calculate score from execution status."""
        status_scores = {
            SandboxStatus.COMPLETED: 0.0,
            SandboxStatus.PENDING: 0.5,
            SandboxStatus.RUNNING: 1.0,
            SandboxStatus.ERROR: 2.0,
            SandboxStatus.TIMEOUT: 3.0,
            SandboxStatus.BLOCKED: 5.0
        }
        return status_scores.get(status, 0.0)
    
    def _calculate_behavior_score(
        self,
        behaviors: List[BehaviorEvent]
    ) -> float:
        """Calculate score from behavior events."""
        if not behaviors:
            return 0.0
        
        # Sum max severity behaviors
        max_by_type: Dict[BehaviorType, int] = {}
        for b in behaviors:
            if b.behavior_type not in max_by_type:
                max_by_type[b.behavior_type] = b.severity
            else:
                max_by_type[b.behavior_type] = max(max_by_type[b.behavior_type], b.severity)
        
        return min(sum(max_by_type.values()), 10.0)
    
    def _calculate_complexity_score(
        self,
        violations: List[RuleViolation]
    ) -> float:
        """Calculate score based on pattern complexity."""
        if not violations:
            return 0.0
        
        # Multiple categories = higher complexity = higher risk
        categories = set(v.rule.category for v in violations)
        unique_patterns = len(set(v.rule.id for v in violations))
        
        # Base score from unique patterns
        score = unique_patterns * 0.5
        
        # Bonus for multiple categories
        if len(categories) > 2:
            score += len(categories) * 0.3
        
        return min(score, 10.0)
    
    def _get_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score."""
        if score >= 8.0:
            return RiskLevel.CRITICAL
        elif score >= 6.0:
            return RiskLevel.HIGH
        elif score >= 4.0:
            return RiskLevel.MEDIUM
        elif score >= 2.0:
            return RiskLevel.LOW
        else:
            return RiskLevel.NONE
    
    def _generate_block_reason(
        self,
        factors: List[RiskFactor],
        score: float,
        violations: Optional[List[RuleViolation]],
        sandbox_result: Optional[SandboxResult]
    ) -> str:
        """Generate human-readable block reason."""
        reasons = []
        
        # Check critical factors
        for f in factors:
            if f.value >= 8.0:
                reasons.append(f"{f.name} (score: {f.value:.1f})")
        
        # Check for specific violations
        if violations:
            high_severity = [v for v in violations if v.rule.severity >= 8]
            if high_severity:
                reasons.append(
                    f"High-severity violations: {', '.join(v.rule.name for v in high_severity[:3])}"
                )
        
        # Check sandbox status
        if sandbox_result and sandbox_result.status == SandboxStatus.TIMEOUT:
            reasons.append("Execution timeout")
        
        if not reasons:
            reasons.append(f"Overall risk score {score:.1f} exceeds threshold {self.block_threshold}")
        
        return "; ".join(reasons)
    
    def _generate_recommendations(
        self,
        factors: List[RiskFactor],
        violations: Optional[List[RuleViolation]],
        sandbox_result: Optional[SandboxResult]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Check for specific issues
        if violations:
            # Shell execution
            shell_violations = [
                v for v in violations
                if v.rule.category.value == "PROCESS"
                and v.rule.severity >= 7
            ]
            if shell_violations:
                recommendations.append(
                    "Avoid using shell execution (os.system, subprocess). "
                    "Use safer alternatives like library functions."
                )
            
            # Network access
            network_violations = [
                v for v in violations
                if v.rule.category.value == "NETWORK"
            ]
            if network_violations:
                recommendations.append(
                    "Consider removing or restricting network access. "
                    "Verify external connections are necessary and secure."
                )
            
            # File system access
            fs_violations = [
                v for v in violations
                if v.rule.category.value == "FILE_SYSTEM"
            ]
            if fs_violations:
                recommendations.append(
                    "Review file operations. Ensure write operations "
                    "are restricted to safe directories."
                )
        
        # Sandbox recommendations
        if sandbox_result:
            if sandbox_result.status == SandboxStatus.TIMEOUT:
                recommendations.append(
                    "Optimize code to reduce execution time. "
                    "Consider breaking complex operations into smaller steps."
                )
            
            behaviors = sandbox_result.behaviors
            if any(b.behavior_type == BehaviorType.SHELL_EXECUTION for b in behaviors):
                recommendations.append(
                    "Shell execution detected. This pattern is often "
                    "associated with malicious code. Review the code purpose."
                )
        
        if not recommendations:
            recommendations.append("Code appears safe to execute.")
        
        return recommendations


# Global scorer instance
_scorer: Optional[RiskScorer] = None


def get_scorer(
    weights: Optional[Dict[str, float]] = None,
    block_threshold: float = 6.0
) -> RiskScorer:
    """Get or create the global risk scorer."""
    global _scorer
    if _scorer is None or weights is not None:
        _scorer = RiskScorer(weights=weights, block_threshold=block_threshold)
    return _scorer


async def assess_code_risk(
    code: str,
    sandbox_result: Optional[SandboxResult] = None,
    violations: Optional[List[RuleViolation]] = None,
    block_threshold: float = 6.0
) -> RiskAssessment:
    """
    Quick assessment combining multiple sources.
    
    Args:
        code: Code being analyzed
        sandbox_result: Optional sandbox result
        violations: Optional rule violations
        block_threshold: Threshold for blocking
    
    Returns:
        RiskAssessment with complete analysis
    """
    scorer = get_scorer(block_threshold=block_threshold)
    return scorer.calculate(sandbox_result, violations)
