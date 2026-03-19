"""
Output Security Engine.

Inspects LLM responses before they are returned to the client.
If code is present, extracts dependencies and validates each against Nexus.
Fail-closed: any unvalidated or unsafe dependency blocks the response.
"""
from dataclasses import dataclass, field

from .code_parser import extract_code_blocks
from .nexus import validate_package, ValidationResult
from src.proxy.logging import get_logger

logger = get_logger("output_security")


@dataclass
class OutputPolicyResult:
    allowed: bool
    block_code: str = ""
    block_reason: str = ""
    blocked_packages: list[str] = field(default_factory=list)


async def check(response_text: str) -> OutputPolicyResult:
    """
    Run output security checks on the LLM response text.
    Returns OutputPolicyResult indicating whether the response is safe.
    """
    blocks = extract_code_blocks(response_text)

    if not blocks:
        return OutputPolicyResult(allowed=True)

    for block in blocks:
        if not block.dependencies:
            continue

        lang = block.language
        for package in block.dependencies:
            result: ValidationResult = await validate_package(package, lang)
            if not result.approved:
                logger.warning("output_blocked", extra={
                    "package": package,
                    "language": lang,
                    "block_code": result.block_code,
                })
                return OutputPolicyResult(
                    allowed=False,
                    block_code=result.block_code,
                    block_reason=result.reason,
                    blocked_packages=[package],
                )

    return OutputPolicyResult(allowed=True)


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
