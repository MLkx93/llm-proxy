"""
Unit tests for the Output Security Engine.
Nexus HTTP calls are mocked — no network required.
"""
import pytest
from unittest.mock import AsyncMock, patch

from src.output_security.code_parser import extract_code_blocks, _extract_deps
from src.output_security.engine import check, extract_response_text
from src.output_security.nexus import ValidationResult, _CircuitBreaker, CircuitState


# ---------------------------------------------------------------------------
# Code parser — dependency extraction
# ---------------------------------------------------------------------------
class TestCodeParser:
    def test_no_code_block_returns_empty(self):
        blocks = extract_code_blocks("This is a plain text response with no code.")
        assert blocks == []

    def test_python_imports_extracted(self):
        text = "```python\nimport requests\nfrom flask import Flask\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        dep_names = [d.name for d in blocks[0].dependencies]
        assert "requests" in dep_names
        assert "flask" in dep_names

    def test_python_stdlib_filtered_out(self):
        text = "```python\nimport os\nimport sys\nimport requests\n```"
        blocks = extract_code_blocks(text)
        dep_names = [d.name for d in blocks[0].dependencies]
        assert "os" not in dep_names
        assert "sys" not in dep_names
        assert "requests" in dep_names

    def test_javascript_require_extracted(self):
        text = "```javascript\nconst axios = require('axios');\nconst _ = require('lodash');\n```"
        blocks = extract_code_blocks(text)
        dep_names = [d.name for d in blocks[0].dependencies]
        assert "axios" in dep_names
        assert "lodash" in dep_names

    def test_javascript_esm_import_extracted(self):
        text = "```javascript\nimport express from 'express';\n```"
        blocks = extract_code_blocks(text)
        dep_names = [d.name for d in blocks[0].dependencies]
        assert "express" in dep_names

    def test_relative_imports_excluded(self):
        # './utils' and '../lib' are local — should not be flagged
        deps = _extract_deps("javascript", "import foo from './utils';\nimport bar from '../lib';")
        assert deps == []

    def test_multiple_code_blocks(self):
        text = (
            "```python\nimport numpy\n```\n"
            "Some text.\n"
            "```javascript\nconst express = require('express');\n```"
        )
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2

    def test_code_block_no_language_tag(self):
        text = "```\nimport requests\n```"
        blocks = extract_code_blocks(text)
        # No language → no extractors → no deps, but block is still found
        assert len(blocks) == 1
        assert blocks[0].dependencies == []

    def test_pip_install_in_shell(self):
        text = "```shell\npip install requests\n```"
        blocks = extract_code_blocks(text)
        dep_names = [d.name for d in blocks[0].dependencies]
        assert "requests" in dep_names

    def test_extract_response_text(self):
        resp = {"choices": [{"message": {"content": "Hello!"}}]}
        assert extract_response_text(resp) == "Hello!"

    def test_extract_response_text_malformed(self):
        assert extract_response_text({}) == ""
        assert extract_response_text({"choices": []}) == ""


# ---------------------------------------------------------------------------
# Nexus circuit breaker
# ---------------------------------------------------------------------------
class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = _CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request()

    def test_opens_after_threshold(self):
        cb = _CircuitBreaker()
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.allow_request()

    def test_success_resets_failures(self):
        cb = _CircuitBreaker()
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failures == 0
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_recovery_timeout(self):
        import time
        cb = _CircuitBreaker()
        for _ in range(3):
            cb.record_failure()
        # Wind back the clock
        cb.opened_at = time.monotonic() - 31.0
        assert cb.allow_request()
        assert cb.state == CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# Output engine — end-to-end (Nexus mocked)
# ---------------------------------------------------------------------------
APPROVED = ValidationResult(approved=True)
BLOCKED_DEP = ValidationResult(approved=False, reason="Not in Nexus.", block_code="BLOCKED_UNVALIDATED_DEP")
NEXUS_DOWN = ValidationResult(approved=False, reason="Unreachable.", block_code="NEXUS_UNAVAILABLE")


class TestOutputEngine:
    @pytest.mark.asyncio
    async def test_no_code_allowed(self):
        result = await check("Here is your answer: 42. No code here.")
        assert result.allowed

    @pytest.mark.asyncio
    async def test_code_with_approved_dep_allowed(self):
        text = "```python\nimport requests\nprint('hi')\n```"
        with patch("src.output_security.engine.validate_package", new_callable=AsyncMock) as mock:
            mock.return_value = APPROVED
            result = await check(text)
        assert result.allowed
        mock.assert_called_once_with("requests", "python")

    @pytest.mark.asyncio
    async def test_code_with_unknown_dep_blocked(self):
        text = "```python\nimport evil_package\n```"
        with patch("src.output_security.engine.validate_package", new_callable=AsyncMock) as mock:
            mock.return_value = BLOCKED_DEP
            result = await check(text)
        assert not result.allowed
        assert result.block_code == "BLOCKED_UNVALIDATED_DEP"
        assert "evil_package" in result.blocked_packages

    @pytest.mark.asyncio
    async def test_nexus_down_blocked(self):
        text = "```python\nimport requests\n```"
        with patch("src.output_security.engine.validate_package", new_callable=AsyncMock) as mock:
            mock.return_value = NEXUS_DOWN
            result = await check(text)
        assert not result.allowed
        assert result.block_code == "NEXUS_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_code_without_deps_allowed(self):
        text = "```python\ndef add(a, b):\n    return a + b\n```"
        result = await check(text)
        assert result.allowed

    @pytest.mark.asyncio
    async def test_first_blocked_dep_stops_further_checks(self):
        text = "```python\nimport evil\nimport also_evil\n```"
        with patch("src.output_security.engine.validate_package", new_callable=AsyncMock) as mock:
            mock.return_value = BLOCKED_DEP
            result = await check(text)
        assert not result.allowed
        # Should stop after first failure
        mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_javascript_dep_validated(self):
        text = "```javascript\nconst express = require('express');\n```"
        with patch("src.output_security.engine.validate_package", new_callable=AsyncMock) as mock:
            mock.return_value = APPROVED
            result = await check(text)
        assert result.allowed
        mock.assert_called_once_with("express", "javascript")
