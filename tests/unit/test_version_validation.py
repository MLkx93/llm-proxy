"""
Unit tests for Version Validation Module (Phase 2).
"""
import pytest
import os
import tempfile

from src.output_security.version_parser import (
    parse_constraint,
    _parse_version_string,
    is_version_affected,
    compare_versions,
    Version,
    VersionConstraint,
    VersionComparison,
)
from src.output_security.security_advisory import (
    SecurityAdvisoryDatabase,
    Advisory,
)
from src.output_security.version_validator import (
    validate_package_version,
    check_version_against_advisory,
    populate_sample_advisories,
    get_database_stats,
    VersionVulnerability,
    VersionValidationResult,
)


class TestVersionParser:
    """Test version parsing and constraint matching."""

    def test_parse_simple_version(self):
        """Test parsing simple version strings."""
        v = _parse_version_string("1.0.0")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0

    def test_parse_version_with_prefix(self):
        """Test parsing versions with v prefix."""
        v = _parse_version_string("v1.0.0")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0

    def test_parse_version_with_pre_release(self):
        """Test parsing versions with pre-release."""
        v = _parse_version_string("1.0.0-beta")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
        assert v.pre_release == "beta"

    def test_parse_greater_than_constraint(self):
        """Test parsing > constraints."""
        constraints = parse_constraint(">1.0.0")
        assert len(constraints) == 1
        assert constraints[0].operator == ">"

    def test_parse_greater_than_or_equal_constraint(self):
        """Test parsing >= constraints."""
        constraints = parse_constraint(">=1.0.0")
        assert len(constraints) == 1
        assert constraints[0].operator == ">="

    def test_parse_less_than_constraint(self):
        """Test parsing < constraints."""
        constraints = parse_constraint("<2.0.0")
        assert len(constraints) == 1
        assert constraints[0].operator == "<"

    def test_parse_exact_constraint(self):
        """Test parsing exact (==) constraints."""
        constraints = parse_constraint("==1.0.0")
        assert len(constraints) == 1
        assert constraints[0].operator == "=="

    def test_parse_range_constraints(self):
        """Test parsing compound constraints."""
        constraints = parse_constraint(">=1.0.0 <2.0.0")
        assert len(constraints) == 2


class TestVersionComparison:
    """Test version comparison logic."""

    def test_version_equality(self):
        """Test version equality."""
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 3)
        v3 = Version(1, 2, 4)

        assert v1 == v2
        assert v1 != v3

    def test_version_less_than(self):
        """Test version less than."""
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 4)
        v3 = Version(2, 0, 0)

        assert v1 < v2
        assert v1 < v3
        assert v2 < v3

    def test_version_greater_than(self):
        """Test version greater than."""
        v1 = Version(2, 0, 0)
        v2 = Version(1, 9, 9)

        assert v1 > v2

    def test_pre_release_comparison(self):
        """Test pre-release version comparison."""
        v1 = Version(1, 0, 0, pre_release="alpha")
        v2 = Version(1, 0, 0)

        # Pre-release < release
        assert v1 < v2
        assert v2 > v1


class TestIsVersionAffected:
    """Test constraint matching."""

    def test_matches_exact_version(self):
        """Test exact version matching."""
        assert is_version_affected("1.0.0", "==1.0.0") is True
        assert is_version_affected("1.0.0", "==1.0.1") is False

    def test_matches_greater_than(self):
        """Test greater than constraint."""
        assert is_version_affected("2.0.0", ">1.0.0") is True
        assert is_version_affected("1.0.0", ">1.0.0") is False

    def test_matches_greater_than_or_equal(self):
        """Test greater than or equal constraint."""
        assert is_version_affected("1.0.0", ">=1.0.0") is True
        assert is_version_affected("2.0.0", ">=1.0.0") is True
        assert is_version_affected("0.9.0", ">=1.0.0") is False

    def test_matches_less_than(self):
        """Test less than constraint."""
        assert is_version_affected("0.9.0", "<1.0.0") is True
        assert is_version_affected("1.0.0", "<1.0.0") is False


class TestSecurityAdvisoryDatabase:
    """Test security advisory database operations."""

    def test_database_initialization(self):
        """Test database initialization."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            db = SecurityAdvisoryDatabase(db_path=db_path)
            assert os.path.exists(db_path)
            assert db.get_advisory_count() == 0
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_add_advisory(self):
        """Test adding an advisory to the database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            db = SecurityAdvisoryDatabase(db_path=db_path)

            advisory = Advisory(
                id="TEST-2024-001",
                package_name="test-package",
                package_manager="python",
                affected_versions='[">=1.0.0,<2.0.0"]',
                fixed_versions='["2.0.0"]',
                severity="HIGH",
                cvss_score=7.5,
                summary="Test vulnerability",
                published_date="2024-01-01",
                references_url='["https://example.com/advisory"]',
                source="TEST"
            )

            assert db.add_advisory(advisory) is True
            assert db.get_advisory_count() == 1
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_get_advisories_for_package(self):
        """Test retrieving advisories for a package."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            db = SecurityAdvisoryDatabase(db_path=db_path)

            advisory = Advisory(
                id="TEST-2024-002",
                package_name="requests",
                package_manager="python",
                affected_versions='["<2.20.0"]',
                fixed_versions='["2.20.0"]',
                severity="HIGH",
                cvss_score=7.5,
                summary="Test vulnerability",
                published_date="2024-01-01",
                references_url='[]',
                source="TEST"
            )

            db.add_advisory(advisory)

            advisories = db.get_advisories_for_package("requests", "python")
            assert len(advisories) == 1
            assert advisories[0].id == "TEST-2024-002"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_get_advisories_by_severity(self):
        """Test retrieving advisories by severity."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            db = SecurityAdvisoryDatabase(db_path=db_path)

            advisories = [
                Advisory(
                    id=f"TEST-2024-{i:03d}",
                    package_name="test-package",
                    package_manager="python",
                    affected_versions='["<1.0.0"]',
                    fixed_versions='["1.0.0"]',
                    severity="HIGH" if i % 2 == 0 else "MEDIUM",
                    cvss_score=7.5,
                    summary="Test vulnerability",
                    published_date="2024-01-01",
                    references_url='[]',
                    source="TEST"
                )
                for i in range(4)
            ]

            for adv in advisories:
                db.add_advisory(adv)

            high_advisories = db.get_advisories_by_severity("HIGH")
            assert len(high_advisories) == 2
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestVersionValidator:
    """Test version validation logic."""

    def test_check_version_against_advisory(self):
        """Test checking version against advisory."""
        advisory = Advisory(
            id="TEST-2024-003",
            package_name="log4j",
            package_manager="java",
            affected_versions='[">=2.0.0,<2.15.0"]',
            fixed_versions='["2.15.0"]',
            severity="CRITICAL",
            cvss_score=10.0,
            summary="Log4j vulnerability",
            published_date="2021-12-10",
            references_url='[]',
            source="TEST"
        )

        # Vulnerable version
        assert check_version_against_advisory("2.14.0", advisory) is True

        # Fixed version
        assert check_version_against_advisory("2.15.0", advisory) is False

        # Out of range
        assert check_version_against_advisory("1.9.0", advisory) is False

    def test_check_version_outside_range(self):
        """Test checking version outside vulnerable range."""
        advisory = Advisory(
            id="TEST-2024-004",
            package_name="test",
            package_manager="python",
            affected_versions='[">=1.0.0,<1.5.0"]',
            fixed_versions='["1.5.0"]',
            severity="HIGH",
            cvss_score=7.0,
            summary="Test vulnerability",
            published_date="2024-01-01",
            references_url='[]',
            source="TEST"
        )

        assert check_version_against_advisory("2.0.0", advisory) is False


class TestVersionValidationResult:
    """Test VersionValidationResult dataclass."""

    def test_vulnerability_count(self):
        """Test vulnerability count property."""
        result = VersionValidationResult(
            package_name="test",
            package_version="1.0.0",
            language="python",
            vulnerabilities=[
                VersionVulnerability(
                    advisory_id="CVE-1",
                    package_name="test",
                    package_version="1.0.0",
                    affected_range=">=1.0.0",
                    fixed_versions=["1.0.1"],
                    is_vulnerable=True
                )
            ]
        )

        assert result.vulnerability_count == 1
        assert result.has_vulnerabilities is True

    def test_secure_package(self):
        """Test secure package result."""
        result = VersionValidationResult(
            package_name="test",
            package_version="1.0.0",
            language="python"
        )

        assert result.vulnerability_count == 0
        assert result.has_vulnerabilities is False
        assert result.is_secure is True


class TestPopulateSampleAdvisories:
    """Test populating sample advisories."""

    def test_populate_advisories(self):
        """Test that sample advisories are populated correctly."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            # Patch the database path
            from src.output_security import security_advisory
            original_db = security_advisory._db_instance
            security_advisory._db_instance = None

            # Create database with custom path
            db = SecurityAdvisoryDatabase(db_path=db_path)
            security_advisory._db_instance = db

            # Populate sample advisories
            count = populate_sample_advisories()
            assert count == 6

            # Verify count
            assert db.get_advisory_count() == 6

            # Restore original
            security_advisory._db_instance = original_db
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            from src.output_security import security_advisory
            security_advisory._db_instance = None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_constraint(self):
        """Test parsing empty constraint raises ValueError."""
        with pytest.raises(ValueError):
            parse_constraint("")

    def test_invalid_version(self):
        """Test parsing invalid version raises ValueError."""
        with pytest.raises(ValueError):
            _parse_version_string("not-a-version")

    def test_none_version_handling(self):
        """Test handling of None/null versions."""
        result = VersionValidationResult(
            package_name="test",
            package_version="",
            language="python"
        )
        assert result.package_version == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])