"""
Input Policy Engine.

Analyses all prompt messages before they reach LiteLLM.
Returns a PolicyResult indicating whether the request is safe to proceed.
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine

from .patterns import find_secrets
from .injection import find_injections

# Strip all XML-like tag blocks injected by tools (e.g. Claude Code).
# These contain URLs, names, emails, file paths that trigger false positives.
# Matches <tag-name>...content...</tag-name> and self-closing <tag-name ... />
_TOOL_TAG_RE = re.compile(r"<[a-zA-Z_-]+[^>]*>.*?</[a-zA-Z_-]+>", re.DOTALL)


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
    """Concatenate all message contents into a single string for analysis (OpenAI format)."""
    return "\n".join(m.get("content", "") for m in messages)


def _extract_content_block_text(content) -> str:
    """Extract text from a content field that may be a string or list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def extract_text_anthropic(body: dict) -> str:
    """
    Extract scannable text from an Anthropic Messages API request body.
    Only scans the LAST user content block from the LAST user message.

    Why:
    - System prompts are tool-generated (URLs, names) → false positives
    - Assistant messages are AI-generated → not user input
    - Previous user messages were already scanned when they were first sent
    - Claude Code may bundle multiple user turns into a single message
      separated by content blocks — we only scan the last block
    """
    messages = body.get("messages", [])

    # Find the last user message
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue

        content = msg.get("content", "")

        # If content is a list of blocks, only scan the last text block
        if isinstance(content, list):
            for block in reversed(content):
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
            return ""

        # If content is a string, only scan the last segment
        # (Claude Code separates turns with double newlines)
        if isinstance(content, str):
            segments = content.split("\n\n")
            return segments[-1].strip() if segments else ""

        return ""

    return ""


def check_text(text: str) -> PolicyResult:
    """
    Core policy check on pre-extracted text.
    Returns the first violation found, or allowed if clean.
    """
    # Strip tool-generated tags (e.g. <system-reminder>) that cause false positives
    text = _TOOL_TAG_RE.sub("", text).strip()

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


def check(messages: list[dict]) -> PolicyResult:
    """
    Run all input checks on OpenAI-format messages.
    Delegates to check_text() after extraction.
    """
    return check_text(_extract_text(messages))
