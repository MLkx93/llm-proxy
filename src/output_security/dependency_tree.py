"""
Dependency Tree Module.

Provides data structures and algorithms for managing and analyzing
package dependency trees with transitive vulnerability tracking.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum
import json


class RiskLevel(Enum):
    """Risk level classification for dependencies."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


@dataclass
class DependencyNode:
    """Represents a single dependency node in the tree."""
    name: str
    version: str
    ecosystem: str
    parent: Optional['DependencyNode'] = None
    children: List['DependencyNode'] = field(default_factory=list)
    depth: int = 0
    is_direct: bool = True
    
    # Vulnerability info
    vulnerability_count: int = 0
    highest_severity: str = "NONE"
    highest_cvss: float = 0.0
    advisory_ids: List[str] = field(default_factory=list)
    
    # Metadata
    license: Optional[str] = None
    is_deprecated: bool = False
    maintainer_status: str = "unknown"  # "active", "inactive", "unknown"
    
    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (no children)."""
        return len(self.children) == 0
    
    @property
    def path(self) -> List[str]:
        """Get the path from root to this node."""
        path = [self.name]
        node = self.parent
        while node:
            path.insert(0, node.name)
            node = node.parent
        return path
    
    @property
    def path_string(self) -> str:
        """Get path as a string (e.g., 'root -> child1 -> child2')."""
        return " -> ".join(self.path)
    
    @property
    def risk_level(self) -> RiskLevel:
        """Determine risk level based on vulnerability severity."""
        severity_map = {
            "CRITICAL": RiskLevel.CRITICAL,
            "HIGH": RiskLevel.HIGH,
            "MEDIUM": RiskLevel.MEDIUM,
            "LOW": RiskLevel.LOW,
        }
        return severity_map.get(self.highest_severity.upper(), RiskLevel.NONE)
    
    def get_all_vulnerabilities(self) -> Set[str]:
        """Get all vulnerability IDs in this node's subtree."""
        vulns = set(self.advisory_ids)
        for child in self.children:
            vulns.update(child.get_all_vulnerabilities())
        return vulns
    
    def get_total_vulnerability_count(self) -> int:
        """Get total vulnerability count in this node's subtree."""
        count = self.vulnerability_count
        for child in self.children:
            count += child.get_total_vulnerability_count()
        return count


@dataclass
class DependencyTree:
    """Represents a complete dependency tree."""
    root: DependencyNode
    package_name: str
    package_version: str
    ecosystem: str
    total_nodes: int = 0
    total_vulnerabilities: int = 0
    
    def find_node(self, name: str, version: Optional[str] = None) -> Optional[DependencyNode]:
        """Find a node by name (and optionally version) in the tree."""
        def search(node: DependencyNode) -> Optional[DependencyNode]:
            if node.name == name and (version is None or node.version == version):
                return node
            for child in node.children:
                result = search(child)
                if result:
                    return result
            return None
        
        return search(self.root)
    
    def get_all_nodes(self) -> List[DependencyNode]:
        """Get all nodes in the tree."""
        nodes = []
        
        def traverse(node: DependencyNode):
            nodes.append(node)
            for child in node.children:
                traverse(child)
        
        traverse(self.root)
        return nodes
    
    def get_vulnerable_nodes(self) -> List[DependencyNode]:
        """Get all nodes with vulnerabilities."""
        return [node for node in self.get_all_nodes() if node.vulnerability_count > 0]
    
    def get_critical_nodes(self) -> List[DependencyNode]:
        """Get all nodes with CRITICAL severity vulnerabilities."""
        return [node for node in self.get_all_nodes() if node.highest_severity == "CRITICAL"]
    
    def get_high_risk_nodes(self) -> List[DependencyNode]:
        """Get all nodes with HIGH or CRITICAL severity vulnerabilities."""
        return [node for node in self.get_all_nodes() 
                if node.highest_severity in ("HIGH", "CRITICAL")]
    
    def calculate_tree_risk_score(self) -> float:
        """
        Calculate overall risk score for the dependency tree.
        
        Score calculation:
        - CRITICAL vulnerability: 10 points
        - HIGH vulnerability: 7 points
        - MEDIUM vulnerability: 4 points
        - LOW vulnerability: 1 point
        - Score is weighted by depth (deeper = more risk)
        """
        score = 0.0
        
        def calculate_node_score(node: DependencyNode) -> float:
            severity_weights = {
                "CRITICAL": 10.0,
                "HIGH": 7.0,
                "MEDIUM": 4.0,
                "LOW": 1.0,
            }
            
            weight = severity_weights.get(node.highest_severity.upper(), 0.0)
            
            # Weight by depth (transitive deps are riskier)
            depth_multiplier = 1.0 + (node.depth * 0.1)
            
            node_score = weight * depth_multiplier * node.vulnerability_count
            
            for child in node.children:
                node_score += calculate_node_score(child)
            
            return node_score
        
        return calculate_node_score(self.root)
    
    def get_dependency_conflicts(self) -> List[Dict]:
        """Find version conflicts in the dependency tree."""
        conflicts = []
        version_map: Dict[str, List[Tuple[str, str]]] = {}
        
        def collect_versions(node: DependencyNode):
            if node.name not in version_map:
                version_map[node.name] = []
            version_map[node.name].append((node.version, node.path_string))
            
            for child in node.children:
                collect_versions(child)
        
        collect_versions(self.root)
        
        for name, versions in version_map.items():
            unique_versions = set(v[0] for v in versions)
            if len(unique_versions) > 1:
                conflicts.append({
                    "package": name,
                    "versions": list(unique_versions),
                    "occurrences": versions
                })
        
        return conflicts
    
    def get_upgrade_recommendations(self) -> List[Dict]:
        """Generate upgrade recommendations for vulnerable packages."""
        recommendations = []
        
        for node in self.get_vulnerable_nodes():
            if node.advisory_ids:
                recommendations.append({
                    "package": node.name,
                    "version": node.version,
                    "path": node.path_string,
                    "vulnerability_count": node.vulnerability_count,
                    "highest_severity": node.highest_severity,
                    "advisory_ids": node.advisory_ids,
                    "is_direct": node.is_direct
                })
        
        # Sort by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        recommendations.sort(key=lambda x: severity_order.get(x["highest_severity"], 4))
        
        return recommendations
    
    def to_dict(self) -> Dict:
        """Convert tree to dictionary for serialization."""
        def node_to_dict(node: DependencyNode) -> Dict:
            return {
                "name": node.name,
                "version": node.version,
                "ecosystem": node.ecosystem,
                "depth": node.depth,
                "is_direct": node.is_direct,
                "vulnerability_count": node.vulnerability_count,
                "highest_severity": node.highest_severity,
                "highest_cvss": node.highest_cvss,
                "advisory_ids": node.advisory_ids,
                "license": node.license,
                "is_deprecated": node.is_deprecated,
                "children": [node_to_dict(child) for child in node.children]
            }
        
        return {
            "package": self.package_name,
            "version": self.package_version,
            "ecosystem": self.ecosystem,
            "total_nodes": self.total_nodes,
            "total_vulnerabilities": self.total_vulnerabilities,
            "risk_score": self.calculate_tree_risk_score(),
            "tree": node_to_dict(self.root)
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert tree to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @staticmethod
    def from_dict(data: Dict) -> 'DependencyTree':
        """Reconstruct tree from dictionary."""
        def dict_to_node(d: Dict, parent: Optional[DependencyNode] = None) -> DependencyNode:
            node = DependencyNode(
                name=d["name"],
                version=d["version"],
                ecosystem=d["ecosystem"],
                depth=d["depth"],
                is_direct=d["is_direct"],
                vulnerability_count=d["vulnerability_count"],
                highest_severity=d["highest_severity"],
                highest_cvss=d["highest_cvss"],
                advisory_ids=d["advisory_ids"],
                license=d.get("license"),
                is_deprecated=d.get("is_deprecated", False),
                parent=parent
            )
            node.children = [dict_to_node(child, node) for child in d.get("children", [])]
            return node
        
        root = dict_to_node(data["tree"])
        
        tree = DependencyTree(
            root=root,
            package_name=data["package"],
            package_version=data["version"],
            ecosystem=data["ecosystem"],
            total_nodes=data["total_nodes"],
            total_vulnerabilities=data["total_vulnerabilities"]
        )
        
        return tree


def create_dependency_tree(
    package_name: str,
    package_version: str,
    ecosystem: str,
    dependencies: List[Dict]
) -> DependencyTree:
    """
    Create a DependencyTree from a list of dependency specifications.
    
    Args:
        package_name: Root package name
        package_version: Root package version
        ecosystem: Package ecosystem (python, javascript, java, etc.)
        dependencies: List of dependency dicts with name, version, children
    
    Returns:
        DependencyTree object
    """
    def build_tree(
        deps: List[Dict],
        parent: DependencyNode,
        is_direct: bool = True
    ) -> None:
        for dep in deps:
            child = DependencyNode(
                name=dep["name"],
                version=dep["version"],
                ecosystem=ecosystem,
                parent=parent,
                depth=parent.depth + 1,
                is_direct=is_direct,
                vulnerability_count=dep.get("vulnerability_count", 0),
                highest_severity=dep.get("highest_severity", "NONE"),
                highest_cvss=dep.get("highest_cvss", 0.0),
                advisory_ids=dep.get("advisory_ids", []),
                license=dep.get("license"),
                is_deprecated=dep.get("is_deprecated", False)
            )
            parent.children.append(child)
            
            if "children" in dep:
                build_tree(dep["children"], child, is_direct=False)
    
    root = DependencyNode(
        name=package_name,
        version=package_version,
        ecosystem=ecosystem,
        depth=0,
        is_direct=True
    )
    
    build_tree(dependencies, root)
    
    # Calculate total nodes
    nodes = []
    def count_nodes(node: DependencyNode):
        nodes.append(node)
        for child in node.children:
            count_nodes(child)
    count_nodes(root)
    
    tree = DependencyTree(
        root=root,
        package_name=package_name,
        package_version=package_version,
        ecosystem=ecosystem,
        total_nodes=len(nodes),
        total_vulnerabilities=root.get_total_vulnerability_count()
    )
    
    return tree
