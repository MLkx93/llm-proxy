import os


def _env(key: str, default: str = "") -> str:
    """Read an env var and strip whitespace (trailing spaces in .env are a common pitfall)."""
    return os.environ.get(key, default).strip()


class Settings:
    # OpenRouter configuration — primary LLM provider
    OPENROUTER_API_KEY: str = _env("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = _env("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
    
    # Direct provider API keys (optional - bypass OpenRouter)
    OPENAI_API_KEY: str = _env("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: str = _env("ANTHROPIC_API_KEY")
    
    # LiteLLM proxy (legacy - ignored when OPENROUTER_API_KEY is set)
    LITELLM_API_BASE: str = _env("LITELLM_API_BASE")
    LITELLM_API_KEY: str = _env("LITELLM_API_KEY")
    
    # Nexus
    NEXUS_BASE_URL: str = _env("NEXUS_BASE_URL")
    NEXUS_API_KEY: str = _env("NEXUS_API_KEY")
    NEXUS_FAIL_OPEN: bool = _env("NEXUS_FAIL_OPEN", "false").lower() == "true"

    # Logging
    AUDIT_LOG_PATH: str = _env("AUDIT_LOG_PATH", "logs/audit.jsonl")

    # Malicious Code Detection (Phase 0.5 - always-on pattern detection)
    MALICIOUS_CODE_ENABLED: bool = _env("MALICIOUS_CODE_ENABLED", "true").lower() == "true"
    MALICIOUS_CODE_BLOCK_LEVEL: str = _env("MALICIOUS_CODE_BLOCK_LEVEL", "HIGH")  # HIGH or CRITICAL

    # Timeouts
    LLM_TIMEOUT_S: float = float(_env("LLM_TIMEOUT_S", "120"))

    # Streaming (opt-in — requires STREAMING_ENABLED=true to activate)
    STREAMING_ENABLED: bool = _env("STREAMING_ENABLED", "false").lower() == "true"

    # Database (demo deliverable — admin panel persistence + chat history)
    DATABASE_URL: str = _env("DATABASE_URL", "postgresql+asyncpg://shield:shield@localhost:5433/shield")

    # Demo auth gate (NOT production — simple login for the thesis defence)
    JWT_SECRET: str = _env("JWT_SECRET", "shield-demo-secret-change-me")
    JWT_EXPIRY_HOURS: int = int(_env("JWT_EXPIRY_HOURS", "12"))
    # Hardcoded demo accounts: "username:password:role" entries, comma-separated.
    DEMO_ACCOUNTS: str = _env("DEMO_ACCOUNTS", "admin:admin:admin,user:user:user")

    # Keycloak / OIDC (production admin-panel auth for the security team).
    # OIDC_ENABLED=false → the proxy degrades to API-key auth for /v1/audit/* so it
    # runs without Keycloak. Flip to true and fill the realm details to require SSO.
    OIDC_ENABLED: bool = _env("OIDC_ENABLED", "false").lower() == "true"
    KEYCLOAK_SERVER_URL: str = _env("KEYCLOAK_SERVER_URL", "")   # e.g. https://sso.company.com
    KEYCLOAK_REALM: str = _env("KEYCLOAK_REALM", "")            # e.g. security
    KEYCLOAK_CLIENT_ID: str = _env("KEYCLOAK_CLIENT_ID", "")    # public SPA client id
    KEYCLOAK_AUDIENCE: str = _env("KEYCLOAK_AUDIENCE", "")      # expected token aud (often the client id or "account")
    KEYCLOAK_ADMIN_ROLE: str = _env("KEYCLOAK_ADMIN_ROLE", "security-admin")

    # Vulnerability Scanning
    VULN_SCAN_ENABLED: bool = _env("VULN_SCAN_ENABLED", "false").lower() == "true"
    VULN_MIN_SEVERITY: str = _env("VULN_MIN_SEVERITY", "HIGH")  # For scanning/loading
    VULN_BLOCK_MIN_SEVERITY: str = _env("VULN_BLOCK_MIN_SEVERITY", "CRITICAL")  # For blocking decisions
    VULN_CACHE_TTL: int = int(_env("VULN_CACHE_TTL", "3600"))
    VULN_OSV_ENABLED: bool = _env("VULN_OSV_ENABLED", "true").lower() == "true"
    VULN_CVE_ENABLED: bool = _env("VULN_CVE_ENABLED", "true").lower() == "true"
    VULN_SNYK_API_KEY: str = _env("VULN_SNYK_API_KEY", "")
    
    # Version Validation (Phase 2)
    VERSION_VALIDATION_ENABLED: bool = _env("VERSION_VALIDATION_ENABLED", "false").lower() == "true"
    VERSION_ADVISORY_DB_PATH: str = _env("VERSION_ADVISORY_DB_PATH", "security_advisories.db")
    VERSION_AUTO_UPDATE_DB: bool = _env("VERSION_AUTO_UPDATE_DB", "true").lower() == "true"
    VERSION_UPDATE_INTERVAL_HOURS: int = int(_env("VERSION_UPDATE_INTERVAL_HOURS", "24"))
    VERSION_BLOCK_MIN_SEVERITY: str = _env("VERSION_BLOCK_MIN_SEVERITY", "HIGH")  # For blocking decisions
    
    # Dependency Tree Analysis (Phase 3)
    DEPENDENCY_SCAN_ENABLED: bool = _env("DEPENDENCY_SCAN_ENABLED", "false").lower() == "true"
    DEPENDENCY_MAX_DEPTH: int = int(_env("DEPENDENCY_MAX_DEPTH", "3"))
    DEPENDENCY_RISK_THRESHOLD: float = float(_env("DEPENDENCY_RISK_THRESHOLD", "10.0"))
    DEPENDENCY_BLOCK_ON_CRITICAL: bool = _env("DEPENDENCY_BLOCK_ON_CRITICAL", "true").lower() == "true"
    DEPENDENCY_BLOCK_MIN_GRADE: str = _env("DEPENDENCY_BLOCK_MIN_GRADE", "F")  # For blocking decisions
    
    # Code Sandbox Validation (Phase 4)
    SANDBOX_ENABLED: bool = _env("SANDBOX_ENABLED", "false").lower() == "true"
    SANDBOX_IMAGE: str = _env("SANDBOX_IMAGE", "python:3.11-slim")
    SANDBOX_TIMEOUT_SECONDS: int = int(_env("SANDBOX_TIMEOUT_SECONDS", "30"))
    SANDBOX_MEMORY_LIMIT: str = _env("SANDBOX_MEMORY_LIMIT", "512m")
    SANDBOX_CPU_LIMIT: float = float(_env("SANDBOX_CPU_LIMIT", "1.0"))
    SANDBOX_NETWORK_ENABLED: bool = _env("SANDBOX_NETWORK_ENABLED", "false").lower() == "true"
    SANDBOX_RISK_THRESHOLD: float = float(_env("SANDBOX_RISK_THRESHOLD", "6.0"))  # For scanning/loading
    SANDBOX_BLOCK_RISK_THRESHOLD: float = float(_env("SANDBOX_BLOCK_RISK_THRESHOLD", "8.0"))  # For blocking decisions
    
    # PII Handling
    PII_ACTION: str = _env("PII_ACTION", "redact")  # Options: "block", "redact"
    
    # Credential Handling
    CREDENTIAL_ACTION: str = _env("CREDENTIAL_ACTION", "block")  # Options: "block", "redact"
    
    # Guardrails (Phase 5)
    GUARDRAILS_ENABLED: bool = _env("GUARDRAILS_ENABLED", "false").lower() == "true"
    GUARDRAILS_TOXICITY_THRESHOLD: float = float(_env("GUARDRAILS_TOXICITY_THRESHOLD", "5.0"))
    GUARDRAILS_HALLUCINATION_THRESHOLD: float = float(_env("GUARDRAILS_HALLUCINATION_THRESHOLD", "3.0"))
    GUARDRAILS_PROMPT_LEAKAGE_THRESHOLD: float = float(_env("GUARDRAILS_PROMPT_LEAKAGE_THRESHOLD", "4.0"))
    GUARDRAILS_CONTENT_SAFETY_THRESHOLD: float = float(_env("GUARDRAILS_CONTENT_SAFETY_THRESHOLD", "4.0"))
    GUARDRAILS_BLOCK_ON_CRITICAL: bool = _env("GUARDRAILS_BLOCK_ON_CRITICAL", "true").lower() == "true"
    GUARDRAILS_EARLY_TERMINATION: bool = _env("GUARDRAILS_EARLY_TERMINATION", "true").lower() == "true"
    
    @property
    def use_openrouter(self) -> bool:
        """Check if OpenRouter is configured and should be used."""
        return bool(self.OPENROUTER_API_KEY)
    
    @property
    def use_litellm(self) -> bool:
        """Check if LiteLLM should be used (when OpenRouter is not configured)."""
        return not self.use_openrouter and bool(self.LITELLM_API_BASE)
    
    def transform_model_name(self, model: str) -> str:
        """
        Transform Claude Code model names to OpenRouter model names.
        
        Claude Code uses names like:
        - claude-sonnet-4.6
        - claude-haiku-4.5
        - claude-opus-4.6
        
        OpenRouter uses names like:
        - anthropic/claude-3-sonnet
        - anthropic/claude-3-haiku
        - anthropic/claude-3-opus
        """
        # Model name mapping from Claude Code to OpenRouter
        model_mapping = {
            # Sonnet models
            "claude-sonnet-4.6": "anthropic/claude-3-sonnet",
            "claude-sonnet-4-6": "anthropic/claude-3-sonnet",
            "sonnet-4-6": "anthropic/claude-3-sonnet",
            "claude-3.5-sonnet": "anthropic/claude-3-5-sonnet",
            "claude-3.5-sonnet-20241022": "anthropic/claude-3-5-sonnet",
            
            # Haiku models
            "claude-haiku-4.5": "anthropic/claude-3-haiku",
            "claude-haiku-4-5": "anthropic/claude-3-haiku",
            "claude-haiku-4-5-20251001": "anthropic/claude-3-haiku",
            "haiku-4-5": "anthropic/claude-3-haiku",
            "claude-3-haiku": "anthropic/claude-3-haiku",
            
            # Opus models
            "claude-opus-4.6": "anthropic/claude-3-opus",
            "claude-opus-4-6": "anthropic/claude-3-opus",
            "claude-opus-4-6-20251101": "anthropic/claude-3-opus",
            "opus-4-6": "anthropic/claude-3-opus",
            "claude-3-opus": "anthropic/claude-3-opus",
            "gpt-4o": "openai/gpt-4o",
            "gpt-4-turbo": "openai/gpt-4-turbo",
            "gpt-3.5-turbo": "openai/gpt-3.5-turbo",
            
            # Google models
            "gemini-pro": "google/gemini-pro",
            "gemini-flash": "google/gemini-flash",
            "gemma-4-26b-a4b-it": "google/gemma-4-26b-a4b-it",         
            
            # Meta models
            "llama-3-8b": "meta-llama/llama-3-8b-instruct",
            "llama-3-70b": "meta-llama/llama-3-70b-instruct",
        }
        
        
        # Check if model is already in OpenRouter format
        if model.startswith("anthropic/") or model.startswith("openai/") or model.startswith("meta-llama/"):
            return model
        
        # Look up in mapping
        transformed = model_mapping.get(model)
        if transformed:
            return transformed
        
        # If not found in mapping, return as-is (might work if it's already OpenRouter format)
        return model


settings = Settings()