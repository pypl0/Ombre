"""
Ombre Pipeline Context
======================
The PipelineContext object travels through all eight agents,
accumulating state, metrics, and decisions at each stage.
This is the core data structure of the Ombre pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineContext:
    """
    Mutable context object that flows through the entire Ombre pipeline.

    Each agent reads from and writes to this object.
    Nothing in this object ever leaves the customer's infrastructure.
    """

    # === Core Request ===
    prompt: str
    config: Any  # OmbreConfig
    request_id: str = ""
    session_id: str = ""
    user_id: Optional[str] = None

    # === Request Options ===
    model: str = "auto"
    system: Optional[str] = None
    context: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    agents: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # === Security Agent State ===
    blocked: bool = False
    block_reason: Optional[str] = None
    threats_blocked: int = 0
    pii_redacted: bool = False
    redacted_fields: List[str] = field(default_factory=list)
    sanitized_prompt: Optional[str] = None
    injection_detected: bool = False

    # === Memory Agent State ===
    memory_loaded: bool = False
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    user_context: Dict[str, Any] = field(default_factory=dict)
    persistent_facts: List[str] = field(default_factory=list)

    # === Token Agent State ===
    cache_hit: bool = False
    cached_response: Optional[str] = None
    compressed: bool = False
    original_token_count: int = 0
    compressed_token_count: int = 0
    tokens_saved: int = 0
    estimated_tokens: int = 0
    cache_key: Optional[str] = None

    # === Compute Agent State ===
    selected_model: Optional[str] = None
    selected_provider: Optional[str] = None
    model_rationale: Optional[str] = None
    fallback_providers: List[str] = field(default_factory=list)
    routing_score: float = 0.0

    # === Truth Agent State ===
    ground_truth_loaded: bool = False
    verified_facts: List[Dict[str, Any]] = field(default_factory=list)
    fact_sources: List[str] = field(default_factory=list)
    truth_constraints: List[str] = field(default_factory=list)

    # === Inference State ===
    raw_response: Optional[str] = None
    response_text: Optional[str] = None
    inference_start: float = field(default_factory=time.time)
    inference_end: Optional[float] = None
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # === Latency Agent State ===
    latency_ok: bool = True
    latency_ms: float = 0.0
    sla_breach: bool = False
    rerouted: bool = False
    reroute_count: int = 0

    # === Reliability Agent State ===
    reliability_score: float = 1.0
    hallucinations_caught: int = 0
    hallucination_details: List[Dict[str, Any]] = field(default_factory=list)
    bias_detected: bool = False
    consistency_score: float = 1.0
    confidence_score: float = 1.0
    output_validated: bool = False

    # === Audit Agent State ===
    audit_id: Optional[str] = None
    audit_timestamp: Optional[float] = None
    audit_hash: Optional[str] = None
    compliance_flags: List[str] = field(default_factory=list)

    # === Feedback Agent State ===
    feedback_registered: bool = False
    outcome_logged: bool = False

    # === Cost Tracking ===
    estimated_cost_without_ombre: float = 0.0
    actual_cost: float = 0.0
    cost_saved: float = 0.0

    # === Pipeline Tracking ===
    agents_activated: List[str] = field(default_factory=list)
    pipeline_start: float = field(default_factory=time.time)
    errors: List[str] = field(default_factory=list)

    def activate_agent(self, agent_name: str) -> None:
        """Record that an agent was activated."""
        if agent_name not in self.agents_activated:
            self.agents_activated.append(agent_name)

    def add_error(self, error: str) -> None:
        """Record a non-fatal pipeline error."""
        self.errors.append(error)

    def should_run_agent(self, agent_name: str) -> bool:
        """Check if a specific agent should run for this request."""
        if self.agents is None:
            return True  # All agents active by default
        return agent_name in self.agents

    def get_effective_prompt(self) -> str:
        """Get the prompt to send to the model (sanitized if needed)."""
        return self.sanitized_prompt or self.prompt

    def get_full_context(self) -> str:
        """Build the complete context string for model inference."""
        parts = []
        if self.conversation_history:
            for msg in self.conversation_history[-10:]:  # Last 10 turns
                role = msg.get("role", "user").upper()
                content = msg.get("content", "")
                parts.append(f"{role}: {content}")
        if self.context:
            parts.append(f"CONTEXT:\n{self.context}")
        if self.persistent_facts:
            parts.append("KNOWN FACTS:\n" + "\n".join(self.persistent_facts))
        if self.verified_facts:
            fact_strs = [f.get("fact", "") for f in self.verified_facts]
            parts.append("VERIFIED GROUND TRUTH:\n" + "\n".join(fact_strs))
        return "\n\n".join(parts) if parts else ""

    def to_audit_record(self) -> Dict[str, Any]:
        """Serialize context to an audit record (strips sensitive data)."""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.audit_timestamp,
            "model": self.selected_model,
            "provider": self.selected_provider,
            "agents_activated": self.agents_activated,
            "tokens_used": self.tokens_used,
            "tokens_saved": self.tokens_saved,
            "cost_saved": self.cost_saved,
            "confidence_score": self.confidence_score,
            "hallucinations_caught": self.hallucinations_caught,
            "threats_blocked": self.threats_blocked,
            "cache_hit": self.cache_hit,
            "latency_ms": self.latency_ms,
            "sla_breach": self.sla_breach,
            "bias_detected": self.bias_detected,
            "pii_redacted": self.pii_redacted,
            "compliance_flags": self.compliance_flags,
            "audit_hash": self.audit_hash,
            # NOTE: prompt and response deliberately excluded from audit record
            # Customer data never leaves their infrastructure
        }
