"""
Input Policy Engine.

Analyses all prompt messages before they reach LiteLLM.
Returns a PolicyResult indicating whether the request is safe to proceed.
"""
from dataclasses import dataclass, field
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine

from .patterns import find_secrets
from .injection import find_injections


# Presidio entity types we care about.
# Full list: https://microsoft.github.io/presidio/supported_entities/
PII_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "US_SSN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "MEDICAL_LICENSE",
    "URL",           # catches internal URLs that may expose infra
    # LOCATION excluded: too many false positives (city/country names in normal prompts)
]

PRESIDIO_SCORE_THRESHOLD = 0.7


@lru_cache(maxsize=1)
def _get_analyzer() -> AnalyzerEngine:
    """Lazy-initialise Presidio once; cached for the process lifetime."""
    return AnalyzerEngine()


@dataclass
class PolicyResult:
    allowed: bool
    block_code: str = ""
    block_reason: str = ""
    findings: list[str] = field(default_factory=list)


def _extract_text(messages: list[dict]) -> str:
    """Concatenate all message contents into a single string for analysis."""
    return "\n".join(m.get("content", "") for m in messages)


def check(messages: list[dict]) -> PolicyResult:
    """
    Run all input checks. Returns the first policy violation found,
    or an allowed result if everything is clean.
    """
    text = _extract_text(messages)

    # --- 1. Secret / credential detection (fast regex, runs first) ---
    secrets = find_secrets(text)
    if secrets:
        return PolicyResult(
            allowed=False,
            block_code="BLOCKED_CREDENTIALS",
            block_reason="Prompt contains what appears to be secret credentials or API keys.",
            findings=secrets,
        )

    # --- 2. Prompt injection detection ---
    injections = find_injections(text)
    if injections:
        return PolicyResult(
            allowed=False,
            block_code="BLOCKED_INJECTION",
            block_reason="Prompt contains patterns associated with prompt injection attacks.",
            findings=injections,
        )

    # --- 3. PII detection via Presidio ---
    analyzer = _get_analyzer()
    results = analyzer.analyze(text=text, entities=PII_ENTITIES, language="en")
    pii_hits = [
        r.entity_type
        for r in results
        if r.score >= PRESIDIO_SCORE_THRESHOLD
    ]
    if pii_hits:
        return PolicyResult(
            allowed=False,
            block_code="BLOCKED_PII",
            block_reason="Prompt contains personally identifiable information (PII).",
            findings=list(set(pii_hits)),
        )

    return PolicyResult(allowed=True)
