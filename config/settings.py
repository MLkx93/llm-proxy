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

    # Logging
    AUDIT_LOG_PATH: str = _env("AUDIT_LOG_PATH", "logs/audit.jsonl")
    
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
