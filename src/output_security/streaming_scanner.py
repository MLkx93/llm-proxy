"""
Streaming Code Block Scanner.

Stateful scanner that accumulates streaming text chunks and fires security
scans the moment each fenced code block (```...```) closes — before the
surrounding text continues to the client.

Reuses MaliciousCodeDetector (sync) and extract_code_blocks() from the
existing output security pipeline so streaming gets identical protection
to non-streaming responses.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .malicious_code_detector import MaliciousCodeDetector
from .code_parser import extract_code_blocks, Dependency
from src.proxy.logging import get_logger

logger = get_logger("streaming_scanner")

_FENCE_RE = re.compile(r'```', re.MULTILINE)


@dataclass
class ScanDecision:
    """Result of scanning a newly-closed code block."""
    safe: bool
    block_code: str = ""
    block_reason: str = ""
    packages: List[Dependency] = field(default_factory=list)


class StreamingCodeScanner:
    """
    Accumulates streaming text and scans code blocks as they complete.

    Usage:
        scanner = StreamingCodeScanner()
        for chunk in stream:
            decision = scanner.feed(chunk)
            if not decision.safe:
                # abort stream, send error to client
                break
            # safe — forward chunk to client
    """

    def __init__(self):
        self._buffer = ""
        # Position in buffer from which the next fence search should start.
        # Always advances forward — never goes backwards.
        self._search_from = 0
        self._open_fence_pos: Optional[int] = None  # abs pos of opening ```
        self._detector = MaliciousCodeDetector()

    def feed(self, chunk: str) -> ScanDecision:
        """
        Feed one text chunk (the text delta from an SSE event).
        Returns ScanDecision immediately — never blocks.
        """
        if not chunk:
            return ScanDecision(safe=True)

        self._buffer += chunk

        # Search only the newly-arrived portion (with a small 2-char overlap
        # to catch a ``` that was split: ".." + "`" + "``" across two chunks).
        search_start = max(0, self._search_from - 2)

        while True:
            idx = self._buffer.find("```", search_start)
            if idx == -1:
                break

            if self._open_fence_pos is None:
                # Opening fence found
                self._open_fence_pos = idx
                search_start = idx + 3
                self._search_from = idx + 3
            else:
                # Closing fence — only valid if it's AFTER the opening fence
                if idx <= self._open_fence_pos:
                    search_start = idx + 3
                    continue

                block_text = self._buffer[self._open_fence_pos: idx + 3]
                self._open_fence_pos = None
                self._search_from = idx + 3
                search_start = idx + 3

                decision = self._scan_block(block_text)
                if not decision.safe:
                    return decision

        return ScanDecision(safe=True)

    def _scan_block(self, block_text: str) -> ScanDecision:
        """Scan a single complete code block."""
        logger.info("scanning_code_block", extra={"length": len(block_text)})

        # 1. Malicious pattern detection (sync, always-on)
        blocks = extract_code_blocks(block_text)
        for block in blocks:
            mal = self._detector.scan(block.code)
            if not mal.allowed:
                logger.warning("streaming_block_malicious", extra={
                    "block_code": mal.block_code,
                    "risk_level": mal.risk_level,
                })
                return ScanDecision(
                    safe=False,
                    block_code=mal.block_code,
                    block_reason=mal.block_reason,
                )

            # 2. Collect packages for async vulnerability scan by caller
            if block.dependencies:
                return ScanDecision(
                    safe=True,
                    packages=list(block.dependencies),
                )

        return ScanDecision(safe=True)

    @property
    def full_text(self) -> str:
        """Full accumulated response text so far."""
        return self._buffer
