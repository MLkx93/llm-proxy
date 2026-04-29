"""Provider management service - handles provider configuration and model listing."""

import os
import yaml
from typing import Optional


# ── Provider Configuration ──────────────────────────────────────────────────

PROVIDERS = {
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "icon": "🌐",
        "description": "Multi-provider gateway with free and paid models",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "models": {
            "free": [
                {"id": "google/gemini-flash-thinking-1.0", "name": "Gemini Flash Thinking", "provider": "Google", "cost": "Free"},
                {"id": "deepseek/deepseek-chat-v3-0324", "name": "DeepSeek Chat V3", "provider": "DeepSeek", "cost": "Free"},
            ],
            "paid": [
                {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B", "provider": "Alibaba", "cost": "$0.40/M tokens"},
                {"id": "microsoft/phi-4", "name": "Phi-4", "provider": "Microsoft", "cost": "$0.30/M tokens"},
                {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "provider": "Meta", "cost": "$0.39/M tokens"},
                {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic", "cost": "$15/M tokens"},
                {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "provider": "Anthropic", "cost": "$4/M tokens"},
                {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic", "cost": "$30/M tokens"},
                {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI", "cost": "$5/M tokens"},
                {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI", "cost": "$0.60/M tokens"},
                {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash", "provider": "Google", "cost": "$0.10/M tokens"},
            ],
        },
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI Direct",
        "icon": "🟢",
        "description": "Direct OpenAI API access",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "models": {
            "free": [],
            "paid": [
                {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI", "cost": "$5/M tokens"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI", "cost": "$0.60/M tokens"},
                {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI", "cost": "$10/M tokens"},
            ],
        },
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Direct",
        "icon": "🟣",
        "description": "Direct Anthropic API access",
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "models": {
            "free": [],
            "paid": [
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "Anthropic", "cost": "$15/M tokens"},
                {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "Anthropic", "cost": "$4/M tokens"},
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "provider": "Anthropic", "cost": "$30/M tokens"},
            ],
        },
    },
    "litellm": {
        "id": "litellm",
        "name": "LiteLLM Proxy",
        "icon": "🔀",
        "description": "Self-hosted multi-provider proxy",
        "base_url": "http://localhost:4000/v1",
        "env_key": "LITELLM_API_KEY",
        "models": {
            "free": [],
            "paid": [
                {"id": "gpt-4o", "name": "GPT-4o (via LiteLLM)", "provider": "OpenAI", "cost": "Varies"},
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet (via LiteLLM)", "provider": "Anthropic", "cost": "Varies"},
            ],
        },
    },
}


class ProviderService:
    """Manages LLM provider configuration and state."""

    def __init__(self):
        self._active_provider: str = "openrouter"
        self._api_keys: dict = {}
        self._load_api_keys()

    def _load_api_keys(self):
        """Load API keys from environment and config file."""
        # Load from environment
        for pid, provider in PROVIDERS.items():
            key = os.environ.get(provider["env_key"])
            if key:
                self._api_keys[pid] = key

        # Load from config file
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "api_keys.yaml")
            if os.path.exists(config_path):
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                if config:
                    for pid in PROVIDERS:
                        if pid in config and config[pid].get("api_key"):
                            self._api_keys[pid] = config[pid]["api_key"]
        except Exception:
            pass

    def get_providers(self) -> dict:
        """Get all providers with their status."""
        providers_list = []
        for pid, provider in PROVIDERS.items():
            providers_list.append({
                "id": pid,
                "name": provider["name"],
                "icon": provider["icon"],
                "description": provider["description"],
                "active": pid == self._active_provider,
                "configured": pid in self._api_keys,
                "model_count": len(provider["models"]["free"]) + len(provider["models"]["paid"]),
            })
        return {
            "active_provider": self._active_provider,
            "providers": providers_list,
        }

    def get_models(self, provider_id: str) -> Optional[dict]:
        """Get models for a specific provider."""
        if provider_id not in PROVIDERS:
            return None
        provider = PROVIDERS[provider_id]
        return {
            "provider_id": provider_id,
            "provider_name": provider["name"],
            "free_models": provider["models"]["free"],
            "paid_models": provider["models"]["paid"],
        }

    def switch_provider(self, provider_id: str) -> Optional[dict]:
        """Switch the active provider."""
        if provider_id not in PROVIDERS:
            return None
        self._active_provider = provider_id
        provider = PROVIDERS[provider_id]
        return {
            "success": True,
            "active_provider": provider_id,
            "provider_name": provider["name"],
            "message": f"Switched to {provider['name']}",
        }

    def set_api_key(self, provider_id: str, api_key: str) -> Optional[dict]:
        """Set API key for a provider."""
        if provider_id not in PROVIDERS:
            return None
        self._api_keys[provider_id] = api_key
        provider = PROVIDERS[provider_id]
        return {
            "success": True,
            "provider_id": provider_id,
            "provider_name": provider["name"],
            "message": f"API key set for {provider['name']}",
        }

    def get_active_provider_config(self) -> dict:
        """Get the full configuration for the active provider."""
        provider = PROVIDERS[self._active_provider]
        return {
            "id": self._active_provider,
            "name": provider["name"],
            "icon": provider["icon"],
            "base_url": provider["base_url"],
            "api_key": self._api_keys.get(self._active_provider, ""),
            "has_key": self._active_provider in self._api_keys,
        }

    def get_proxy_base_url(self) -> str:
        """Get the proxy base URL for routing requests."""
        return os.environ.get("PROXY_BASE_URL", "http://localhost:8080")


# Singleton instance
provider_service = ProviderService()