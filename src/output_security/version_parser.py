""" Version Parser Module.

Parses and compares version strings and version constraints for security vulnerability checking.
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union


class VersionComparison(Enum):
    """Enum for version comparison results."""
    LESS_THAN = -1
    EQUAL = 0
    GREATER_THAN = 1


@dataclass
class Version:
    """Represents a parsed version number with major, minor, patch, and pre-release components."""
    major: int
    minor: int
    patch: int
    pre_release: Optional[str] = None
    build_metadata: Optional[str] = None

    def __post_init__(self):
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version components cannot be negative")

    def __str__(self) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            result += f"-{self.pre_release}"
        if self.build_metadata:
            result += f"+{self.build_metadata}"
        return result

    def __repr__(self) -> str:
        return f"Version(major={self.major}, minor={self.minor}, patch={self.patch}, pre_release={self.pre_release!r}, build_metadata={self.build_metadata!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major == other.major and
                self.minor == other.minor and
                self.patch == other.patch and
                self.pre_release == other.pre_release)

    def __lt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.compare(other) == VersionComparison.LESS_THAN

    def __le__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        comparison = self.compare(other)
        return comparison in (VersionComparison.LESS_THAN, VersionComparison.EQUAL)

    def __gt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.compare(other) == VersionComparison.GREATER_THAN

    def __ge__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        comparison = self.compare(other)
        return comparison in (VersionComparison.GREATER_THAN, VersionComparison.EQUAL)

    def compare(self, other: "Version") -> VersionComparison:
        """Compare this version with another version.

        Args:
            other: Version to compare against

        Returns:
            VersionComparison enum value
        """
        # Compare major versions
        if self.major < other.major:
            return VersionComparison.LESS_THAN
        if self.major > other.major:
            return VersionComparison.GREATER_THAN

        # Compare minor versions
        if self.minor < other.minor:
            return VersionComparison.LESS_THAN
        if self.minor > other.minor:
            return VersionComparison.GREATER_THAN

        # Compare patch versions
        if self.patch < other.patch:
            return VersionComparison.LESS_THAN
        if self.patch > other.patch:
            return VersionComparison.GREATER_THAN

        # Compare pre-release versions (pre-release < release)
        if self.pre_release is not None and other.pre_release is None:
            return VersionComparison.LESS_THAN
        if self.pre_release is None and other.pre_release is not None:
            return VersionComparison.GREATER_THAN
        if self.pre_release is not None and other.pre_release is not None:
            if self.pre_release < other.pre_release:
                return VersionComparison.LESS_THAN
            if self.pre_release > other.pre_release:
                return VersionComparison.GREATER_THAN

        # Versions are equal
        return VersionComparison.EQUAL


@dataclass
class VersionConstraint:
    """Represents a version constraint for matching against versions."""
    operator: str
    version: Version

    def __post_init__(self):
        if self.operator not in [">=", "<=", ">", "<", "==", "!="]:
            raise ValueError(f"Invalid operator: {self.operator}")

    def matches(self, version: Version) -> bool:
        """Check if a version matches this constraint.

        Args:
            version: Version to check

        Returns:
            True if version matches the constraint, False otherwise
        """
        if self.operator == ">=":
            return version >= self.version
        elif self.operator == "<=":
            return version <= self.version
        elif self.operator == ">":
            return version > self.version
        elif self.operator == "<":
            return version < self.version
        elif self.operator == "==":
            return version == self.version
        elif self.operator == "!=":
            return version != self.version
        return False

    def __str__(self) -> str:
        return f"{self.operator}{self.version}"

    def __repr__(self) -> str:
        return f"VersionConstraint(operator={self.operator!r}, version={self.version!r})"


# Version string parsing patterns
VERSION_PATTERN = re.compile(
    r'^v?'  # Optional 'v' prefix
    r'(?P<major>\d+)'
    r'(?:\.(?P<minor>\d+))?'
    r'(?:\.(?P<patch>\d+))?'
    r'(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
    r'(?:\+(?P<buildmetadata>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
    r'$'
)


def _parse_version_string(version_str: str) -> Version:
    """
    Parse a version string into a Version object.

    Args:
        version_str: Version string to parse (e.g., "1.2.3", "1.0.0-alpha", "2.1.0+build.123")

    Returns:
        Version object with parsed components

    Raises:
        ValueError: If the version string cannot be parsed
    """
    if not version_str:
        raise ValueError("Version string cannot be empty")

    # Remove leading 'v' if present
    version_str = version_str.lstrip('v')

    # Try to match the version pattern
    match = VERSION_PATTERN.match(version_str)
    if not match:
        raise ValueError(f"Invalid version string: {version_str}")

    major = int(match.group("major"))
    minor = int(match.group("minor") or 0)
    patch = int(match.group("patch") or 0)
    pre_release = match.group("prerelease")
    build_metadata = match.group("buildmetadata")

    return Version(
        major=major,
        minor=minor,
        patch=patch,
        pre_release=pre_release,
        build_metadata=build_metadata
    )


def parse_constraint(constraint_str: str) -> List[VersionConstraint]:
    """
    Parse a version constraint string into a list of VersionConstraint objects.

    Args:
        constraint_str: Constraint string (e.g., ">=1.0.0 <2.0.0", ">1.2.3")

    Returns:
        List of VersionConstraint objects

    Raises:
        ValueError: If the constraint string cannot be parsed
    """
    if not constraint_str:
        raise ValueError("Constraint string cannot be empty")

    # Remove brackets and quotes if present
    constraint_str = constraint_str.strip().strip('[]').strip('"').strip("'")

    # Split by spaces to get individual constraints
    constraint_parts = constraint_str.split()

    constraints = []
    for part in constraint_parts:
        if not part:
            continue

        # Handle compound operators (>=, <=)
        if part.startswith(">="):
            operator = ">="
            version_str = part[2:]
        elif part.startswith("<="):
            operator = "<="
            version_str = part[2:]
        elif part.startswith(">"):
            operator = ">"
            version_str = part[1:]
        elif part.startswith("<"):
            operator = "<"
            version_str = part[1:]
        elif part.startswith("=="):
            operator = "=="
            version_str = part[2:]
        elif part.startswith("!="):
            operator = "!="
            version_str = part[2:]
        else:
            # Default to equality if no operator specified
            operator = "=="
            version_str = part

        version = _parse_version_string(version_str)
        constraints.append(VersionConstraint(operator=operator, version=version))

    return constraints


def is_version_affected(version_str: str, constraint_str: str) -> bool:
    """
    Check if a version string is affected by a version constraint.

    Args:
        version_str: Version string to check
        constraint_str: Version constraint string

    Returns:
        True if version is affected, False otherwise
    """
    version = _parse_version_string(version_str)
    constraints = parse_constraint(constraint_str)

    # Version must match ALL constraints (AND relationship)
    for constraint in constraints:
        if not constraint.matches(version):
            return False

    return True


def compare_versions(version1_str: str, version2_str: str) -> VersionComparison:
    """
    Compare two version strings.

    Args:
        version1_str: First version string
        version2_str: Second version string

    Returns:
        VersionComparison enum value
    """
    version1 = _parse_version_string(version1_str)
    version2 = _parse_version_string(version2_str)
    return version1.compare(version2)


def get_version_info(version_str: str) -> dict:
    """
    Get detailed information about a version string.

    Args:
        version_str: Version string to analyze

    Returns:
        Dictionary with version information
    """
    version = _parse_version_string(version_str)
    return {
        "original": version_str,
        "major": version.major,
        "minor": version.minor,
        "patch": version.patch,
        "pre_release": version.pre_release,
        "build_metadata": version.build_metadata,
        "is_prerelease": version.pre_release is not None,
        "string_representation": str(version),
    }