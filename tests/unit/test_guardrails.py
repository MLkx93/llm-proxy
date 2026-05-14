"""
Unit tests for guardrails module.
"""
import asyncio
import pytest
from src.output_security.guardrails import (
    ToxicityChecker,
    HallucinationChecker,
    PromptLeakageChecker,
    ContentSafetyChecker,
    GuardrailsOrchestrator,
    check_guardrails,
    GuardrailCategory,
    RiskLevel
)


class TestToxicityChecker:
    def test_toxic_content_detected(self):
        checker = ToxicityChecker(threshold=5.0)
        result = checker.check("I hate everyone and want to hurt them")

        assert result.category == GuardrailCategory.TOXICITY
        assert result.passed == False
        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert result.score > 0

    def test_safe_content_passed(self):
        checker = ToxicityChecker(threshold=5.0)
        result = checker.check("Hello, how are you today?")

        assert result.category == GuardrailCategory.TOXICITY
        assert result.passed == True
        assert result.risk_level == RiskLevel.LOW
        assert result.score == 0.0


class TestHallucinationChecker:
    def test_hallucination_detected(self):
        checker = HallucinationChecker(threshold=3.0)
        result = checker.check("I'm not sure but I think this is definitely true")

        assert result.category == GuardrailCategory.HALLUCINATION
        # This should detect both uncertainty and overconfidence
        assert result.score > 0

    def test_confident_response_low_risk(self):
        checker = HallucinationChecker(threshold=3.0)
        result = checker.check("The sky is blue and water is wet")

        assert result.category == GuardrailCategory.HALLUCINATION
        assert result.passed == True
        assert result.score <= 1.0  # Should be low score


class TestPromptLeakageChecker:
    def test_prompt_leakage_detected(self):
        checker = PromptLeakageChecker(threshold=4.0)
        result = checker.check("You are an AI assistant created by OpenAI")

        assert result.category == GuardrailCategory.PROMPT_LEAKAGE
        assert result.passed == False
        assert result.score > 0

    def test_normal_response_passed(self):
        checker = PromptLeakageChecker(threshold=4.0)
        result = checker.check("Paris is the capital of France")

        assert result.category == GuardrailCategory.PROMPT_LEAKAGE
        assert result.passed == True
        assert result.score == 0.0


class TestContentSafetyChecker:
    def test_unsafe_content_detected(self):
        checker = ContentSafetyChecker(threshold=4.0)
        result = checker.check("How to make a bomb at home")

        assert result.category == GuardrailCategory.CONTENT_SAFETY
        assert result.passed == False
        assert result.score > 0

    def test_safe_content_passed(self):
        checker = ContentSafetyChecker(threshold=4.0)
        result = checker.check("How to cook pasta")

        assert result.category == GuardrailCategory.CONTENT_SAFETY
        assert result.passed == True
        assert result.score == 0.0


class TestGuardrailsOrchestrator:
    @pytest.mark.asyncio
    async def test_orchestrator_safe_content(self):
        orchestrator = GuardrailsOrchestrator()
        result = await orchestrator.check("Hello world")

        assert hasattr(result, 'overall_passed')
        assert result.overall_passed == True
        # For safe content, we expect no high or critical risk
        assert result.overall_risk not in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    @pytest.mark.asyncio
    async def test_orchestrator_toxic_content(self):
        orchestrator = GuardrailsOrchestrator()
        result = await orchestrator.check("I hate everyone and want to kill them")

        assert result.overall_passed == False
        assert result.overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    @pytest.mark.asyncio
    async def test_orchestrator_early_termination(self):
        orchestrator = GuardrailsOrchestrator(block_on_critical=True, early_termination=True)
        result = await orchestrator.check("I want to kill everyone")  # Should trigger toxicity

        # With early termination, we expect quick blocking
        assert result.overall_passed == False


class TestGuardrailsFunction:
    @pytest.mark.asyncio
    async def test_check_guardrails_function(self):
        result = await check_guardrails("Hello world")

        assert hasattr(result, 'overall_passed')
        assert isinstance(result.overall_passed, bool)
        # For safe content, we expect no high or critical risk
        assert result.overall_risk not in [RiskLevel.HIGH, RiskLevel.CRITICAL]


if __name__ == "__main__":
    pytest.main([__file__])