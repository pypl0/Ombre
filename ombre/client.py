"""
Ombre Core Client
=================
The primary interface for interacting with the Ombre AI infrastructure layer.
All data stays within the customer's own environment. Ombre never sees
customer prompts, responses, or API keys.

Usage:
    from ombre import Ombre

    ai = Ombre(
        openai_key="sk-...",
        anthropic_key="sk-ant-...",
        ombre_key="omb_ent_..."  # optional, unlocks enterprise features
    )

    response = ai.run("Your prompt here")
    print(response.text)
    print(response.confidence)
    print(response.cost_saved)
    print(response.audit_id)
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Any, Dict, List, Optional, Union

from .config import OmbreConfig
from .response import OmbreResponse
from .agents.security import SecurityAgent
from .agents.memory import MemoryAgent
from .agents.token import TokenAgent
from .agents.compute import ComputeAgent
from .agents.truth import TruthAgent
from .agents.latency import LatencyAgent
from .agents.reliability import ReliabilityAgent
from .agents.audit import AuditAgent
from .agents.feedback import FeedbackAgent
from .utils.logger import get_logger
from .utils.validators import validate_prompt, validate_config
from .utils.crypto import generate_request_id

logger = get_logger(__name__)


class Ombre:
    """
    Ombre — The infrastructure layer that makes AI trustworthy.

    Runs entirely within the customer's own environment.
    No data ever leaves the customer's infrastructure.
    Customers bring their own API keys.

    Architecture:
        Request → Security → Memory → Token → Compute → Truth
               → Model → Latency → Reliability → Audit → Response
               → Feedback (async, closes the loop)
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        groq_key: Optional[str] = None,
        mistral_key: Optional[str] = None,
        cohere_key: Optional[str] = None,
        ombre_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        log_level: str = "INFO",
        memory_backend: str = "local",
        audit_backend: str = "local",
        enable_telemetry: bool = False,  # Always False — Ombre never phones home
    ):
        """
        Initialize Ombre with customer-provided API keys.

        Args:
            openai_key: OpenAI API key (customer's own key)
            anthropic_key: Anthropic API key (customer's own key)
            groq_key: Groq API key (customer's own key)
            mistral_key: Mistral API key (customer's own key)
            cohere_key: Cohere API key (customer's own key)
            ombre_key: Ombre enterprise license key (optional)
            config: Additional configuration dictionary
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            memory_backend: Where to store memory ('local', 'redis', 'postgres')
            audit_backend: Where to store audit logs ('local', 'postgres', 's3')
            enable_telemetry: ALWAYS False. Ombre never transmits customer data.
        """
        self.session_id = str(uuid.uuid4())
        self._start_time = time.time()

        # Validate inputs before storing anything
        validate_config(
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            groq_key=groq_key,
            ombre_key=ombre_key,
        )

        # Build internal config — keys never leave this object
        self.config = OmbreConfig(
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            groq_key=groq_key,
            mistral_key=mistral_key,
            cohere_key=cohere_key,
            ombre_key=ombre_key,
            memory_backend=memory_backend,
            audit_backend=audit_backend,
            extra=config or {},
        )

        # Telemetry is hardcoded off — we don't want your data
        self.config.enable_telemetry = False

        # Set up logging
        logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))

        # Initialize all eight agents
        self._init_agents()

        logger.info(
            f"Ombre v{self.VERSION} initialized | session={self.session_id} | "
            f"providers={self.config.available_providers}"
        )

    def _init_agents(self) -> None:
        """Initialize all eight Ombre agents in order."""
        self.security = SecurityAgent(self.config)
        self.memory = MemoryAgent(self.config)
        self.token = TokenAgent(self.config)
        self.compute = ComputeAgent(self.config)
        self.truth = TruthAgent(self.config)
        self.latency = LatencyAgent(self.config)
        self.reliability = ReliabilityAgent(self.config)
        self.audit = AuditAgent(self.config)
        self.feedback = FeedbackAgent(self.config)
        logger.debug("All 8 Ombre agents initialized")

    def run(
        self,
        prompt: str,
        context: Optional[str] = None,
        system: Optional[str] = None,
        model: str = "auto",
        agents: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> OmbreResponse:
        """
        Run a prompt through the full Ombre pipeline.

        The request flows through all active agents before reaching
        the AI model, and all agents validate the response before
        it reaches the caller.

        Args:
            prompt: The user's prompt or question
            context: Additional context to include (documents, data, etc.)
            system: System prompt override
            model: Model to use ('auto' lets Compute Agent decide)
            agents: List of agents to activate (None = all agents)
            session_id: Session identifier for memory continuity
            user_id: User identifier for personalized memory
            metadata: Additional metadata to attach to this request
            stream: Whether to stream the response (enterprise feature)
            temperature: Model temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response

        Returns:
            OmbreResponse object with text, confidence, audit_id, and metrics
        """
        request_id = generate_request_id()
        pipeline_start = time.time()

        logger.info(f"Pipeline start | request={request_id}")

        try:
            # Build the pipeline context object
            ctx = self._build_context(
                prompt=prompt,
                context=context,
                system=system,
                model=model,
                agents=agents,
                session_id=session_id or self.session_id,
                user_id=user_id,
                metadata=metadata or {},
                temperature=temperature,
                max_tokens=max_tokens,
                request_id=request_id,
            )

            # === STEP 1: SECURITY AGENT ===
            # Block injection, redact PII, verify authorization
            ctx = self.security.process(ctx)
            if ctx.blocked:
                return self._build_blocked_response(ctx, request_id)

            # === STEP 2: MEMORY AGENT ===
            # Load persistent context and conversation history
            ctx = self.memory.process(ctx)

            # === STEP 3: TOKEN AGENT ===
            # Check cache, compress context, optimize token usage
            ctx = self.token.process(ctx)
            if ctx.cache_hit:
                logger.info(f"Cache hit | request={request_id}")
                return self._build_cached_response(ctx, request_id, pipeline_start)

            # === STEP 4: COMPUTE AGENT ===
            # Route to optimal model and provider
            ctx = self.compute.process(ctx)

            # === STEP 5: TRUTH AGENT ===
            # Pre-load verified facts, set hallucination guardrails
            ctx = self.truth.process(ctx)
< truncated lines 228-402 >
                    session_id=session_id or self.session_id,
                ): i
                for i, p in enumerate(prompts)
            }
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = self._build_error_response(str(e), generate_request_id())

        return results

    def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """
        Start a self-hosted REST API server on the customer's own infrastructure.
        All data stays within the customer's environment.

        Args:
            host: Host to bind to (default: all interfaces)
            port: Port to listen on (default: 8080)
        """
        try:
            from .server import OmbreServer
            server = OmbreServer(self)
            logger.info(f"Starting Ombre server on {host}:{port}")
            logger.info("All data processed locally — nothing leaves your infrastructure")
            server.run(host=host, port=port)
        except ImportError:
            raise ImportError(
                "Server dependencies not installed. "
                "Run: pip install 'ombre[server]'"
            )

    def stats(self) -> Dict[str, Any]:
        """
        Return runtime statistics for this Ombre instance.
        No external calls — all data is local.
        """
        uptime = round(time.time() - self._start_time, 2)
        return {
            "version": self.VERSION,
            "session_id": self.session_id,
            "uptime_seconds": uptime,
            "providers": self.config.available_providers,
            "agents": {
                "security": self.security.stats(),
                "memory": self.memory.stats(),
                "token": self.token.stats(),
                "compute": self.compute.stats(),
                "truth": self.truth.stats(),
                "latency": self.latency.stats(),
                "reliability": self.reliability.stats(),
                "audit": self.audit.stats(),
                "feedback": self.feedback.stats(),
            },
        }

    def reset_memory(self, session_id: Optional[str] = None) -> None:
        """Clear memory for a specific session or current session."""
        target = session_id or self.session_id
        self.memory.clear(target)
        logger.info(f"Memory cleared | session={target}")

    def export_audit(
        self,
        output_path: str,
        format: str = "json",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> str:
        """
        Export audit logs to a file. Stays on customer's infrastructure.

        Args:
            output_path: Where to write the audit export
            format: Export format ('json', 'csv', 'jsonl')
            start_time: Unix timestamp for start of range
            end_time: Unix timestamp for end of range

        Returns:
            Path to the exported file
        """
        return self.audit.export(
            output_path=output_path,
            format=format,
            start_time=start_time,
            end_time=end_time,
        )

    # =========================================================================
    # Private methods
    # =========================================================================

    def _build_context(self, prompt: str, **kwargs) -> "PipelineContext":
        """Build the pipeline context object for a request."""
        from .pipeline import PipelineContext
        validate_prompt(prompt)
        return PipelineContext(
            prompt=prompt,
            config=self.config,
            **kwargs,
        )

    def _run_inference(self, ctx: "PipelineContext") -> "PipelineContext":
        """Run actual model inference using the selected provider."""
        return self.compute.infer(ctx)

    def _build_response(
        self,
        ctx: "PipelineContext",
        request_id: str,
        pipeline_start: float,
    ) -> OmbreResponse:
        """Build the final OmbreResponse from pipeline context."""
        pipeline_ms = round((time.time() - pipeline_start) * 1000, 2)
        return OmbreResponse(
            text=ctx.response_text,
            confidence=ctx.confidence_score,
            cost_saved=ctx.cost_saved,
            audit_id=ctx.audit_id,
            request_id=request_id,
            model=ctx.selected_model,
            provider=ctx.selected_provider,
            tokens_used=ctx.tokens_used,
            tokens_saved=ctx.tokens_saved,
            latency_ms=pipeline_ms,
            hallucinations_caught=ctx.hallucinations_caught,
            threats_blocked=ctx.threats_blocked,
            cache_hit=ctx.cache_hit,
            agents_activated=ctx.agents_activated,
            metadata=ctx.metadata,
        )

    def _build_cached_response(
        self,
        ctx: "PipelineContext",
        request_id: str,
        pipeline_start: float,
    ) -> OmbreResponse:
        """Build response from cache hit."""
        pipeline_ms = round((time.time() - pipeline_start) * 1000, 2)
        return OmbreResponse(
            text=ctx.cached_response,
            confidence=ctx.confidence_score or 1.0,
            cost_saved=ctx.cost_saved,
            audit_id=ctx.audit_id or generate_request_id(),
            request_id=request_id,
            model="cache",
            provider="ombre-cache",
            tokens_used=0,
            tokens_saved=ctx.estimated_tokens,
            latency_ms=pipeline_ms,
            hallucinations_caught=0,
            threats_blocked=ctx.threats_blocked,
            cache_hit=True,
            agents_activated=ctx.agents_activated,
            metadata=ctx.metadata,
        )

    def _build_blocked_response(
        self,
        ctx: "PipelineContext",
        request_id: str,
    ) -> OmbreResponse:
        """Build response for security-blocked requests."""
        return OmbreResponse(
            text="[Request blocked by Ombre Security Agent]",
            confidence=0.0,
            cost_saved=0.0,
            audit_id=ctx.audit_id or generate_request_id(),
            request_id=request_id,
            model=None,
            provider=None,
            tokens_used=0,
            tokens_saved=0,
            latency_ms=0,
            hallucinations_caught=0,
            threats_blocked=ctx.threats_blocked,
            cache_hit=False,
            blocked=True,
            block_reason=ctx.block_reason,
            agents_activated=ctx.agents_activated,
            metadata=ctx.metadata,
        )

    def _build_error_response(
        self,
        error: str,
        request_id: str,
    ) -> OmbreResponse:
        """Build response for pipeline errors."""
        return OmbreResponse(
            text=f"[Ombre pipeline error: {error}]",
            confidence=0.0,
            cost_saved=0.0,
            audit_id=generate_request_id(),
            request_id=request_id,
            model=None,
            provider=None,
            tokens_used=0,
            tokens_saved=0,
            latency_ms=0,
            hallucinations_caught=0,
            threats_blocked=0,
            cache_hit=False,
            error=error,
            agents_activated=[],
            metadata={},
        )

    def __repr__(self) -> str:
        return (
            f"Ombre(version={self.VERSION}, "
            f"session={self.session_id[:8]}..., "
            f"providers={self.config.available_providers})"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.audit.flush()
        self.memory.flush()
        logger.info(f"Ombre session closed | session={self.session_id}")
        return False
