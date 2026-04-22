"""
Output Security Engine.

Inspects LLM responses before they are returned to the client.
If code is present, extracts dependencies and validates each against Nexus.
Fail-closed: any unvalidated or unsafe dependency blocks the response.

Optionally performs vulnerability scanning on package dependencies.
"""
from dataclasses import dataclass, field

from .code_parser import extract_code_blocks
from .nexus import validate_package, ValidationResult
from .vulnerability_scanner import (
    scan_package_cached,
    should_block_package,
    VulnerabilityReport,
)
from src.proxy.logging import get_logger
from config.settings import settings

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
    
    Performs two-stage validation:
    1. Nexus validation (package in approved repository)
    2. Vulnerability scanning (if enabled, check for known CVEs)
    """
    blocks = extract_code_blocks(response_text)

    if not blocks:
        return OutputPolicyResult(allowed=True)

    for block in blocks:
        if not block.dependencies:
            continue

        for dep in block.dependencies:
            # Stage 1: Nexus validation
            result: ValidationResult = await validate_package(dep.name, dep.source_type)
            if not result.approved:
                logger.warning("output_blocked", extra={
                    "package": dep.name,
                    "language": dep.source_type,
                    "block_code": result.block_code,
                })
                return OutputPolicyResult(
                    allowed=False,
                    block_code=result.block_code,
                    block_reason=result.reason,
                    blocked_packages=[dep.name],
                )
            
            # Stage 2: Vulnerability scanning (if enabled)
            if settings.VULN_SCAN_ENABLED:
                vuln_report: VulnerabilityReport = await scan_package_cached(
                    package=dep.name,
                    ecosystem=dep.source_type
                )
                
                if not vuln_report.is_secure:
                    should_block, reason = should_block_package(
                        vuln_report, 
                        min_severity=settings.VULN_MIN_SEVERITY
                    )
                    if should_block:
                        logger.warning("vulnerability_blocked", extra={
                            "package": dep.name,
                            "language": dep.source_type,
                            "highest_severity": vuln_report.highest_severity,
                            "cvss_score": vuln_report.highest_cvss,
                            "vulnerability_count": vuln_report.vulnerability_count,
                        })
                        return OutputPolicyResult(
                            allowed=False,
                            block_code="BLOCKED_VULNERABLE_PACKAGE",
                            block_reason=reason,
                            blocked_packages=[dep.name],
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
