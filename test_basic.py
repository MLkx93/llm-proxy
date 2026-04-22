#!/usr/bin/env python3
import asyncio
import sys
import os

# Add src to path (works in venv)
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.output_security.vulnerability_scanner import (
    _parse_cvss_score,
    _get_severity_from_score,
    SeverityLevel,
    Vulnerability,
    VulnerabilityReport,
    should_block_package
)

async def test_basic():
    print("=== Basic Vulnerability Scanner Tests ===")
    
    # Test CVSS parsing
    print("✓ Testing CVSS parsing...")
    assert _parse_cvss_score("9.8") == 9.8
    assert _parse_cvss_score("7.5") == 7.5
    assert _parse_cvss_score("0.0") == 0.0
    print("  CVSS parsing: OK")
    
    # Test severity levels
    print("✓ Testing severity levels...")
    assert _get_severity_from_score(10.0) == SeverityLevel.CRITICAL
    assert _get_severity_from_score(8.0) == SeverityLevel.HIGH
    assert _get_severity_from_score(5.0) == SeverityLevel.MEDIUM
    print("  Severity levels: OK")
    
    # Test package blocking
    print("✓ Testing package blocking...")
    vuln = Vulnerability(
        id="CVE-2021-44228",
        severity="CRITICAL",
        cvss_score=10.0,
        summary="Test vulnerability"
    )
    
    report = VulnerabilityReport(
        package_name="test-package",
        package_version="1.0.0",
        language="python",
        vulnerabilities=[vuln]
    )
    
    should_block, reason = should_block_package(report, min_severity="HIGH")
    assert should_block == True
    assert "CRITICAL" in reason
    print("  Package blocking: OK")
    
    # Test safe package
    safe_report = VulnerabilityReport(
        package_name="safe-package",
        package_version="1.0.0",
        language="python",
        vulnerabilities=[]
    )
    
    should_block_safe, reason_safe = should_block_package(safe_report, min_severity="HIGH")
    assert should_block_safe == False
    print("  Safe package handling: OK")
    
    print("\n🎉 All basic tests passed!")

if __name__ == "__main__":
    asyncio.run(test_basic())
