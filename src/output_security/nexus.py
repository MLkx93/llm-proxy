""" Nexus Firewall validation client.

Checks whether a package is approved in the enterprise Nexus repository.
Implements a simple circuit breaker: after FAILURE_THRESHOLD consecutive
failures, the circuit opens and all requests are fail-closed (blocked)
until RECOVERY_TIMEOUT seconds have elapsed.

Fail-closed policy (per Phase 0 decision):
- Nexus unreachable → block the response, return NEXUS_UNAVAILABLE
- Package not found → block the response, return BLOCKED_UNVALIDATED_DEP
- Package found and clean → allow
"""
import time
import httpx
from enum import Enum
from dataclasses import dataclass, field

from config.settings import settings
from src.proxy.logging import get_logger

logger = get_logger("nexus")

# Circuit breaker thresholds
FAILURE_THRESHOLD = 3  # consecutive failures before opening circuit
RECOVERY_TIMEOUT = 30.0  # seconds before attempting recovery
REQUEST_TIMEOUT = 5.0  # seconds per Nexus HTTP call

class CircuitState(Enum):
    CLOSED = "closed"  # normal operation
    OPEN = "open"  # failing — all requests rejected immediately
    HALF_OPEN = "half_open"  # one probe allowed to test recovery

@dataclass
class _CircuitBreaker:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    opened_at: float = 0.0

    def record_success(self) -> None:
        self.failures = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= FAILURE_THRESHOLD:
            self.state = CircuitState.OPEN
            self.opened_at = time.monotonic()
            logger.warning("circuit_opened", extra={"failures": self.failures})

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.opened_at >= RECOVERY_TIMEOUT:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_half_open")
                return True
            return False
        # HALF_OPEN: allow the probe
        return True

_circuit = _CircuitBreaker()

@dataclass(frozen=True)
class ValidationResult:
    approved: bool
    reason: str = ""  # human-readable
    block_code: str = ""  # machine-readable error code

def _nexus_url(package: str, language: str) -> str:
    """Build the Nexus REST API search URL for a given package."""
    # Nexus Repository Manager 3 search API
    # https://help.sonatype.com/en/search-api.html
    repo_map = {
        "python": "pypi-proxy",
        "javascript": "npm-proxy",
        "typescript": "npm-proxy",
        "java": "maven-central-proxy",
        "ruby": "rubygems-proxy",
        "go": "go-proxy",
    }
    repo = repo_map.get(language, "default")
    base = settings.NEXUS_BASE_URL.rstrip("/")
    return f"{base}/service/rest/v1/search?repository={repo}&name={package}"

async def validate_package(package: str, language: str) -> ValidationResult:
    """ Check a single package against Nexus Firewall.
    Returns ValidationResult(approved=True) if safe, or a blocking result.
    """
    if not settings.NEXUS_BASE_URL:
        # Nexus not configured — fail-closed
        logger.error("nexus_not_configured")
        return ValidationResult(
            approved=False,
            reason="Nexus is not configured. Cannot validate dependencies.",
            block_code="NEXUS_UNAVAILABLE",
        )

    if not _circuit.allow_request():
        logger.warning("circuit_open_blocked", extra={"package": package})
        return ValidationResult(
            approved=False,
            reason="Dependency validation service is temporarily unavailable.",
            block_code="NEXUS_UNAVAILABLE",
        )

    url = _nexus_url(package, language)
    headers = {}
    if settings.NEXUS_API_KEY:
        headers["Authorization"] = f"Bearer {settings.NEXUS_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    _circuit.record_success()  # Nexus responded — it's up
                    logger.warning("package_not_in_nexus", extra={"package": package, "language": language})
                    return ValidationResult(
                        approved=False,
                        reason=f"Package '{package}' was not found in the approved Nexus repository.",
                        block_code="BLOCKED_UNVALIDATED_DEP",
                    )
                _circuit.record_success()
                logger.info("package_approved", extra={"package": package, "language": language})
                return ValidationResult(approved=True)

            # Non-200 from Nexus — treat as unavailable
            _circuit.record_failure()
            logger.error("nexus_bad_status", extra={"status": resp.status_code, "package": package})
            return ValidationResult(
                approved=False,
                reason="Dependency validation service returned an unexpected response.",
                block_code="NEXUS_UNAVAILABLE",
            )
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
        _circuit.record_failure()
        logger.error("nexus_unreachable", extra={"error": str(exc), "package": package})
        return ValidationResult(
            approved=False,
            reason="Dependency validation service is unreachable.",
            block_code="NEXUS_UNAVAILABLE",
        )