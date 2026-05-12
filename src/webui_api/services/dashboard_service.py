"""Dashboard service - provides system status, metrics, and security data."""
import os
import time
from typing import Optional
from config.settings import settings

class DashboardService:
    """Manages dashboard data and system metrics."""

    def __init__(self):
        self._start_time = time.time()
        self._metrics = {
            "total_requests": 0,
            "allowed_requests": 0,
            "blocked_requests": 0,
            "error_requests": 0,
        }

    def get_health(self) -> dict:
        """Get system health status."""
        return {
            "proxy_status": "online",
            "nexus_status": "configured" if settings.NEXUS_BASE_URL else "not_configured",
            "uptime_seconds": int(time.time() - self._start_time),
            "version": "1.0.0",
        }

    def get_metrics(self) -> dict:
        """Get request metrics."""
        return self._metrics

    def record_request(self, outcome: str):
        """Record a request outcome."""
        self._metrics["total_requests"] += 1
        if outcome in self._metrics:
            self._metrics[outcome] += 1

    def get_features(self) -> list:
        """Get security features list."""
        return [
            {"name": "PII Detection", "icon": "🛡️", "description": "Blocks personal information", "badge": "Active", "category": "input"},
            {"name": "Credential Detection", "icon": "🔐", "description": "Prevents API keys and secrets from leaving", "badge": "Active", "category": "input"},
            {"name": "Prompt Injection", "icon": "⚠️", "description": "Blocks prompt injection attempts", "badge": "Active", "category": "input"},
            {"name": "Smart Redaction", "icon": "✏️", "description": "Context-aware PII redaction", "badge": "Active", "category": "input"},
            {"name": "Nexus Validation", "icon": "📦", "description": "Verifies packages against Nexus repository", "badge": "Active", "category": "output"},
            {"name": "Vulnerability Scan", "icon": "🦠", "description": "OSV + NVD/CVE scanning", "badge": "Configurable", "category": "output"},
            {"name": "Version Validation", "icon": "🏷️", "description": "Semver matching against advisories", "badge": "Configurable", "category": "output"},
            {"name": "Dependency Tree", "icon": "🌳", "description": "Transitive dependency resolution", "badge": "Configurable", "category": "output"},
            {"name": "Sandbox Execution", "icon": "🐳", "description": "Docker isolation with detection rules", "badge": "Configurable", "category": "output"},
            {"name": "Risk Scoring", "icon": "📊", "description": "5-factor weighted risk assessment", "badge": "Configurable", "category": "output"},
            {"name": "Rate Limiting", "icon": "🚀", "description": "Token bucket rate limiting", "badge": "Active", "category": "resilience"},
            {"name": "Circuit Breaker", "icon": "🔄", "description": "3-failure threshold circuit breaker", "badge": "Active", "category": "resilience"},
        ]

    def get_pipeline(self) -> list:
        """Get the output security pipeline phases."""
        return [
            {"phase": 0, "name": "Nexus Validation", "description": "Verify package in approved repository", "status": "Active"},
            {"phase": 1, "name": "Vulnerability Scan", "description": "OSV + NVD/CVE scanning", "status": "Configurable"},
            {"phase": 2, "name": "Version Validation", "description": "Semver matching against SQLite", "status": "Configurable"},
            {"phase": 3, "name": "Dependency Tree", "description": "Transitive dependency resolution", "status": "Configurable"},
            {"phase": 4, "name": "Sandbox + Risk Score", "description": "Docker execution + risk assessment", "status": "Configurable"},
        ]

    def get_issues(self) -> dict:
        """Get known issues categorized by severity."""
        return {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
        }

    def get_codebase_stats(self) -> dict:
        """Get codebase statistics."""
        return {
            "source_loc": "~4,800",
            "test_loc": "~1,200",
            "test_files": 14,
            "security_phases": 5,
            "languages_supported": 7,
            "detection_rules": 18,
            "api_endpoints": 2,
        }

    def get_components(self) -> list:
        """Get component inventory."""
        return [
            {"layer": "Proxy", "module": "main.py", "lines": 598, "status": "Good"},
            {"layer": "Input", "module": "engine.py", "lines": 267, "status": "Good"},
            {"layer": "Output", "module": "engine.py (orchestrator)", "lines": 577, "status": "Good"},
            {"layer": "Output", "module": "code_parser.py", "lines": 172, "status": "Good"},
            {"layer": "Output", "module": "nexus.py", "lines": 155, "status": "Good"},
            {"layer": "Output", "module": "vulnerability_scanner.py", "lines": 390, "status": "Good"},
            {"layer": "Output", "module": "version_validator.py", "lines": 286, "status": "Good"},
            {"layer": "Output", "module": "version_parser.py", "lines": 320, "status": "Good"},
            {"layer": "Output", "module": "security_advisory.py", "lines": 335, "status": "Good"},
            {"layer": "Output", "module": "dependency_tree.py", "lines": 358, "status": "Good"},
            {"layer": "Output", "module": "dependency_resolver.py", "lines": 562, "status": "Good"},
            {"layer": "Output", "module": "sandbox.py", "lines": 431, "status": "Good"},
            {"layer": "Output", "module": "detection_rules.py", "lines": 459, "status": "Good"},
            {"layer": "Output", "module": "risk_scorer.py", "lines": 487, "status": "Good"},
        ]

    def get_roadmap(self) -> list:
        """Get improvement roadmap."""
        return [
            {
                "phase": "Phase 1: Critical Fixes",
                "severity": "critical",
                "effort": "1-2 days",
                "items": [
                    {"task": "Add Pydantic model for /v1/messages endpoint", "effort": "2h"},
                    {"task": "Complete requirements.txt with all dependencies", "effort": "30m"},
                ],
            },
            {
                "phase": "Phase 2: Hardening",
                "severity": "high",
                "effort": "3-5 days",
                "items": [
                    {"task": "Refactor main.py into route handlers + service layer", "effort": "2-3d"},
                    {"task": "Add streaming support with incremental output scanning", "effort": "2-3d"},
                    {"task": "Unify auth strategy between endpoints", "effort": "4h"},
                    {"task": "Add Redis-backed rate limiting", "effort": "1d"},
                    {"task": "Add request body size limits + CORS", "effort": "2h"},
                ],
            },
            {
                "phase": "Phase 3: Operational Excellence",
                "severity": "medium",
                "effort": "5-7 days",
                "items": [
                    {"task": "Make model mapping configurable (YAML)", "effort": "4h"},
                    {"task": "Add JS/TS/Ruby stdlib filtering", "effort": "2h"},
                    {"task": "Add shared cache for vulnerability scanning", "effort": "1d"},
                    {"task": "Convert sandbox subprocess to async", "effort": "4h"},
                    {"task": "Add OpenTelemetry tracing + graceful shutdown", "effort": "2-3d"},
                ],
            },
        ]

# Singleton instance
dashboard_service = DashboardService()