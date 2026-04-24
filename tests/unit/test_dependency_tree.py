"""
Unit tests for Dependency Tree Module (Phase 3).
"""
import pytest
from src.output_security.dependency_tree import (
    DependencyNode,
    DependencyTree,
    RiskLevel,
    create_dependency_tree,
)


class TestDependencyNode:
    """Test DependencyNode class."""
    
    def test_create_node(self):
        """Test creating a dependency node."""
        node = DependencyNode(
            name="requests",
            version="2.28.0",
            ecosystem="python"
        )
        
        assert node.name == "requests"
        assert node.version == "2.28.0"
        assert node.ecosystem == "python"
        assert node.depth == 0
        assert node.is_direct is True
        assert node.vulnerability_count == 0
    
    def test_node_is_leaf(self):
        """Test leaf node detection."""
        parent = DependencyNode("parent", "1.0.0", "python")
        child = DependencyNode("child", "2.0.0", "python", parent=parent, depth=1)
        
        assert child.is_leaf is True
        assert parent.is_leaf is False
    
    def test_node_path(self):
        """Test path property."""
        root = DependencyNode("root", "1.0.0", "python")
        level1 = DependencyNode("level1", "2.0.0", "python", parent=root, depth=1)
        level2 = DependencyNode("level2", "3.0.0", "python", parent=level1, depth=2)
        
        assert level2.path == ["root", "level1", "level2"]
        assert level2.path_string == "root -> level1 -> level2"
    
    def test_node_risk_level(self):
        """Test risk level property."""
        node = DependencyNode(
            name="test",
            version="1.0.0",
            ecosystem="python",
            highest_severity="HIGH"
        )
        
        assert node.risk_level == RiskLevel.HIGH
    
    def test_vulnerability_accumulation(self):
        """Test vulnerability count in subtree."""
        root = DependencyNode("root", "1.0.0", "python")
        child1 = DependencyNode("child1", "1.0.0", "python", parent=root, depth=1)
        child1.vulnerability_count = 2
        
        child2 = DependencyNode("child2", "2.0.0", "python", parent=child1, depth=2)
        child2.vulnerability_count = 1
        
        assert child1.get_total_vulnerability_count() == 3  # 2 + 1
        assert root.get_total_vulnerability_count() == 3


class TestDependencyTree:
    """Test DependencyTree class."""
    
    def test_create_tree(self):
        """Test creating a dependency tree."""
        deps = [
            {"name": "dep1", "version": "1.0.0"},
            {"name": "dep2", "version": "2.0.0"},
        ]
        
        tree = create_dependency_tree(
            "mypackage",
            "1.0.0",
            "python",
            deps
        )
        
        assert tree.package_name == "mypackage"
        assert tree.total_nodes == 3  # root + 2 deps
    
    def test_find_node(self):
        """Test finding a node in the tree."""
        deps = [
            {"name": "requests", "version": "2.28.0"},
            {"name": "urllib3", "version": "1.26.0"},
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        
        found = tree.find_node("requests")
        assert found is not None
        assert found.version == "2.28.0"
        
        not_found = tree.find_node("nonexistent")
        assert not_found is None
    
    def test_get_all_nodes(self):
        """Test getting all nodes."""
        deps = [
            {"name": "dep1", "version": "1.0.0"},
            {"name": "dep2", "version": "2.0.0"},
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        nodes = tree.get_all_nodes()
        
        assert len(nodes) == 3  # root + 2 deps
        assert tree.root in nodes
    
    def test_get_vulnerable_nodes(self):
        """Test getting vulnerable nodes."""
        deps = [
            {
                "name": "vuln1",
                "version": "1.0.0",
                "vulnerability_count": 1,
                "highest_severity": "HIGH"
            },
            {
                "name": "safe",
                "version": "2.0.0",
                "vulnerability_count": 0
            },
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        vulnerable = tree.get_vulnerable_nodes()
        
        assert len(vulnerable) == 1
        assert vulnerable[0].name == "vuln1"
    
    def test_calculate_risk_score(self):
        """Test tree risk score calculation."""
        deps = [
            {
                "name": "critical",
                "version": "1.0.0",
                "vulnerability_count": 1,
                "highest_severity": "CRITICAL"
            },
            {
                "name": "high",
                "version": "2.0.0",
                "vulnerability_count": 1,
                "highest_severity": "HIGH"
            },
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        score = tree.calculate_tree_risk_score()
        
        # CRITICAL = 10, HIGH = 7
        assert score >= 17.0  # 10 + 7 plus depth multipliers
    
    def test_get_dependency_conflicts(self):
        """Test detecting version conflicts."""
        deps = [
            {
                "name": "shared",
                "version": "1.0.0",
                "children": [
                    {"name": "shared", "version": "2.0.0"}  # Same name, different version
                ]
            }
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        conflicts = tree.get_dependency_conflicts()
        
        assert len(conflicts) == 1
        assert conflicts[0]["package"] == "shared"
        assert len(conflicts[0]["versions"]) == 2
    
    def test_to_dict(self):
        """Test tree serialization to dict."""
        deps = [{"name": "dep1", "version": "1.0.0"}]
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        
        d = tree.to_dict()
        
        assert d["package"] == "mypackage"
        assert d["version"] == "1.0.0"
        assert "tree" in d
        assert "risk_score" in d
    
    def test_to_json(self):
        """Test tree serialization to JSON."""
        deps = [{"name": "dep1", "version": "1.0.0"}]
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        
        json_str = tree.to_json()
        
        assert '"mypackage"' in json_str
        assert '"dep1"' in json_str
    
    def test_from_dict(self):
        """Test tree deserialization from dict."""
        deps = [{"name": "dep1", "version": "1.0.0"}]
        original = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        
        d = original.to_dict()
        restored = DependencyTree.from_dict(d)
        
        assert restored.package_name == "mypackage"
        assert restored.package_version == "1.0.0"
        assert len(restored.get_all_nodes()) == len(original.get_all_nodes())
    
    def test_get_upgrade_recommendations(self):
        """Test generating upgrade recommendations."""
        deps = [
            {
                "name": "vuln",
                "version": "1.0.0",
                "vulnerability_count": 1,
                "highest_severity": "CRITICAL",
                "advisory_ids": ["CVE-2024-001"]
            }
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        recommendations = tree.get_upgrade_recommendations()
        
        assert len(recommendations) == 1
        assert recommendations[0]["package"] == "vuln"
        assert recommendations[0]["advisory_ids"] == ["CVE-2024-001"]


class TestRiskLevel:
    """Test RiskLevel enum."""
    
    def test_risk_levels_exist(self):
        """Test all risk levels are defined."""
        assert RiskLevel.CRITICAL is not None
        assert RiskLevel.HIGH is not None
        assert RiskLevel.MEDIUM is not None
        assert RiskLevel.LOW is not None
        assert RiskLevel.NONE is not None
    
    def test_risk_level_values(self):
        """Test risk level string values."""
        assert RiskLevel.CRITICAL.value == "CRITICAL"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.NONE.value == "NONE"


class TestCreateDependencyTree:
    """Test create_dependency_tree function."""
    
    def test_simple_tree(self):
        """Test creating a simple tree."""
        tree = create_dependency_tree(
            "mypackage",
            "1.0.0",
            "python",
            []
        )
        
        assert tree.root.name == "mypackage"
        assert tree.root.is_direct is True
        assert len(tree.root.children) == 0
    
    def test_nested_dependencies(self):
        """Test creating tree with nested dependencies."""
        deps = [
            {
                "name": "dep1",
                "version": "1.0.0",
                "children": [
                    {
                        "name": "transitive",
                        "version": "2.0.0",
                        "children": []
                    }
                ]
            }
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        
        assert tree.total_nodes == 3
        dep1 = tree.find_node("dep1")
        assert dep1 is not None
        assert dep1.depth == 1
        assert dep1.is_direct is True
        
        transitive = tree.find_node("transitive")
        assert transitive is not None
        assert transitive.depth == 2
        assert transitive.is_direct is False
    
    def test_with_vulnerability_info(self):
        """Test creating tree with vulnerability information."""
        deps = [
            {
                "name": "vuln-package",
                "version": "1.0.0",
                "vulnerability_count": 2,
                "highest_severity": "HIGH",
                "highest_cvss": 8.5,
                "advisory_ids": ["CVE-2024-001", "CVE-2024-002"]
            }
        ]
        
        tree = create_dependency_tree("mypackage", "1.0.0", "python", deps)
        vuln_node = tree.find_node("vuln-package")
        
        assert vuln_node is not None
        assert vuln_node.vulnerability_count == 2
        assert vuln_node.highest_severity == "HIGH"
        assert vuln_node.highest_cvss == 8.5
        assert len(vuln_node.advisory_ids) == 2


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_dependencies(self):
        """Test with empty dependency list."""
        tree = create_dependency_tree("package", "1.0.0", "python", [])
        
        assert tree.total_nodes == 1
        assert tree.root.name == "package"
        assert len(tree.root.children) == 0
    
    def test_deep_nesting(self):
        """Test with deeply nested dependencies."""
        deps = [
            {
                "name": "level1",
                "version": "1.0.0",
                "children": [
                    {
                        "name": "level2",
                        "version": "1.0.0",
                        "children": [
                            {
                                "name": "level3",
                                "version": "1.0.0",
                                "children": []
                            }
                        ]
                    }
                ]
            }
        ]
        
        tree = create_dependency_tree("root", "1.0.0", "python", deps)
        level3 = tree.find_node("level3")
        
        assert level3 is not None
        assert level3.depth == 3
    
    def test_duplicate_names_at_different_depths(self):
        """Test handling packages with same name at different depths."""
        deps = [
            {
                "name": "package",
                "version": "1.0.0",
                "children": [
                    {
                        "name": "other-package",
                        "version": "2.0.0",
                        "children": [
                            {"name": "package", "version": "3.0.0", "children": []}
                        ]
                    }
                ]
            }
        ]
        
        tree = create_dependency_tree("root", "1.0.0", "python", deps)
        
        # Should find both packages (one at depth 1, one at depth 2)
        all_nodes = tree.get_all_nodes()
        package_count = sum(1 for n in all_nodes if n.name == "package")
        assert package_count == 2


class TestGetAllVulnerabilities:
    """Test getting all vulnerabilities from a tree."""
    
    def test_accumulate_vulnerabilities(self):
        """Test vulnerabilities are accumulated from children."""
        root = DependencyNode("root", "1.0.0", "python")
        child = DependencyNode("child", "1.0.0", "python", parent=root, depth=1)
        child.advisory_ids = ["CVE-1", "CVE-2"]
        root.children.append(child)
        
        grandchild = DependencyNode("gc", "1.0.0", "python", parent=child, depth=2)
        grandchild.advisory_ids = ["CVE-3"]
        child.children.append(grandchild)
        
        all_vulns = root.get_all_vulnerabilities()
        assert len(all_vulns) == 3
        assert "CVE-1" in all_vulns
        assert "CVE-2" in all_vulns
        assert "CVE-3" in all_vulns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
