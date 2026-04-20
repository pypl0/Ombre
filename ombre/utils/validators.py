"""
Ombre Input Validators
======================
Input validation for prompts, configuration, and API keys.
"""

from __future__ import annotations

from typing import Any, Optional


def validate_prompt(prompt: str) -> None:
    """Validate a prompt before processing."""
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    if not isinstance(prompt, str):
        raise TypeError(f"Prompt must be a string, got {type(prompt)}")
    if len(prompt) > 1_000_000:
        raise ValueError("Prompt exceeds maximum length of 1,000,000 characters")


def validate_config(
    openai_key: Optional[str] = None,
    anthropic_key: Optional[str] = None,
    groq_key: Optional[str] = None,
    ombre_key: Optional[str] = None,
) -> None:
    """Validate configuration values."""
    has_provider = any([openai_key, anthropic_key, groq_key])
    if not has_provider:
        import os
        env_keys = [
            os.environ.get("OPENAI_API_KEY"),
            os.environ.get("ANTHROPIC_API_KEY"),
            os.environ.get("GROQ_API_KEY"),
        ]
        if not any(env_keys):
            import warnings
            warnings.warn(
                "No AI provider API keys configured. "
                "Provide at least one key: openai_key, anthropic_key, or groq_key. "
                "Or set environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY",
                UserWarning,
                stacklevel=3,
            )


def validate_temperature(temperature: float) -> None:
    """Validate temperature parameter."""
    if not isinstance(temperature, (int, float)):
        raise TypeError("Temperature must be a number")
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("Temperature must be between 0.0 and 2.0")


def validate_max_tokens(max_tokens: int) -> None:
    """Validate max_tokens parameter."""
    if not isinstance(max_tokens, int):
        raise TypeError("max_tokens must be an integer")
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")
    if max_tokens > 128_000:
        raise ValueError("max_tokens cannot exceed 128,000")


def sanitize_metadata(metadata: Any) -> dict:
    """Sanitize metadata dictionary."""
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        return {"value": str(metadata)}
    # Remove any None values and ensure all keys are strings
    return {str(k): v for k, v in metadata.items() if v is not None}
