import os


def _env(key: str, default: str = "") -> str:
    """Read an env var and strip whitespace (trailing spaces in .env are a common pitfall)."""
    return os.environ.get(key, default).strip()


class Settings:
    # LLM provider API keys — loaded from environment only, never hardcoded
    OPENAI_API_KEY: str = _env("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: str = _env("ANTHROPIC_API_KEY")

    # LiteLLM proxy — if set, routes all LLM calls through this server
    LITELLM_API_BASE: str = _env("LITELLM_API_BASE")
    LITELLM_API_KEY: str = _env("LITELLM_API_KEY")

    # Nexus
    NEXUS_BASE_URL: str = _env("NEXUS_BASE_URL")
    NEXUS_API_KEY: str = _env("NEXUS_API_KEY")

    # Logging
    AUDIT_LOG_PATH: str = _env("AUDIT_LOG_PATH", "logs/audit.jsonl")


settings = Settings()
