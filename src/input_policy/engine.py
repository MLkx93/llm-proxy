"""
Input Policy Engine.

Analyses all prompt messages before they reach LiteLLM.
Returns a PolicyResult indicating whether the request is safe to proceed.
"""
import re
import hashlib
from dataclasses import dataclass, field
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine

from .patterns import find_secrets
from .injection import find_injections
from .pii_patterns import find_pii_patterns

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


def _hash_messages(messages: list[dict]) -> str:
    """SHA-256 of concatenated message contents. Never logs raw prompts."""
    combined = "\n".join(m.get("content", "") for m in messages)
    return hashlib.sha256(combined.encode()).hexdigest()


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
    """Replace violations in text with [REDACTED].

    Uses three layers:
    1. Secret/credential regex patterns (API keys, passwords)
    2. Enhanced PII regex patterns (phone, SSN, IDs that Presidio might miss)
    3. Presidio NLP (email, names, entities)
    """
    from .patterns import SECRET_PATTERNS
    from .pii_patterns import PII_PATTERNS

    cleaned = text

    # Layer 1: Replace secrets (API keys, passwords, etc.)
    for sp in SECRET_PATTERNS:
        cleaned = sp.pattern.sub("[REDACTED]", cleaned)

    # Layer 2: Replace PII patterns that Presidio often misses
    for pii_pattern in PII_PATTERNS:
        cleaned = pii_pattern.pattern.sub("[REDACTED]", cleaned)

    # Layer 3: Presidio NLP analysis for entity-based PII
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


def _redact_credentials(text: str) -> str:
    """Replace credentials in text with [REDACTED]."""
    from .patterns import SECRET_PATTERNS

    cleaned = text

    # Find all secrets and replace
    for sp in SECRET_PATTERNS:
        cleaned = sp.pattern.sub("[REDACTED]", cleaned)

    return cleaned


def extract_text_anthropic(body: dict) -> str:
    """Extract text from the last user message only (for hashing/logging)."""
    return _get_last_user_text(body)


def check_and_sanitize_anthropic(body: dict) -> tuple[dict, PolicyResult, dict]:
    """
    Check Anthropic request body and sanitize if needed.

    Strategy:
    1. Check ONLY the last user message - if violations found:
        - For credentials: REDACT (if CREDENTIAL_ACTION is "redact") or BLOCK (if "block")
        - For injections: Always BLOCK
        - For PII: REDACT (if PII_ACTION is "redact") or BLOCK (if "block")
    2. If last message is clean, check older messages
    3. If older messages have violations, REDACT them (don't block)
    4. Return (sanitized_body, policy_result, redaction_details)

    This allows users to continue after a block while preventing
    blocked content from reaching the LLM.

    Returns:
        tuple: (sanitized_body, PolicyResult, redaction_details)
        redaction_details: {
            "redacted": bool,
            "pii_types": list[str],
            "redaction_count": int,
            "original_hash": str,
            "sanitized_hash": str,
            "redaction_method": str
        }
    """
    import copy
    import hashlib
    from config.settings import settings

    messages = body.get("messages", [])
    if not messages:
        return body, PolicyResult(allowed=True), {"redacted": False}

    # Calculate original body hash (for tracking redaction impact)
    original_hash = hashlib.sha256(str(messages).encode()).hexdigest()
    redaction_details = {
        "redacted": False,
        "pii_types": [],
        "redaction_count": 0,
        "original_hash": original_hash,
        "sanitized_hash": original_hash,
        "redaction_method": None
    }

    # Step 1: Check the LAST user message
    last_user_text = _get_last_user_text(body)
    last_user_text_cleaned = _TOOL_TAG_RE.sub("", last_user_text).strip()

    policy = check_text(last_user_text_cleaned)
    if not policy.allowed:
        # Handle different violation types
        if policy.block_code == "BLOCKED_PII":
            # For PII, check if we should redact instead of block
            if settings.PII_ACTION == "redact":
                # Redact the PII in the last user message and allow the request
                sanitized_body = copy.deepcopy(body)
                # Redact only the last user message content
                if isinstance(sanitized_body.get("messages", [])[-1].get("content"), str):
                    # Simple string content
                    redacted_text = _redact_text(last_user_text)
                    sanitized_body["messages"][-1]["content"] = redacted_text
                    redaction_details["redacted"] = True
                    redaction_details["pii_types"] = policy.findings
                    redaction_details["redaction_count"] = redacted_text.count("[REDACTED]")
                    redaction_details["redaction_method"] = "presidio"
                elif isinstance(sanitized_body.get("messages", [])[-1].get("content"), list):
                    # Complex content (blocks)
                    content = sanitized_body["messages"][-1]["content"]
                    total_redactions = 0
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            redacted_text = _redact_text(block.get("text", ""))
                            block["text"] = redacted_text
                            total_redactions += redacted_text.count("[REDACTED]")
                    redaction_details["redacted"] = True
                    redaction_details["pii_types"] = policy.findings
                    redaction_details["redaction_count"] = total_redactions
                    redaction_details["redaction_method"] = "presidio"
                redaction_details["sanitized_hash"] = hashlib.sha256(str(sanitized_body.get("messages", [])).encode()).hexdigest()
                return sanitized_body, PolicyResult(allowed=True, findings=policy.findings), redaction_details
            else:
                # Block for PII (original behavior)
                return body, policy, redaction_details
        elif policy.block_code == "BLOCKED_CREDENTIALS":
            # For credentials, check if we should redact instead of block
            if settings.CREDENTIAL_ACTION == "redact":
                # Redact the credentials in the last user message and allow the request
                sanitized_body = copy.deepcopy(body)
                # Redact only the last user message content
                if isinstance(sanitized_body.get("messages", [])[-1].get("content"), str):
                    # Simple string content
                    redacted_text = _redact_credentials(last_user_text)
                    sanitized_body["messages"][-1]["content"] = redacted_text
                    redaction_details["redacted"] = True
                    redaction_details["pii_types"] = policy.findings
                    redaction_details["redaction_count"] = redacted_text.count("[REDACTED]")
                    redaction_details["redaction_method"] = "regex"
                elif isinstance(sanitized_body.get("messages", [])[-1].get("content"), list):
                    # Complex content (blocks)
                    content = sanitized_body["messages"][-1]["content"]
                    total_redactions = 0
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            redacted_text = _redact_credentials(block.get("text", ""))
                            block["text"] = redacted_text
                            total_redactions += redacted_text.count("[REDACTED]")
                    redaction_details["redacted"] = True
                    redaction_details["pii_types"] = policy.findings
                    redaction_details["redaction_count"] = total_redactions
                    redaction_details["redaction_method"] = "regex"
                redaction_details["sanitized_hash"] = hashlib.sha256(str(sanitized_body.get("messages", [])).encode()).hexdigest()
                return sanitized_body, PolicyResult(allowed=True, findings=policy.findings), redaction_details
            else:
                # Block for credentials (original behavior)
                return body, policy, redaction_details
        else:
            # Block for injections (higher risk - always block)
            return body, policy, redaction_details

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
    any_redacted = False
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
                redacted_text = _redact_text(content)
                sanitized_messages[i]["content"] = redacted_text
                redaction_details["redaction_count"] += redacted_text.count("[REDACTED]")
                any_redacted = True

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
                        redacted_text = _redact_text(text)
                        sanitized_messages[i]["content"][j]["text"] = redacted_text
                        redaction_details["redaction_count"] += redacted_text.count("[REDACTED]")
                        any_redacted = True

    if any_redacted:
        redaction_details["redacted"] = True
        redaction_details["redaction_method"] = "presidio"
        redaction_details["sanitized_hash"] = hashlib.sha256(str(sanitized_messages).encode()).hexdigest()

    return sanitized_body, PolicyResult(allowed=True), redaction_details


def check_text(text: str) -> PolicyResult:
    """
    Core policy check on pre-extracted text.
    Collects ALL violations (not just first) to provide complete findings.

    Detection order:
    1. Secrets/credentials (fast, explicit) — always blocks
    2. Prompt injection (fast, pattern-based) — always blocks
    3. Enhanced PII patterns (regex for common formats) — collects all
    4. Presidio NLP (entity-based, catches names, etc.) — collects all
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

    # --- 3 & 4: Collect ALL PII (both regex patterns and Presidio NLP) ---
    all_pii_findings = []

    # Enhanced PII pattern detection (regex for formats Presidio might miss)
    pii_patterns_found = find_pii_patterns(text)
    all_pii_findings.extend(pii_patterns_found)

    # Presidio NLP-based PII detection
    analyzer = _get_analyzer()
    results = analyzer.analyze(text=text, entities=PII_ENTITIES, language="en")
    pii_hits = [
        r.entity_type
        for r in results
        if r.score >= PRESIDIO_SCORE_THRESHOLD
        and text[r.start:r.end].lower() not in TECH_TERMS_ALLOWLIST
    ]
    all_pii_findings.extend(pii_hits)

    # If any PII found, block with all findings
    if all_pii_findings:
        return PolicyResult(
            allowed=False,
            block_code="BLOCKED_PII",
            block_reason="Prompt contains personally identifiable information (PII).",
            findings=list(dict.fromkeys(all_pii_findings)),  # Remove duplicates while preserving order
        )

    return PolicyResult(allowed=True)


def check_and_sanitize_openai(messages: list[dict]) -> tuple[list[dict], PolicyResult, dict]:
    """
    Check OpenAI-format messages and sanitize if needed.
    
    Strategy:
    1. Check ONLY the last user message - if violations found:
        - For credentials: REDACT (if CREDENTIAL_ACTION is "redact") or BLOCK (if "block")
        - For injections: Always BLOCK
        - For PII: REDACT (if PII_ACTION is "redact") or BLOCK (if "block")
    2. If last message is clean, check older messages
    3. If older messages have violations, REDACT them (don't block)
    4. Return (sanitized_messages, policy_result, redaction_details)
    
    This allows users to continue after a block while preventing
    blocked content from reaching the LLM.
    
    Returns:
        tuple: (sanitized_messages, PolicyResult, redaction_details)
        redaction_details: {
            "redacted": bool,
            "pii_types": list[str],
            "redaction_count": int,
            "original_hash": str,
            "sanitized_hash": str,
            "redaction_method": str
        }
    """
    import copy
    import hashlib
    from config.settings import settings
    
    if not messages:
        return messages, PolicyResult(allowed=True), {"redacted": False}
    
    # Calculate original hash before any redaction
    original_hash = _hash_messages(messages)
    redaction_details = {
        "redacted": False,
        "pii_types": [],
        "redaction_count": 0,
        "original_hash": original_hash,
        "sanitized_hash": original_hash,
        "redaction_method": None
    }
    
    # Find the last user message
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break
    
    if last_user_idx is None:
        return messages, PolicyResult(allowed=True), redaction_details
    
    # Step 1: Check the LAST user message
    last_msg = messages[last_user_idx]
    last_content = last_msg.get("content", "")
    
    if isinstance(last_content, str):
        # Simple string content
        policy = check_text(last_content)
        if not policy.allowed:
            # Handle different violation types
            if policy.block_code == "BLOCKED_PII":
                if settings.PII_ACTION == "redact":
                    # Redact PII and allow the request
                    sanitized_messages = copy.deepcopy(messages)
                    sanitized_messages[last_user_idx]["content"] = _redact_text(last_content)
                    # Calculate sanitized hash
                    sanitized_hash = _hash_messages(sanitized_messages)
                    redaction_details["redacted"] = True
                    redaction_details["pii_types"] = policy.findings
                    redaction_details["redaction_count"] = sanitized_messages[last_user_idx]["content"].count("[REDACTED]")
                    redaction_details["sanitized_hash"] = sanitized_hash
                    redaction_details["redaction_method"] = "presidio"
                    return sanitized_messages, PolicyResult(allowed=True, findings=policy.findings), redaction_details
                else:
                    return messages, policy, redaction_details
            elif policy.block_code == "BLOCKED_CREDENTIALS":
                if settings.CREDENTIAL_ACTION == "redact":
                    sanitized_messages = copy.deepcopy(messages)
                    sanitized_messages[last_user_idx]["content"] = _redact_credentials(last_content)
                    sanitized_hash = _hash_messages(sanitized_messages)
                    redaction_details["redacted"] = True
                    redaction_details["pii_types"] = policy.findings
                    redaction_details["redaction_count"] = sanitized_messages[last_user_idx]["content"].count("[REDACTED]")
                    redaction_details["sanitized_hash"] = sanitized_hash
                    redaction_details["redaction_method"] = "regex"
                    return sanitized_messages, PolicyResult(allowed=True, findings=policy.findings), redaction_details
                else:
                    return messages, policy, redaction_details
            else:
                # Block for injections
                return messages, policy, redaction_details
    elif isinstance(last_content, list):
        # Complex content (blocks) - check only the last text block
        last_text_block = None
        last_block_idx = None
        for j in range(len(last_content) - 1, -1, -1):
            if isinstance(last_content[j], dict) and last_content[j].get("type") == "text":
                last_text_block = last_content[j].get("text", "")
                last_block_idx = j
                break
        
        if last_text_block:
            policy = check_text(last_text_block)
            if not policy.allowed:
                if policy.block_code == "BLOCKED_PII":
                    if settings.PII_ACTION == "redact":
                        sanitized_messages = copy.deepcopy(messages)
                        sanitized_messages[last_user_idx]["content"][last_block_idx]["text"] = _redact_text(last_text_block)
                        sanitized_hash = _hash_messages(sanitized_messages)
                        redaction_details["redacted"] = True
                        redaction_details["pii_types"] = policy.findings
                        redaction_details["redaction_count"] = sanitized_messages[last_user_idx]["content"][last_block_idx]["text"].count("[REDACTED]")
                        redaction_details["sanitized_hash"] = sanitized_hash
                        redaction_details["redaction_method"] = "presidio"
                        return sanitized_messages, PolicyResult(allowed=True, findings=policy.findings), redaction_details
                    else:
                        return messages, policy, redaction_details
                elif policy.block_code == "BLOCKED_CREDENTIALS":
                    if settings.CREDENTIAL_ACTION == "redact":
                        sanitized_messages = copy.deepcopy(messages)
                        sanitized_messages[last_user_idx]["content"][last_block_idx]["text"] = _redact_credentials(last_text_block)
                        sanitized_hash = _hash_messages(sanitized_messages)
                        redaction_details["redacted"] = True
                        redaction_details["pii_types"] = policy.findings
                        redaction_details["redaction_count"] = sanitized_messages[last_user_idx]["content"][last_block_idx]["text"].count("[REDACTED]")
                        redaction_details["sanitized_hash"] = sanitized_hash
                        redaction_details["redaction_method"] = "regex"
                        return sanitized_messages, PolicyResult(allowed=True, findings=policy.findings), redaction_details
                    else:
                        return messages, policy, redaction_details
                else:
                    return messages, policy, redaction_details
    
    # Step 2: Last message is clean. Redact violations in ALL older content.
    sanitized_messages = copy.deepcopy(messages)
    
    for i, msg in enumerate(sanitized_messages):
        if msg.get("role") != "user" or i == last_user_idx:
            continue
        
        content = msg.get("content", "")
        
        if isinstance(content, str):
            policy = check_text(content)
            if not policy.allowed:
                sanitized_messages[i]["content"] = _redact_text(content)
        elif isinstance(content, list):
            for j, block in enumerate(content):
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    policy = check_text(text)
                    if not policy.allowed:
                        sanitized_messages[i]["content"][j]["text"] = _redact_text(text)
    
    # Calculate final sanitized hash and update redaction details
    sanitized_hash = _hash_messages(sanitized_messages)
    redaction_details["sanitized_hash"] = sanitized_hash
    
    return sanitized_messages, PolicyResult(allowed=True), redaction_details


def check(messages: list[dict]) -> PolicyResult:
    """
    Run all input checks on OpenAI-format messages.
    Delegates to check_text() after extraction.
    """
    return check_text(_extract_text(messages))
