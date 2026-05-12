"""
Dependency Resolver Module.

Resolves package dependency trees for various package managers:
- Python (pip)
- JavaScript (npm)
- Java (Maven)
- Ruby (RubyGems)
- Go (Go modules)

Provides comprehensive transitive dependency analysis with vulnerability tracking.
"""
import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any
from abc import ABC, abstractmethod
from enum import Enum

from .dependency_tree import DependencyTree, DependencyNode, create_dependency_tree
from .security_advisory import get_advisory_database
from .version_validator import check_version_against_advisory, get_first_fixed_version
from src.proxy.logging import get_logger

logger = get_logger("dependency_resolver")


class Ecosystem(Enum):
    """Supported package ecosystems."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    JAVA = "java"
    RUBY = "ruby"
    GO = "go"
    RUST = "rust"


@dataclass
class ResolvedDependency:
    """Represents a resolved dependency."""
    name: str
    version: str
    ecosystem: str
    children: List['ResolvedDependency'] = field(default_factory=list)
    depth: int = 0
    is_direct: bool = True
    source: Optional[str] = None  # Which package requires this dependency


@dataclass
class DependencyAnalysisResult:
    """Result of dependency tree analysis."""
    package_name: str
    package_version: str
    ecosystem: str
    tree: DependencyTree
    total_dependencies: int = 0
    direct_dependencies: int = 0
    transitive_dependencies: int = 0
    vulnerable_packages: int = 0
    critical_vulnerabilities: int = 0
    high_vulnerabilities: int = 0
    medium_vulnerabilities: int = 0
    low_vulnerabilities: int = 0
    risk_score: float = 0.0
    has_conflicts: bool = False
    upgrade_recommendations: List[Dict] = field(default_factory=list)
    
    @property
    def is_secure(self) -> bool:
        """Check if the dependency tree is secure."""
        return self.vulnerable_packages == 0
    
    @property
    def security_grade(self) -> str:
        """Get a letter grade for the security posture."""
        if self.critical_vulnerabilities > 0:
            return "F"
        elif self.high_vulnerabilities > 0:
            return "D"
        elif self.medium_vulnerabilities > 0:
            return "C"
        elif self.low_vulnerabilities > 0:
            return "B"
        elif self.vulnerable_packages > 0:
            return "B"
        else:
            return "A"


class BaseResolver(ABC):
    """Base class for ecosystem-specific dependency resolvers."""
    
    @abstractmethod
    async def get_direct_dependencies(self, package: str, version: str) -> List[Dict]:
        """Get direct dependencies of a package."""
        pass
    
    @abstractmethod
    async def get_package_metadata(self, package: str, version: Optional[str] = None) -> Dict:
        """Get package metadata including version information."""
        pass


class PythonResolver(BaseResolver):
    """Resolver for Python packages using pip and PyPI."""
    
    async def get_direct_dependencies(self, package: str, version: str) -> List[Dict]:
        """Get direct dependencies using pip show."""
        try:
            result = subprocess.run(
                ["pip", "show", package],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.warning("package_not_found", package=package)
                return []
            
            # Parse dependencies from pip show output
            deps = []
            in_requires = False
            
            for line in result.stdout.split('\n'):
                if line.startswith('Requires:'):
                    in_requires = True
                    continue
                
                if in_requires:
                    if line.strip() == '':
                        break
                    # Parse requirement: package (version)
                    req = line.strip()
                    if req:
                        dep_info = self._parse_requirement(req)
                        deps.append(dep_info)
            
            return deps
        
        except subprocess.TimeoutExpired:
            logger.error("pip_timeout", package=package)
            return []
        except Exception as e:
            logger.error("pip_error", package=package, error=str(e))
            return []
    
    def _parse_requirement(self, requirement: str) -> Dict:
        """Parse a pip requirement string."""
        # Simple parsing: "package (version)" or "package"
        import re
        
        match = re.match(r'([a-zA-Z0-9_-]+)\s*(?:\(([^)]+)\))?', requirement)
        if match:
            name = match.group(1)
            version = match.group(2) if match.group(2) else "unknown"
            return {"name": name, "version": version}
        
        return {"name": requirement, "version": "unknown"}
    
    async def get_package_metadata(self, package: str, version: Optional[str] = None) -> Dict:
        """Get package metadata from PyPI."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://pypi.org/pypi/{package}/json", timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    info = data.get("info", {})
                    
                    return {
                        "name": info.get("name"),
                        "version": info.get("version"),
                        "summary": info.get("summary"),
                        "license": info.get("license"),
                        "home_page": info.get("home_page"),
                        "requires_python": info.get("requires_python"),
                        "deprecated": info.get("deprecated", False)
                    }
        except Exception as e:
            logger.error("pypi_error", package=package, error=str(e))
        
        return {}
    
    async def get_pip_tree(self, package: str) -> Optional[Dict]:
        """Get dependency tree using pipdeptree if available."""
        try:
            result = subprocess.run(
                ["pipdeptree", "--packages", package, "--json-tree"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("pipdeptree_not_available")
        
        return None


class JavaScriptResolver(BaseResolver):
    """Resolver for JavaScript packages using npm."""
    
    async def get_direct_dependencies(self, package: str, version: str) -> List[Dict]:
        """Get direct dependencies using npm view."""
        try:
            result = subprocess.run(
                ["npm", "view", package, "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return []
            
            data = json.loads(result.stdout)
            deps = data.get("dependencies", {})
            
            return [
                {"name": name, "version": ver}
                for name, ver in deps.items()
            ]
        
        except subprocess.TimeoutExpired:
            logger.error("npm_timeout", package=package)
            return []
        except Exception as e:
            logger.error("npm_error", package=package, error=str(e))
            return []
    
    async def get_package_metadata(self, package: str, version: Optional[str] = None) -> Dict:
        """Get package metadata from npm registry."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                url = f"https://registry.npmjs.org/{package}"
                if version:
                    url += f"/{version}"
                else:
                    url += "/latest"
                
                response = await client.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "name": data.get("name"),
                        "version": data.get("version"),
                        "description": data.get("description"),
                        "license": data.get("license"),
                        "deprecated": data.get("deprecated", False)
                    }
        except Exception as e:
            logger.error("npm_registry_error", package=package, error=str(e))
        
        return {}
    
    async def get_npm_tree(self, package: str) -> Optional[Dict]:
        """Get dependency tree using npm ls if available."""
        try:
            result = subprocess.run(
                ["npm", "ls", package, "--json", "--all"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("npm_not_available")
        
        return None


class JavaResolver(BaseResolver):
    """Resolver for Java packages using Maven."""
    
    async def get_direct_dependencies(self, package: str, version: str) -> List[Dict]:
        """Get dependencies using Maven dependency:list."""
        try:
            result = subprocess.run(
                ["mvn", "dependency:list", "-DincludeScope=compile"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                deps = []
                in_deps = False
                
                for line in result.stdout.split('\n'):
                    if 'The following files have been resolved:' in line:
                        in_deps = True
                        continue
                    
                    if in_deps and line.strip():
                        # Parse: groupId:artifactId:version
                        parts = line.strip().split(':')
                        if len(parts) >= 3:
                            deps.append({
                                "name": f"{parts[0]}.{parts[1]}",
                                "version": parts[2]
                            })
                
                return deps
        
        except subprocess.TimeoutExpired:
            logger.error("maven_timeout", package=package)
            return []
        except Exception as e:
            logger.error("maven_error", package=package, error=str(e))
            return []
    
    async def get_package_metadata(self, package: str, version: Optional[str] = None) -> Dict:
        """Get package metadata from Maven Central."""
        try:
            import httpx
            group_id, artifact_id = package.split('.', 1) if '.' in package else (package, package)
            
            async with httpx.AsyncClient() as client:
                url = f"https://search.maven.org/solrsearch/select?q=g:{group_id}+AND+a:{artifact_id}&rows=1&wt=json"
                response = await client.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    docs = data.get("response", {}).get("docs", [])
                    if docs:
                        doc = docs[0]
                        return {
                            "name": doc.get("a"),
                            "group_id": doc.get("g"),
                            "version": version or doc.get("latestVersion"),
                            "license": doc.get("license"),
                        }
        except Exception as e:
            logger.error("maven_central_error", package=package, error=str(e))
        
        return {}


# Resolver registry
_resolvers: Dict[str, BaseResolver] = {
    "python": PythonResolver(),
    "javascript": JavaScriptResolver(),
    "java": JavaResolver(),
}


def get_resolver(ecosystem: str) -> Optional[BaseResolver]:
    """Get the resolver for a specific ecosystem."""
    return _resolvers.get(ecosystem.lower())


async def resolve_dependencies(
    package: str,
    version: Optional[str],
    ecosystem: str,
    max_depth: int = 3
) -> DependencyAnalysisResult:
    """
    Resolve dependencies for a package and analyze for vulnerabilities.
    
    Args:
        package: Package name
        version: Package version (None for latest)
        ecosystem: Package ecosystem (python, javascript, java, etc.)
        max_depth: Maximum depth for transitive dependency resolution
    
    Returns:
        DependencyAnalysisResult with full analysis
    """
    resolver = get_resolver(ecosystem)
    
    if not resolver:
        logger.error("unsupported_ecosystem", ecosystem=ecosystem)
        return DependencyAnalysisResult(
            package_name=package,
            package_version=version or "unknown",
            ecosystem=ecosystem,
            tree=DependencyTree(
                root=DependencyNode(package, version or "unknown", ecosystem),
                package_name=package,
                package_version=version or "unknown",
                ecosystem=ecosystem
            )
        )
    
    # Get direct dependencies
    direct_deps = await resolver.get_direct_dependencies(package, version or "unknown")
    
    # Build dependency tree recursively
    dependencies = await _build_dependency_tree(
        resolver,
        direct_deps,
        ecosystem,
        max_depth,
        depth=0
    )
    
    # Create dependency tree
    tree = create_dependency_tree(
        package,
        version or "unknown",
        ecosystem,
        dependencies
    )
    
    # Enrich with vulnerability information
    await _enrich_with_vulnerabilities(tree, ecosystem)
    
    # Calculate statistics
    nodes = tree.get_all_nodes()
    vulnerable_nodes = tree.get_vulnerable_nodes()
    
    result = DependencyAnalysisResult(
        package_name=package,
        package_version=version or "unknown",
        ecosystem=ecosystem,
        tree=tree,
        total_dependencies=len(nodes) - 1,  # Exclude root
        direct_dependencies=sum(1 for n in nodes if n.is_direct and n.depth > 0),
        transitive_dependencies=sum(1 for n in nodes if not n.is_direct),
        vulnerable_packages=len(vulnerable_nodes),
        critical_vulnerabilities=len(tree.get_critical_nodes()),
        high_vulnerabilities=len([n for n in vulnerable_nodes if n.highest_severity == "HIGH"]),
        medium_vulnerabilities=len([n for n in vulnerable_nodes if n.highest_severity == "MEDIUM"]),
        low_vulnerabilities=len([n for n in vulnerable_nodes if n.highest_severity == "LOW"]),
        risk_score=tree.calculate_tree_risk_score(),
        has_conflicts=len(tree.get_dependency_conflicts()) > 0,
        upgrade_recommendations=tree.get_upgrade_recommendations()
    )
    
    return result


async def _build_dependency_tree(
    resolver: BaseResolver,
    dependencies: List[Dict],
    ecosystem: str,
    max_depth: int,
    depth: int
) -> List[Dict]:
    """Recursively build the dependency tree."""
    if depth >= max_depth:
        return []
    
    result = []
    
    for dep in dependencies:
        node = {
            "name": dep["name"],
            "version": dep["version"],
            "ecosystem": ecosystem,
            "children": []
        }
        
        # Get transitive dependencies
        if depth < max_depth - 1:
            transitive_deps = await resolver.get_direct_dependencies(
                dep["name"],
                dep["version"]
            )
            
            children = await _build_dependency_tree(
                resolver,
                transitive_deps,
                ecosystem,
                max_depth,
                depth + 1
            )
            node["children"] = children
        
        result.append(node)
    
    return result


async def _enrich_with_vulnerabilities(tree: DependencyTree, ecosystem: str) -> None:
    """Enrich the dependency tree with vulnerability information."""
    db = get_advisory_database()
    
    def enrich_node(node: DependencyNode):
        # Get advisories for this package
        advisories = db.get_advisories_for_package(node.name, ecosystem)
        
        for advisory in advisories:
            if check_version_against_advisory(node.version, advisory):
                node.vulnerability_count += 1
                node.advisory_ids.append(advisory.id)
                
                if advisory.cvss_score > node.highest_cvss:
                    node.highest_cvss = advisory.cvss_score
                
                if advisory.severity == "CRITICAL":
                    node.highest_severity = "CRITICAL"
                elif advisory.severity == "HIGH" and node.highest_severity != "CRITICAL":
                    node.highest_severity = "HIGH"
                elif advisory.severity == "MEDIUM" and node.highest_severity not in ("CRITICAL", "HIGH"):
                    node.highest_severity = "MEDIUM"
                elif advisory.severity == "LOW" and node.highest_severity == "NONE":
                    node.highest_severity = "LOW"
        
        # Recursively enrich children
        for child in node.children:
            enrich_node(child)
    
    enrich_node(tree.root)


def analyze_package_health(
    package: str,
    version: str,
    ecosystem: str
) -> Dict:
    """
    Quick health check for a package without full dependency resolution.
    
    Returns:
        Dictionary with health metrics
    """
    # This is a simplified version that only checks the direct package
    db = get_advisory_database()
    advisories = db.get_advisories_for_package(package, ecosystem)
    
    vulnerabilities = []
    for advisory in advisories:
        if check_version_against_advisory(version, advisory):
            vulnerabilities.append({
                "id": advisory.id,
                "severity": advisory.severity,
                "cvss_score": advisory.cvss_score,
                "summary": advisory.summary,
                "fixed_versions": advisory.get_fixed_versions_list()
            })
    
    severity_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0
    }
    
    for vuln in vulnerabilities:
        severity_counts[vuln["severity"]] = severity_counts.get(vuln["severity"], 0) + 1
    
    return DependencyAnalysisResult(
        package=package,
        version=version,
        ecosystem=ecosystem,
        vulnerabilities_found=len(vulnerabilities),
        severity_counts=severity_counts,
        is_secure=len(vulnerabilities) == 0,
        vulnerabilities=vulnerabilities
    )
