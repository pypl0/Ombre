"""
Ombre Response Object
=====================
The clean interface returned to every Ombre caller.
Contains the AI response plus all pipeline metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OmbreResponse:
    """
    The response object returned by every Ombre.run() call.

    Contains the AI response text plus full pipeline metrics —
    what was saved, what was caught, what was blocked.
    """

    # === Core Response ===
    text: str
    confidence: float = 1.0

    # === Financial Metrics ===
    cost_saved: float = 0.0

    # === Identity ===
    audit_id: str = ""
    request_id: str = ""

    # === Routing ===
    model: Optional[str] = None
    provider: Optional[str] = None

    # === Token Metrics ===
    tokens_used: int = 0
    tokens_saved: int = 0

    # === Performance ===
    latency_ms: float = 0.0

    # === Safety Metrics ===
    hallucinations_caught: int = 0
    threats_blocked: int = 0

    # === Pipeline State ===
    cache_hit: bool = False
    blocked: bool = False
    block_reason: Optional[str] = None
    error: Optional[str] = None
    agents_activated: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True if the response was successful (not blocked, not an error)."""
        return not self.blocked and self.error is None

    @property
    def cost_saved_formatted(self) -> str:
        """Return cost saved as a formatted dollar string."""
        return f"${self.cost_saved:.4f}"

    @property
    def confidence_pct(self) -> str:
        """Return confidence as a percentage string."""
        return f"{self.confidence * 100:.1f}%"

    @property
    def is_cached(self) -> bool:
        """True if this response was served from cache."""
        return self.cache_hit

    @property
    def summary(self) -> str:
        """One-line summary of pipeline execution."""
        parts = [
            f"model={self.model or 'unknown'}",
            f"confidence={self.confidence_pct}",
            f"latency={self.latency_ms:.0f}ms",
            f"saved={self.cost_saved_formatted}",
        ]
        if self.hallucinations_caught > 0:
            parts.append(f"hallucinations_caught={self.hallucinations_caught}")
        if self.threats_blocked > 0:
            parts.append(f"threats_blocked={self.threats_blocked}")
        if self.cache_hit:
            parts.append("cache=hit")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize response to dictionary."""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "cost_saved": self.cost_saved,
            "audit_id": self.audit_id,
            "request_id": self.request_id,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "tokens_saved": self.tokens_saved,
            "latency_ms": self.latency_ms,
            "hallucinations_caught": self.hallucinations_caught,
            "threats_blocked": self.threats_blocked,
            "cache_hit": self.cache_hit,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "error": self.error,
            "agents_activated": self.agents_activated,
            "ok": self.ok,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize response to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def raise_for_error(self) -> "OmbreResponse":
        """Raise an exception if the response has an error."""
        if self.error:
            raise OmbreError(self.error, request_id=self.request_id)
        if self.blocked:
            raise OmbreBlockedError(
                self.block_reason or "Request blocked by security agent",
                request_id=self.request_id,
            )
        return self

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return (
            f"OmbreResponse(ok={self.ok}, "
            f"confidence={self.confidence:.2f}, "
            f"model={self.model}, "
            f"latency={self.latency_ms:.0f}ms)"
        )

    def __bool__(self) -> bool:
        return self.ok and bool(self.text)


class OmbreError(Exception):
    """Base error for Ombre pipeline failures."""
    def __init__(self, message: str, request_id: Optional[str] = None):
        super().__init__(message)
        self.request_id = request_id


class OmbreBlockedError(OmbreError):
    """Raised when a request is blocked by the Security Agent."""
    pass


class OmbreTimeoutError(OmbreError):
    """Raised when a request exceeds the SLA latency threshold."""
    pass


class OmbreProviderError(OmbreError):
    """Raised when all configured AI providers fail."""
    pass
