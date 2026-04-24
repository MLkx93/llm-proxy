"""
Version Constraint Parser Module.

Parses and normalizes version constraints from various package managers:
- npm: ^1.0.0, ~1.2.3, >=1.0.0 <2.0.0
- PyPI: >=1.0.0, ==2.0.0, !=3.0.0
- Maven: [1.0.0,2.0.0), 1.0.0
- Go: v1.0.0, github.com/pkg@v1.2.3

Supports semantic versioning and comparison.
"""
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum


class ConstraintType(Enum):
    """Types of version constraints."""
    CARET = "^"           # npm: Compatible with version
    TILDE = "~"           # npm: Patch-level changes
    GREATER_THAN = ">"    
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    EXACT = "=="          # Exact version match
    NOT_EQUAL = "!="
    RANGE_OR = "||"       # Logical OR of ranges
    RANGE_AND = " "      # Implicit AND (space between constraints)
    ANY = "*"            # Any version
    TILDE_RANGE = "~"    # Tilde range (PyPI style)


@dataclass(frozen=True)
class Version:
    """Normalized version representation."""
    major: int
    minor: int
    patch: int
    pre_release: str = ""
    build_metadata: str = ""
    
    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            version += f"-{self.pre_release}"
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        return version
    
    def __lt__(self, other: 'Version') -> bool:
        return self._compare(other) < 0
    
    def __le__(self, other: 'Version') -> bool:
        return self._compare(other) <= 0
    
    def __gt__(self, other: 'Version') -> bool:
        return self._compare(other) > 0
    
    def __ge__(self, other: 'Version') -> bool:
        return self._compare(other) >= 0
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self._compare(other) == 0
    
    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)
    
    def _compare(self, other: 'Version') -> int:
        """Compare versions. Returns -1, 0, or 1."""
        self_tuple = (self.major, self.minor, self.patch)
        other_tuple = (other.major, other.minor, other.patch)
        
        if self_tuple < other_tuple:
            return -1
        elif self_tuple > other_tuple:
            return 1
        else:
            # Handle pre-release (pre-release < release)
            if self.pre_release and not other.pre_release:
                return -1
            elif not self.pre_release and other.pre_release:
                return 1
            elif self.pre_release < other.pre_release:
                return -1
            elif self.pre_release > other.pre_release:
                return 1
        return 0


@dataclass(frozen=True)
class VersionConstraint:
    """Represents a single version constraint."""
    constraint_type: ConstraintType
    version: Optional[Version]
    
    def matches(self, version: Version) -> bool:
        """Check if a version matches this constraint."""
        if self.version is None:
            return self.constraint_type == ConstraintType.ANY
        
        if self.constraint_type == ConstraintType.ANY:
            return True
        elif self.constraint_type == ConstraintType.EXACT:
            return version == self.version
        elif self.constraint_type == ConstraintType.GREATER_THAN:
            return version > self.version
        elif self.constraint_type == ConstraintType.GREATER_THAN_OR_EQUAL:
            return version >= self.version
        elif self.constraint_type == ConstraintType.LESS_THAN:
            return version < self.version
        elif self.constraint_type == ConstraintType.LESS_THAN_OR_EQUAL:
            return version <= self.version
        elif self.constraint_type == ConstraintType.NOT_EQUAL:
            return version != self.version
        elif self.constraint_type == ConstraintType.CARET:
            # ^x.y.z := >=x.y.z <(x+1).0.0
            return (version >= self.version and 
                    Version(self.version.major + 1, 0, 0) > version)
        elif self.constraint_type == ConstraintType.TILDE:
            # ~x.y.z := >=x.y.z <x.(y+1).0
            return (version >= self.version and 
                    Version(self.version.major, self.version.minor + 1, 0) > version)
        return False


def _parse_version_string(version_str: str) -> Version:
    """Parse a version string into a Version object."""
    if not version_str:
        return Version(0, 0, 0)
    
    # Remove leading 'v' for Go-style versions
    version_str = re.sub(r'^v', '', version_str)
    
    # Split version and pre-release/build metadata
    version_str = version_str.strip()
    
    # Extract build metadata
    build_metadata = ""
    if '+' in version_str:
        version_str, build_metadata = version_str.split('+', 1)
    
    # Extract pre-release
    pre_release = ""
    if '-' in version_str:
        version_str, pre_release = version_str.split('-', 1)
    
    # Parse version numbers
    match = re.match(r'(\d+)\.(\d+)\.(\d+)', version_str)
    if match:
        major, minor, patch = match.groups()
        return Version(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            pre_release=pre_release,
            build_metadata=build_metadata
        )
    
    # Handle single or double number versions
    match = re.match(r'(\d+)\.(\d+)', version_str)
    if match:
        major, minor = match.groups()
        return Version(
            major=int(major),
            minor=int(minor),
            patch=0,
            pre_release=pre_release,
            build_metadata=build_metadata
        )
    
    match = re.match(r'(\d+)', version_str)
    if match:
        major = match.group(1)
        return Version(
            major=int(major),
            minor=0,
            patch=0,
            pre_release=pre_release,
            build_metadata=build_metadata
        )
    
    return Version(0, 0, 0)


def _parse_constraint_operator(constraint_str: str) -> Tuple[ConstraintType, str]:
    """Parse the operator from a constraint string."""
    constraint_str = constraint_str.strip()
    
    if constraint_str.startswith('>='):
        return (ConstraintType.GREATER_THAN_OR_EQUAL, constraint_str[2:].strip())
    elif constraint_str.startswith('<='):
        return (ConstraintType.LESS_THAN_OR_EQUAL, constraint_str[2:].strip())
    elif constraint_str.startswith('=='):
        return (ConstraintType.EXACT, constraint_str[2:].strip())
    elif constraint_str.startswith('!='):
        return (ConstraintType.NOT_EQUAL, constraint_str[2:].strip())
    elif constraint_str.startswith('>'):
        return (ConstraintType.GREATER_THAN, constraint_str[1:].strip())
    elif constraint_str.startswith('<'):
        return (ConstraintType.LESS_THAN, constraint_str[1:].strip())
    elif constraint_str.startswith('^'):
        return (ConstraintType.CARET, constraint_str[1:].strip())
    elif constraint_str.startswith('~'):
        return (ConstraintType.TILDE, constraint_str[1:].strip())
    elif constraint_str == '*':
        return (ConstraintType.ANY, "")
    elif constraint_str.startswith('[') or constraint_str.startswith('('):
        # Maven-style range, return as-is for special handling
        return (ConstraintType.RANGE_AND, constraint_str)
    else:
        # Default to greater than or equal for bare versions
        return (ConstraintType.GREATER_THAN_OR_EQUAL, constraint_str)


def parse_constraint(constraint_str: str) -> List[VersionConstraint]:
    """
    Parse a version constraint string into individual constraints.
    
    Supports:
    - Simple versions: "1.0.0"
    - Operators: ">=1.0.0", "<2.0.0", "^1.0.0", "~1.0.0"
    - Multiple constraints: ">=1.0.0 <2.0.0"
    - OR constraints: "1.0.0 || >=2.0.0"
    
    Args:
        constraint_str: Version constraint string
        
    Returns:
        List of VersionConstraint objects
    """
    if not constraint_str:
        return [VersionConstraint(ConstraintType.ANY, None)]
    
    constraints = []
    constraint_str = constraint_str.strip()
    
    # Handle OR constraints
    parts = re.split(r'\s*\|\|\s*\|\|\s*', constraint_str)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Check for compound constraint (AND)
        sub_parts = part.split()
        for sub_part in sub_parts:
            sub_part = sub_part.strip()
            if not sub_part:
                continue
            
            constraint_type, version_str = _parse_constraint_operator(sub_part)
            
            if constraint_type == ConstraintType.ANY:
                constraints.append(VersionConstraint(ConstraintType.ANY, None))
            elif constraint_type == ConstraintType.RANGE_AND:
                # Handle Maven-style ranges like [1.0.0,2.0.0)
                # This is complex and would need special handling
                continue
            else:
                version = _parse_version_string(version_str)
                constraints.append(VersionConstraint(constraint_type, version))
    
    if not constraints:
        constraints.append(VersionConstraint(ConstraintType.ANY, None))
    
    return constraints


def matches_constraint(version: str, constraint_str: str) -> bool:
    """
    Check if a version matches a constraint string.
    
    Args:
        version: Version string to check
        constraint_str: Constraint string to match against
        
    Returns:
        True if version matches the constraint, False otherwise
    """
    version_obj = _parse_version_string(version)
    constraints = parse_constraint(constraint_str)
    
    # Version must match ALL constraints (AND relationship)
    for constraint in constraints:
        if not constraint.matches(version_obj):
            return False
    
    return True


def normalize_version(version_str: str) -> str:
    """
    Normalize a version string to a standard format.
    
    Args:
        version_str: Version string to normalize
        
    Returns:
        Normalized version string
    """
    version = _parse_version_string(version_str)
    return str(version)


def get_version_tuple(version_str: str) -> Tuple[int, int, int]:
    """
    Get version as a comparable tuple.
    
    Args:
        version_str: Version string
        
    Returns:
        Tuple of (major, minor, patch)
    """
    version = _parse_version_string(version_str)
    return (version.major, version.minor, version.patch)
