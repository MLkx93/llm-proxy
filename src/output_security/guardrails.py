"""
Guardrails Module (Phase 5).

Provides LLM-specific guardrails for enhanced safety beyond traditional security checks.
Implements toxicity detection, hallucination detection, prompt leakage detection,
and other safety checks for LLM responses.

This module extends the security pipeline with:
- Toxicity detection using multiple approaches
- Hallucination detection for factual consistency
- Prompt leakage prevention
- Content safety scoring
- Configurable guardrail thresholds
"""
import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
from datetime import datetime
import hashlib

from src.proxy.logging import get_logger

logger = get_logger("guardrails")


class GuardrailCategory(Enum):
    """Categories of guardrails."""
    TOXICITY = "TOXICITY"
    HALLUCINATION = "HALLUCINATION"
    PROMPT_LEAKAGE = "PROMPT_LEAKAGE"
    CONTENT_SAFETY = "CONTENT_SAFETY"
    BIAS = "BIAS"
    MALICIOUS_CODE = "MALICIOUS_CODE"


class RiskLevel(Enum):
    """Risk levels for guardrail violations."""
    CRITICAL = "CRITICAL"  # Must block
    HIGH = "HIGH"          # Should block
    MEDIUM = "MEDIUM"      # Should warn
    LOW = "LOW"            # Monitor
    NONE = "NONE"

    def __lt__(self, other):
        if not isinstance(other, RiskLevel):
            return NotImplemented
        # Define order: NONE < LOW < MEDIUM < HIGH < CRITICAL
        order = [RiskLevel.NONE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return order.index(self) < order.index(other)

    def __le__(self, other):
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self < other or self == other

    def __gt__(self, other):
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return not self <= other

    def __ge__(self, other):
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return not self < other


@dataclass
class GuardrailResult:
    """Result of a single guardrail check."""
    category: GuardrailCategory
    passed: bool
    risk_level: RiskLevel
    score: float  # 0-10 scale
    details: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "category": self.category.value,
            "passed": self.passed,
            "risk_level": self.risk_level.value,
            "score": self.score,
            "details": self.details,
            "recommendations": self.recommendations
        }


@dataclass
class GuardrailsAssessment:
    """Complete guardrails assessment."""
    overall_passed: bool
    overall_risk: RiskLevel
    score: float
    category_results: List[GuardrailResult] = field(default_factory=list)
    execution_time_ms: float = 0.0
    summary: str = ""
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "overall_passed": self.overall_passed,
            "overall_risk": self.overall_risk.value,
            "score": self.score,
            "category_results": [r.to_dict() for r in self.category_results],
            "execution_time_ms": self.execution_time_ms,
            "summary": self.summary,
            "metadata": self.metadata
        }


class ToxicityChecker:
    """Detects toxic content in text responses."""

    # Toxicity patterns (simplified approach)
    TOXIC_PATTERNS = [
        # Hate speech
        (r"\b(hate|bigot|prejudice|xenophobia|racism|sexism|homophobia|transphobia)\b", 8.0),
        # Profanity
        (r"\b(fuck|shit|bitch|bastard|damn|hell)\b", 6.0),
        # Threats
        (r"\b(threaten|kill|violence|harm|shoot|attack|murder|bomb)\b", 9.0),
        # Harassment
        (r"\b(harass|bully|torment|abuse|slur|insult)\b", 7.0),
        # Self-harm
        (r"\b(suicide|self-harm|kill myself|hurt myself|dead)\b", 10.0),
    ]

    def __init__(self, threshold: float = 5.0):
        self.threshold = threshold

    def check(self, text: str) -> GuardrailResult:
        """Check for toxicity in text."""
        score = 0.0
        matches = []

        for pattern, severity in self.TOXIC_PATTERNS:
            matches_pattern = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches_pattern:
                score += severity
                matches.append({
                    "pattern": pattern,
                    "text": match.group(),
                    "severity": severity
                })

        # Normalize score (max 10)
        score = min(score, 10.0)

        # Determine risk level
        if score >= 8.0:
            risk_level = RiskLevel.CRITICAL
        elif score >= 6.0:
            risk_level = RiskLevel.HIGH
        elif score >= 4.0:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        passed = score < self.threshold

        return GuardrailResult(
            category=GuardrailCategory.TOXICITY,
            passed=passed,
            risk_level=risk_level,
            score=score,
            details={"matches": matches},
            recommendations=[
                f"Detected {len(matches)} potentially toxic patterns"
                if matches else "No toxic patterns detected"
            ]
        )


class HallucinationChecker:
    """Detects potential hallucinations in LLM responses."""

    # Factual consistency markers
    CONTRADICTION_PATTERNS = [
        (r"I'm not sure|uncertain|possibly|might be", 0.5),
        (r"I don't know|I'm not sure about that", 1.0),
        (r"according to my knowledge|based on my training", 0.3),
        (r"as far as I know|to my understanding", 0.4),
        (r"I could be wrong|this might not be accurate", 0.7),
    ]

    # Overconfidence indicators
    OVERCONFIDENT_PATTERNS = [
        (r"definitely|absolutely|certainly|without a doubt", 0.3),
        (r"100%|guaranteed|prove", 0.5),
        (r"everyone knows|obviously|clearly", 0.6),
    ]

    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold

    def check(self, text: str) -> GuardrailResult:
        """Check for potential hallucinations."""
        contradiction_score = 0.0
        overconfidence_score = 0.0

        # Check contradictions
        for pattern, weight in self.CONTRADICTION_PATTERNS:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            contradiction_score += matches * weight

        # Check overconfidence
        for pattern, weight in self.OVERCONFIDENT_PATTERNS:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            overconfidence_score += matches * weight

        # Combine scores
        score = contradiction_score + overconfidence_score
        score = min(score, 10.0)

        # Determine risk level
        if score >= 6.0:
            risk_level = RiskLevel.HIGH
        elif score >= 4.0:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        passed = score < self.threshold

        return GuardrailResult(
            category=GuardrailCategory.HALLUCINATION,
            passed=passed,
            risk_level=risk_level,
            score=score,
            details={
                "contradiction_score": round(contradiction_score, 2),
                "overconfidence_score": round(overconfidence_score, 2)
            },
            recommendations=[
                "Response shows potential contradictions"
                if contradiction_score > 1.0 else "No significant contradictions detected"
            ]
        )


class PromptLeakageChecker:
    """Detects when LLM reveals system prompts or internal information."""

    # Prompt leakage patterns
    LEAKAGE_PATTERNS = [
        # System prompt references
        (r"You are\s+(an AI assistant|a language model|trained by|created by)", 5.0),
        (r"I cannot\s+(tell you|reveal|disclose)(?:\s+that)", 4.0),
        (r"(I'm|I'm sorry|as an AI|due to policy|by design)", 0.5),

        # Training data references
        (r"my training data|I was trained on|training data|database", 6.0),
        (r"(I don't have|I don't know)\s+(about|access to)", 3.0),

        # System capabilities
        (r"\b(processing|analyzing|thinking|deciding|generating)\s+step", 2.0),
        (r"Please note that|Note that|It's important to", 1.0),
    ]

    def __init__(self, threshold: float = 4.0):
        self.threshold = threshold

    def check(self, text: str) -> GuardrailResult:
        """Check for prompt leakage."""
        score = 0.0
        matches = []

        for pattern, severity in self.LEAKAGE_PATTERNS:
            matches_pattern = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches_pattern:
                score += severity
                matches.append({
                    "pattern": pattern,
                    "text": match.group(),
                    "severity": severity
                })

        # Normalize score
        score = min(score, 10.0)

        # Determine risk level
        if score >= 6.0:
            risk_level = RiskLevel.HIGH
        elif score >= 4.0:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        passed = score < self.threshold

        return GuardrailResult(
            category=GuardrailCategory.PROMPT_LEAKAGE,
            passed=passed,
            risk_level=risk_level,
            score=score,
            details={"matches": matches},
            recommendations=[
                f"Detected {len(matches)} potential prompt leaks"
                if matches else "No prompt leaks detected"
            ]
        )


class ContentSafetyChecker:
    """Checks for general content safety issues."""

    # Safety concerns
    UNSAFE_TOPICS = [
        (r"\b(drugs|marijuana|cocaine|heroin|opioids)\b", 4.0),  # Medical/educational context
        (r"\b(weapon|gun|knife|explosive|bomb)\b", 5.0),
        (r"\b(alcohol|intoxicated|drunk)\b", 3.0),
        (r"\b(extremist|terrorist|violence|riot)\b", 7.0),
    ]

    def __init__(self, threshold: float = 4.0):
        self.threshold = threshold

    def check(self, text: str) -> GuardrailResult:
        """Check for general content safety."""
        score = 0.0
        matches = []

        for pattern, severity in self.UNSAFE_TOPICS:
            matches_pattern = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches_pattern:
                score += severity
                matches.append({
                    "pattern": pattern,
                    "text": match.group(),
                    "severity": severity
                })

        # Normalize score
        score = min(score, 10.0)

        # Determine risk level
        if score >= 7.0:
            risk_level = RiskLevel.CRITICAL
        elif score >= 5.0:
            risk_level = RiskLevel.HIGH
        elif score >= 3.0:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        passed = score < self.threshold

        return GuardrailResult(
            category=GuardrailCategory.CONTENT_SAFETY,
            passed=passed,
            risk_level=risk_level,
            score=score,
            details={"matches": matches},
            recommendations=[
                f"Detected {len(matches)} potentially unsafe topics"
                if matches else "No safety concerns detected"
            ]
        )


class GuardrailsOrchestrator:
    """
    Orchestrates all guardrail checks for comprehensive LLM response safety.

    Combines multiple guardrails to provide a holistic safety assessment
    with configurable thresholds and termination conditions.
    """

    def __init__(
        self,
        toxicity_threshold: float = 5.0,
        hallucination_threshold: float = 3.0,
        prompt_leakage_threshold: float = 4.0,
        content_safety_threshold: float = 4.0,
        block_on_critical: bool = True,
        early_termination: bool = False
    ):
        self.toxicity_checker = ToxicityChecker(toxicity_threshold)
        self.hallucination_checker = HallucinationChecker(hallucination_threshold)
        self.prompt_leakage_checker = PromptLeakageChecker(prompt_leakage_threshold)
        self.content_safety_checker = ContentSafetyChecker(content_safety_threshold)
        self.block_on_critical = block_on_critical
        self.early_termination = early_termination

    async def check(self, text: str) -> GuardrailsAssessment:
        """Run all guardrail checks on text."""
        start_time = datetime.now()
        category_results = []

        # Run all checks
        checks = [
            ("toxicity", self.toxicity_checker.check),
            ("hallucination", self.hallucination_checker.check),
            ("prompt_leakage", self.prompt_leakage_checker.check),
            ("content_safety", self.content_safety_checker.check),
        ]

        for category_name, check_func in checks:
            try:
                result = check_func(text)
                category_results.append(result)

                # Early termination if critical and blocking
                if self.block_on_critical and result.risk_level == RiskLevel.CRITICAL:
                    # Create early termination assessment
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000

                    summary = f"Blocked due to {result.category.value}: {result.score:.1f} score"
                    if result.recommendations:
                        summary += f" - {result.recommendations[0]}"

                    return GuardrailsAssessment(
                        overall_passed=False,
                        overall_risk=RiskLevel.CRITICAL,
                        score=result.score,
                        category_results=[result],
                        execution_time_ms=execution_time,
                        summary=summary,
                        metadata={"early_terminated": True, "category": category_name}
                    )
            except Exception as e:
                logger.error("guardrail_check_error", extra={"category": category_name, "error": str(e)})
                # Continue with other checks
                continue

        # Calculate overall assessment
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        overall_assessment = self._calculate_overall_assessment(category_results)

        # Build summary
        summary = self._build_summary(category_results, overall_assessment)

        return GuardrailsAssessment(
            overall_passed=overall_assessment["passed"],
            overall_risk=overall_assessment["risk"],
            score=overall_assessment["score"],
            category_results=category_results,
            execution_time_ms=execution_time,
            summary=summary,
            metadata={})

    def _calculate_overall_assessment(self, results: List[GuardrailResult]) -> Dict:
        """Calculate overall assessment from individual results."""
        if not results:
            return {"passed": True, "risk": RiskLevel.NONE, "score": 0.0}

        # Find highest risk level
        max_risk = max(result.risk_level for result in results)
        total_score = sum(result.score for result in results)
        max_score = max(result.score for result in results)

        # Overall score is the weighted average
        avg_score = total_score / len(results)

        # Override with max score if critical
        if max_risk == RiskLevel.CRITICAL:
            score = max_score
        else:
            score = avg_score

        # Determine if passed
        passed = all(result.passed for result in results)

        return {
            "passed": passed,
            "risk": max_risk,
            "score": score
        }

    def _build_summary(self, results: List[GuardrailResult], assessment: Dict) -> str:
        """Build a human-readable summary of the assessment."""
        if assessment["passed"]:
            return "All guardrails passed"

        summary = f"Guardrails failed with {assessment['risk'].value} risk: "
        failed_categories = [
            r.category.value for r in results
            if not r.passed and r.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        ]

        if failed_categories:
            summary += f"Failed categories: {', '.join(failed_categories)}"
        else:
            summary += "Low violations"

        return summary


# Create default orchestrator instance
_default_orchestrator: Optional[GuardrailsOrchestrator] = None


def get_guardrails_orchestrator() -> GuardrailsOrchestrator:
    """Get or create the default guardrails orchestrator."""
    global _default_orchestrator
    if _default_orchestrator is None:
        from config.settings import settings

        # Get thresholds from configuration
        toxicity_threshold = getattr(settings, "GUARDRAILS_TOXICITY_THRESHOLD", 5.0)
        hallucination_threshold = getattr(settings, "GUARDRAILS_HALLUCINATION_THRESHOLD", 3.0)
        prompt_leakage_threshold = getattr(settings, "GUARDRAILS_PROMPT_LEAKAGE_THRESHOLD", 4.0)
        content_safety_threshold = getattr(settings, "GUARDRAILS_CONTENT_SAFETY_THRESHOLD", 4.0)
        block_on_critical = getattr(settings, "GUARDRAILS_BLOCK_ON_CRITICAL", True)
        early_termination = getattr(settings, "GUARDRAILS_EARLY_TERMINATION", True)

        _default_orchestrator = GuardrailsOrchestrator(
            toxicity_threshold=toxicity_threshold,
            hallucination_threshold=hallucination_threshold,
            prompt_leakage_threshold=prompt_leakage_threshold,
            content_safety_threshold=content_safety_threshold,
            block_on_critical=block_on_critical,
            early_termination=early_termination
        )

    return _default_orchestrator


async def check_guardrails(text: str, **kwargs) -> GuardrailsAssessment:
    """
    Run guardrails checks on text using default orchestrator.

    Args:
        text: Text to check
        **kwargs: Additional arguments for orchestrator

    Returns:
        GuardrailsAssessment with results
    """
    orchestrator = get_guardrails_orchestrator()

    # Use kwargs if provided to override defaults
    if kwargs:
        from config.settings import settings
        threshold_kwargs = {
            "toxicity_threshold": kwargs.get("toxicity_threshold", getattr(settings, "GUARDRAILS_TOXICITY_THRESHOLD", 5.0)),
            "hallucination_threshold": kwargs.get("hallucination_threshold", getattr(settings, "GUARDRAILS_HALLUCINATION_THRESHOLD", 3.0)),
            "prompt_leakage_threshold": kwargs.get("prompt_leakage_threshold", getattr(settings, "GUARDRAILS_PROMPT_LEAKAGE_THRESHOLD", 4.0)),
            "content_safety_threshold": kwargs.get("content_safety_threshold", getattr(settings, "GUARDRAILS_CONTENT_SAFETY_THRESHOLD", 4.0)),
            "block_on_critical": kwargs.get("block_on_critical", getattr(settings, "GUARDRAILS_BLOCK_ON_CRITICAL", True)),
            "early_termination": kwargs.get("early_termination", getattr(settings, "GUARDRAILS_EARLY_TERMINATION", True))
        }
        orchestrator = GuardrailsOrchestrator(**threshold_kwargs)

    return await orchestrator.check(text)