import os


class Settings:
    # LLM provider API keys — loaded from environment only, never hardcoded
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

    # LiteLLM proxy — if set, routes all LLM calls through this server
    LITELLM_API_BASE: str = os.environ.get("LITELLM_API_BASE", "")
    LITELLM_API_KEY: str = os.environ.get("LITELLM_API_KEY", "")

    # Nexus
    NEXUS_BASE_URL: str = os.environ.get("NEXUS_BASE_URL", "")
    NEXUS_API_KEY: str = os.environ.get("NEXUS_API_KEY", "")

    # Logging
    AUDIT_LOG_PATH: str = os.environ.get("AUDIT_LOG_PATH", "logs/audit.jsonl")


settings = Settings()
