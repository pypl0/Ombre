"""
Ombre Configuration
===================
Central configuration object. Holds all customer-provided API keys
and Ombre settings. Keys are stored in memory only — never written
to disk, never transmitted to Ombre servers.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


class OmbreConfig:
    """
    Configuration for the Ombre SDK.

    API keys are stored in this object only.
    They are never logged, transmitted, or written to disk by Ombre.
    """

    # Default model preferences per task type
    MODEL_ROUTING_TABLE = {
        "reasoning": ["claude-3-5-sonnet-20241022", "gpt-4o", "gpt-4-turbo"],
        "coding": ["claude-3-5-sonnet-20241022", "gpt-4o", "deepseek-coder"],
        "summarization": ["gpt-4o-mini", "claude-3-haiku-20240307", "mistral-small"],
        "chat": ["gpt-4o-mini", "claude-3-haiku-20240307", "llama-3.1-8b-instant"],
        "analysis": ["claude-3-5-sonnet-20241022", "gpt-4o", "gpt-4-turbo"],
        "embedding": ["text-embedding-3-small", "text-embedding-3-large"],
        "default": ["gpt-4o-mini", "claude-3-haiku-20240307"],
    }

    # Cost per 1k tokens by model (approximate, used for savings calculation)
    MODEL_COSTS = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
        "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        "mistral-small": {"input": 0.001, "output": 0.003},
        "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
        "default": {"input": 0.001, "output": 0.002},
    }

    def __init__(
        self,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        groq_key: Optional[str] = None,
        mistral_key: Optional[str] = None,
        cohere_key: Optional[str] = None,
        ombre_key: Optional[str] = None,
        memory_backend: str = "local",
        audit_backend: str = "local",
        extra: Optional[Dict[str, Any]] = None,
    ):
        # Provider keys — stored in memory only
        self._openai_key = openai_key or os.environ.get("OPENAI_API_KEY")
        self._anthropic_key = anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
        self._groq_key = groq_key or os.environ.get("GROQ_API_KEY")
        self._mistral_key = mistral_key or os.environ.get("MISTRAL_API_KEY")
        self._cohere_key = cohere_key or os.environ.get("COHERE_API_KEY")
        self._ombre_key = ombre_key or os.environ.get("OMBRE_API_KEY")

        # Backend configuration
        self.memory_backend = memory_backend
        self.audit_backend = audit_backend

        # Feature flags
        self.enable_telemetry = False  # Always off
        self.enable_caching = True
        self.enable_compression = True
        self.enable_security = True
        self.enable_hallucination_detection = True
        self.enable_audit = True
        self.enable_feedback = True

        # Performance settings
        self.cache_ttl_seconds = 3600
        self.max_cache_size_mb = 512
        self.default_temperature = 0.7
        self.default_max_tokens = 2048
        self.request_timeout_seconds = 60
        self.sla_latency_ms = 5000

        # Security settings
        self.pii_detection_enabled = True
        self.injection_detection_enabled = True
        self.content_filtering_enabled = True

        # Memory settings
        self.memory_max_history = 50
        self.memory_ttl_days = 30

        # Enterprise features (unlocked by ombre_key)
        self.enterprise_features = self._resolve_enterprise_features()

        # Extra configuration
        self.extra = extra or {}

        # Apply any extra config
        for key, value in self.extra.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @property
    def openai_key(self) -> Optional[str]:
        return self._openai_key

    @property
    def anthropic_key(self) -> Optional[str]:
        return self._anthropic_key

    @property
    def groq_key(self) -> Optional[str]:
        return self._groq_key

    @property
    def mistral_key(self) -> Optional[str]:
        return self._mistral_key

    @property
    def cohere_key(self) -> Optional[str]:
        return self._cohere_key

    @property
    def ombre_key(self) -> Optional[str]:
        return self._ombre_key

    @property
    def available_providers(self) -> List[str]:
        """Return list of providers with configured API keys."""
        providers = []
        if self._openai_key:
            providers.append("openai")
        if self._anthropic_key:
            providers.append("anthropic")
        if self._groq_key:
            providers.append("groq")
        if self._mistral_key:
            providers.append("mistral")
        if self._cohere_key:
            providers.append("cohere")
        return providers

    @property
    def has_any_provider(self) -> bool:
        """Check if at least one provider is configured."""
        return len(self.available_providers) > 0

    @property
    def default_embedding_model(self) -> str:
        """Get the default embedding model based on available providers."""
        if self._openai_key:
            return "text-embedding-3-small"
        if self._cohere_key:
            return "embed-english-v3.0"
        return "local"

    @property
    def is_enterprise(self) -> bool:
        """Check if enterprise features are unlocked."""
        return bool(self._ombre_key and self.enterprise_features.get("valid"))

    def get_provider_key(self, provider: str) -> Optional[str]:
        """Get API key for a specific provider."""
        key_map = {
            "openai": self._openai_key,
            "anthropic": self._anthropic_key,
            "groq": self._groq_key,
            "mistral": self._mistral_key,
            "cohere": self._cohere_key,
        }
        return key_map.get(provider)

    def get_model_cost(self, model: str) -> Dict[str, float]:
        """Get cost per 1k tokens for a model."""
        return self.MODEL_COSTS.get(model, self.MODEL_COSTS["default"])

    def get_preferred_models(self, task_type: str) -> List[str]:
        """Get ordered list of preferred models for a task type."""
        models = self.MODEL_ROUTING_TABLE.get(
            task_type,
            self.MODEL_ROUTING_TABLE["default"]
        )
        # Filter to only models from available providers
        available = []
        for model in models:
            provider = self._get_model_provider(model)
            if provider in self.available_providers:
                available.append(model)
        return available or models  # Fall back to all if none available

    def _get_model_provider(self, model: str) -> str:
        """Determine which provider a model belongs to."""
        if model.startswith("gpt") or model.startswith("text-embedding"):
            return "openai"
        if model.startswith("claude"):
            return "anthropic"
        if model.startswith("llama") or model.startswith("mixtral") or model.startswith("gemma"):
            return "groq"
        if model.startswith("mistral") or model.startswith("codestral"):
            return "mistral"
        if model.startswith("embed-"):
            return "cohere"
        return "unknown"

    def _resolve_enterprise_features(self) -> Dict[str, Any]:
        """
        Resolve enterprise feature entitlements from ombre_key.
        Only validates the key structure locally — no API call needed
        for basic validation. Full validation happens on first use.
        """
        if not self._ombre_key:
            return {"valid": False, "tier": "free", "features": []}

        # Basic key format validation
        if self._ombre_key.startswith("omb_ent_"):
            return {
                "valid": True,
                "tier": "enterprise",
                "features": [
                    "advanced_memory",
                    "compliance_exports",
                    "air_gap_mode",
                    "priority_support",
                    "custom_truth_networks",
                    "advanced_audit",
                    "streaming",
                    "dedicated_compute",
                ],
            }
        elif self._ombre_key.startswith("omb_growth_"):
            return {
                "valid": True,
                "tier": "growth",
                "features": [
                    "advanced_memory",
                    "compliance_exports",
                    "priority_support",
                ],
            }
        elif self._ombre_key.startswith("omb_gov_"):
            return {
                "valid": True,
                "tier": "government",
                "features": [
                    "advanced_memory",
                    "compliance_exports",
                    "air_gap_mode",
                    "priority_support",
                    "custom_truth_networks",
                    "advanced_audit",
                    "streaming",
                    "dedicated_compute",
                    "fisma_compliance",
                    "fedramp_ready",
                    "classified_deployment",
                ],
            }

        return {"valid": False, "tier": "free", "features": []}

    def has_feature(self, feature: str) -> bool:
        """Check if a specific enterprise feature is available."""
        return feature in self.enterprise_features.get("features", [])

    def __repr__(self) -> str:
        return (
            f"OmbreConfig(providers={self.available_providers}, "
            f"tier={self.enterprise_features.get('tier', 'free')})"
        )
