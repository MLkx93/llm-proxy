"""
Version Range Validator Module.

Checks if specific package versions fall within vulnerable version ranges
by comparing against security advisories.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from src.output_security.version_parser import parse_constraint, _parse_version_string, Version
from src.output_security.security_advisory import Advisory, get_advisory_database


@dataclass
class VersionVulnerability:
    """Represents a version-specific vulnerability finding."""
    advisory_id: str
    package_name: str
    package_version: str
    affected_range: str
    fixed_versions: List[str]
    is_vulnerable: bool
    severity: str = ""
    cvss_score: float = 0.0
    recommendation: str = ""


@dataclass
class VersionValidationResult:
    """Result of version-specific vulnerability validation."""
    package_name: str
    package_version: str
    language: str
    vulnerabilities: List[VersionVulnerability] = field(default_factory=list)
    is_secure: bool = True
    highest_severity: str = "NONE"
    highest_cvss: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    @property
    def vulnerability_count(self) -> int:
        return len(self.vulnerabilities)

    @property
    def has_vulnerabilities(self) -> bool:
        return len(self.vulnerabilities) > 0


def _check_version_in_range(version_str: str, range_str: str) -> bool:
    """
    Check if a version is within a version range specification.

    Args:
        version_str: Version to check (e.g., "1.2.3")
        range_str: Version range (e.g., ">=1.0.0 <2.0.0")

    Returns:
        True if version is within the range, False otherwise
    """
    if not version_str or not range_str:
        return False

    constraints = parse_constraint(range_str)
    version = _parse_version_string(version_str)

    # Version must match ALL constraints (AND relationship)
    for constraint in constraints:
        if not constraint.matches(version):
            return False

    return True


def check_version_against_advisory(package_version: str, advisory: Advisory) -> bool:
    """
    Check if a package version is affected by an advisory.

    Args:
        package_version: Version to check
        advisory: Security advisory with affected version ranges

    Returns:
        True if version is affected, False otherwise
    """
    affected_ranges = advisory.get_affected_versions_list()

    if not affected_ranges:
        return False

    for range_str in affected_ranges:
        if _check_version_in_range(package_version, range_str):
            return True

    return False


def get_first_fixed_version(advisory: Advisory) -> Optional[str]:
    """Get the first fixed version from an advisory."""
    fixed_versions = advisory.get_fixed_versions_list()
    return fixed_versions[0] if fixed_versions else None


async def validate_package_version(package: str, version: str,
                                   package_manager: str = "python") -> VersionValidationResult:
    """
    Validate a specific package version against security advisories.

    Args:
        package: Package name
        version: Specific version to check
        package_manager: Package manager/ecosystem (python, javascript, java, etc.)

    Returns:
        VersionValidationResult with version-specific vulnerability details
    """
    result = VersionValidationResult(
        package_name=package,
        package_version=version,
        language=package_manager
    )

    # Get advisories for the package
    db = get_advisory_database()
    advisories = db.get_advisories_for_package(package, package_manager)

    if not advisories:
        # No advisories found, package might be secure
        result.is_secure = True
        return result

    # Check each advisory
    for advisory in advisories:
        if check_version_against_advisory(version, advisory):
            fixed_version = get_first_fixed_version(advisory)

            vuln = VersionVulnerability(
                advisory_id=advisory.id,
                package_name=package,
                package_version=version,
                affected_range=", ".join(advisory.get_affected_versions_list()),
                fixed_versions=advisory.get_fixed_versions_list(),
                is_vulnerable=True,
                severity=advisory.severity,
                cvss_score=advisory.cvss_score,
                recommendation=f"Upgrade to {fixed_version}" if fixed_version else "Upgrade to a newer version"
            )

            result.vulnerabilities.append(vuln)

            if fixed_version:
                result.recommendations.append(
                    f"Package '{package}' version {version} is vulnerable to {advisory.id}. "
                    f"Upgrade to version {fixed_version} or later."
                )
            else:
                result.recommendations.append(
                    f"Package '{package}' version {version} is vulnerable to {advisory.id}."
                )

    # Update result based on vulnerabilities found
    if result.vulnerabilities:
        result.is_secure = False
        result.highest_cvss = max(v.cvss_score for v in result.vulnerabilities)

        # Determine highest severity
        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
        max_severity = max(
            (severity_order.get(v.severity.upper(), 0), v.severity)
            for v in result.vulnerabilities
        )
        result.highest_severity = max_severity[1]

    return result


def add_advisory_to_database(advisory: Advisory) -> bool:
    """Add an advisory to the security database."""
    db = get_advisory_database()
    return db.add_advisory(advisory)


def populate_sample_advisories() -> int:
    """
    Populate the database with sample advisories for testing.
    These represent known vulnerabilities in popular packages.

    Returns:
        Number of advisories added
    """
    from datetime import datetime

    sample_advisories = [
        Advisory(
            id="CVE-2021-44228",
            package_name="log4j",
            package_manager="java",
            affected_versions='[">=2.0.0,<2.15.0"]',
            fixed_versions='["2.15.0"]',
            severity="CRITICAL",
            cvss_score=10.0,
            summary="Apache Log4j2 JNDI features vulnerability",
            published_date="2021-12-10",
            references_url='["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"]',
            source="NVD"
        ),
        Advisory(
            id="CVE-2022-0778",
            package_name="openssl",
            package_manager="python",
            affected_versions='[">=1.1.0,<1.1.1n"]',
            fixed_versions='["1.1.1n"]',
            severity="HIGH",
            cvss_score=7.5,
            summary="OpenSSL BN_mod_sqrt() infinite loop vulnerability",
            published_date="2022-03-15",
            references_url='["https://nvd.nist.gov/vuln/detail/CVE-2022-0778"]',
            source="NVD"
        ),
        Advisory(
            id="CVE-2021-23337",
            package_name="django",
            package_manager="python",
            affected_versions='[">=2.2.0,<2.2.23"]',
            fixed_versions='["2.2.23", "3.1.11", "3.2.4"]',
            severity="HIGH",
            cvss_score=8.1,
            summary="Django QuerySet.order_by() SQL injection vulnerability",
            published_date="2021-04-12",
            references_url='["https://nvd.nist.gov/vuln/detail/CVE-2021-23337"]',
            source="NVD"
        ),
        Advisory(
            id="CVE-2020-8203",
            package_name="lodash",
            package_manager="javascript",
            affected_versions='["<4.17.21"]',
            fixed_versions='["4.17.21"]',
            severity="HIGH",
            cvss_score=7.4,
            summary="Lodash prototype pollution vulnerability",
            published_date="2020-07-15",
            references_url='["https://nvd.nist.gov/vuln/detail/CVE-2020-8203"]',
            source="NVD"
        ),
        Advisory(
            id="CVE-2021-3749",
            package_name="requests",
            package_manager="python",
            affected_versions='["<2.20.0"]',
            fixed_versions='["2.20.0"]',
            severity="HIGH",
            cvss_score=7.5,
            summary="Requests urllib3 vulnerability leading to CRLF injection",
            published_date="2022-02-01",
            references_url='["https://nvd.nist.gov/vuln/detail/CVE-2021-3749"]',
            source="NVD"
        ),
        Advisory(
            id="CVE-2022-31197",
            package_name="moment",
            package_manager="javascript",
            affected_versions='["<2.29.2"]',
            fixed_versions='["2.29.2"]',
            severity="MEDIUM",
            cvss_score=5.3,
            summary="Moment.js inefficient rewriting algorithm vulnerability",
            published_date="2022-07-01",
            references_url='["https://nvd.nist.gov/vuln/detail/CVE-2022-31197"]',
            source="NVD"
        ),
    ]

    db = get_advisory_database()
    return db.bulk_insert_advisories(sample_advisories)


def get_database_stats() -> dict:
    """Get statistics about the advisory database."""
    db = get_advisory_database()

    return {
        "total_advisories": db.get_advisory_count(),
        "packages_with_advisories": len(db.get_packages_with_advisories()),
        "critical_count": len(db.get_critical_advisories()),
        "recent_count": len(db.get_recent_advisories(30)),
    }