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

# Tech terms Presidio mistakes for person names — allowlist to avoid false positives
TECH_TERMS_ALLOWLIST = {
    "django", "flask", "rails", "ruby", "rust", "go", "swift", "kotlin",
    "travis", "jenkins", "hudson", "maven", "gradle", "docker", "ansible",
    "kafka", "redis", "mongo", "postgres", "mysql", "sqlite", "oracle",
    "newton", "euler", "darwin",  # algorithms/methods named after people
    "hadoop", "spark", "flink", "cassandra", "apollo", "hermes", "prometheus",
    "flake8", "pytest", "numpy", "pandas", "scipy",  # Python tools/libs
    "anthropic", "openai", "cohere", "mistral", "claude",  # AI companies/models
}


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


def _get_last_user_text(body: dict) -> str:
    """Extract text from only the LAST text block of the LAST user message."""
    messages = body.get("messages", [])

    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            # Get only the LAST text block (Claude Code bundles turns as blocks)
            for block in reversed(content):
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
            return ""
        elif isinstance(content, str):
            return content
    return ""


def _redact_text(text: str) -> str:
    """Replace violations in text with [REDACTED]."""
    from .patterns import SECRET_PATTERNS

    cleaned = text

    # Find all secrets and replace
    for sp in SECRET_PATTERNS:
        cleaned = sp.pattern.sub("[REDACTED]", cleaned)

    # Find all PII and replace
    analyzer = _get_analyzer()
    results = analyzer.analyze(text=cleaned, entities=PII_ENTITIES, language="en")
    # Sort by position descending so we can replace without offset issues
    results = sorted(results, key=lambda r: r.start, reverse=True)
    for r in results:
        if r.score >= PRESIDIO_SCORE_THRESHOLD:
            matched = cleaned[r.start:r.end]
            if matched.lower() not in TECH_TERMS_ALLOWLIST:
                cleaned = cleaned[:r.start] + "[REDACTED]" + cleaned[r.end:]

    return cleaned


def extract_text_anthropic(body: dict) -> str:
    """Extract text from the last user message only (for hashing/logging)."""
    return _get_last_user_text(body)


def check_and_sanitize_anthropic(body: dict) -> tuple[dict, PolicyResult]:
    """
    Check Anthropic request body and sanitize if needed.

    Strategy:
    1. Check ONLY the last user message - if violations found, BLOCK
    2. If last message is clean, check older messages
    3. If older messages have violations, REDACT them (don't block)
    4. Return (sanitized_body, policy_result)

    This allows users to continue after a block while preventing
    blocked content from reaching the LLM.
    """
    import copy

    messages = body.get("messages", [])
    if not messages:
        return body, PolicyResult(allowed=True)

    # Step 1: Check the LAST user message - if bad, block
    last_user_text = _get_last_user_text(body)
    last_user_text_cleaned = _TOOL_TAG_RE.sub("", last_user_text).strip()

    policy = check_text(last_user_text_cleaned)
    if not policy.allowed:
        return body, policy  # Block - last message has violations

    # Step 2: Last message is clean. Redact violations in ALL older content.
    # This includes:
    #   - All user messages before the last one
    #   - All content blocks before the last one in the last user message
    #     (Claude Code bundles multiple turns as blocks in a single message)
    sanitized_body = copy.deepcopy(body)
    sanitized_messages = sanitized_body.get("messages", [])

    # Find the last user message index and last block index within it
    last_user_idx = None
    last_block_idx = None
    for i in range(len(sanitized_messages) - 1, -1, -1):
        if sanitized_messages[i].get("role") == "user":
            last_user_idx = i
            content = sanitized_messages[i].get("content", "")
            if isinstance(content, list):
                # Find the last text block index
                for j in range(len(content) - 1, -1, -1):
                    if isinstance(content[j], dict) and content[j].get("type") == "text":
                        last_block_idx = j
                        break
            break

    # Check and redact all user content except the last block
    for i, msg in enumerate(sanitized_messages):
        if msg.get("role") != "user":
            continue

        content = msg.get("content", "")

        if isinstance(content, str):
            # String content: skip if this is the last user message
            if i == last_user_idx:
                continue
            cleaned = _TOOL_TAG_RE.sub("", content).strip()
            old_policy = check_text(cleaned)
            if not old_policy.allowed:
                sanitized_messages[i]["content"] = _redact_text(content)

        elif isinstance(content, list):
            for j, block in enumerate(content):
                if isinstance(block, dict) and block.get("type") == "text":
                    # Skip the very last block of the last user message
                    if i == last_user_idx and j == last_block_idx:
                        continue
                    text = block.get("text", "")
                    cleaned = _TOOL_TAG_RE.sub("", text).strip()
                    old_policy = check_text(cleaned)
                    if not old_policy.allowed:
                        sanitized_messages[i]["content"][j]["text"] = _redact_text(text)

    return sanitized_body, PolicyResult(allowed=True)


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
        and text[r.start:r.end].lower() not in TECH_TERMS_ALLOWLIST
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
