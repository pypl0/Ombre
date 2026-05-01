"""
Ombre Core Client
=================
The AI security perimeter. 17 autonomous agents.
One swarm intelligence. Zero data transmission.

Your data never leaves your infrastructure.
You bring your own API keys.

Usage:
    from ombre import Ombre

    ai = Ombre(openai_key="sk-...")
    response = ai.run("Your prompt here")
    print(response.text)
    print(response.confidence)
    print(response.audit_id)
    print(response.threats_blocked)
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
from .agents.cost import CostAgent
from .agents.compliance import ComplianceAgent
from .agents.vault import VaultAgent
from .agents.firewall import AIFirewall
from .agents.contract import ContractAgent, BehaviorContract
from .agents.zerotrust import ZeroTrustGateway
from .agents.sentinel import SentinelAgent
from .agents.guardian import GuardianAgent
from .core import ThreatIntelligenceBus
from .utils.logger import get_logger
from .utils.validators import validate_prompt, validate_config
from .utils.crypto import generate_request_id

logger = get_logger(__name__)


class Ombre:
    """
    Ombre — The AI Security Perimeter.

    17 autonomous agents forming a unified swarm.
    Shared threat intelligence across all agents.
    Runs entirely within your own infrastructure.
    """

    VERSION = "2.0.0"

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
        enable_telemetry: bool = False,
    ):
        self.session_id = str(uuid.uuid4())
        self._start_time = time.time()

        validate_config(
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            groq_key=groq_key,
            ombre_key=ombre_key,
        )

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

        self.config.enable_telemetry = False
        logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
        self._init_agents()

        logger.info(
            f"Ombre v{self.VERSION} initialized | "
            f"session={self.session_id} | "
            f"agents=17 | "
            f"providers={self.config.available_providers}"
        )

    def _init_agents(self) -> None:
        """Initialize all 17 agents with shared threat intelligence."""

        # Shared threat intelligence bus — the nervous system
        self._intel = ThreatIntelligenceBus()

        # Core pipeline agents
        self.security = SecurityAgent(self.config)
        self.memory = MemoryAgent(self.config)
        self.token = TokenAgent(self.config)
        self.compute = ComputeAgent(self.config)
        self.truth = TruthAgent(self.config)
        self.latency = LatencyAgent(self.config)
        self.reliability = ReliabilityAgent(self.config)
        self.audit = AuditAgent(self.config)
        self.feedback = FeedbackAgent(self.config)
        self.cost = CostAgent(self.config)
        self.compliance = ComplianceAgent(self.config)

        # Security swarm — all share the intelligence bus
        self.vault = VaultAgent(self.config)
        self.firewall = AIFirewall(self.config)
        self.contract = ContractAgent(self.config)
        self.zerotrust = ZeroTrustGateway(self.config)
        self.sentinel = SentinelAgent(self.config, self._intel)
        self.guardian = GuardianAgent(self.config, self._intel)

        logger.debug("Ombre swarm initialized — 17 agents active")

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
        request_id = generate_request_id()
        pipeline_start = time.time()

        logger.info(f"Pipeline start | request={request_id}")

        try:
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

            # === SECURITY SWARM — runs first ===

            # Sentinel sets security posture
            ctx = self.sentinel.process(ctx)
            if ctx.blocked:
                return self._build_blocked_response(ctx, request_id)

            # Zero Trust — verify user access
            ctx = self.zerotrust.process(ctx)
            if ctx.blocked:
                return self._build_blocked_response(ctx, request_id)

            # Vault — tokenize PII before anything sees it
            ctx = self.vault.process(ctx)

            # Firewall — scan all content for indirect injection
            ctx = self.firewall.process(ctx)

            # Security — direct injection and threat blocking
            ctx = self.security.process(ctx)
            if ctx.blocked:
                return self._build_blocked_response(ctx, request_id)

            # Guardian — runtime anomaly detection
            ctx = self.guardian.process(ctx)

            # === CORE PIPELINE ===

            ctx = self.memory.process(ctx)

            ctx = self.token.process(ctx)
            if ctx.cache_hit:
                # Restore vault tokens in cached response
                ctx = self.vault.restore(ctx)
                logger.info(f"Cache hit | request={request_id}")
                return self._build_cached_response(ctx, request_id, pipeline_start)

            ctx = self.compute.process(ctx)
            ctx = self.truth.process(ctx)
            ctx = self._run_inference(ctx)

            # Restore vault tokens in response
            ctx = self.vault.restore(ctx)

            ctx = self.latency.process(ctx)
            ctx = self.reliability.process(ctx)
            ctx = self.contract.process(ctx)
            if ctx.blocked:
                return self._build_blocked_response(ctx, request_id)

            ctx = self.compliance.process(ctx)
            ctx = self.audit.process(ctx)
            self.cost.record_spend(ctx)

            # Sentinel post-process — learns from swarm
            ctx = self.sentinel.post_process(ctx)

            response = self._build_response(ctx, request_id, pipeline_start)
            self.feedback.process_async(ctx, response)

            pipeline_ms = round((time.time() - pipeline_start) * 1000, 2)
            logger.info(
                f"Pipeline complete | request={request_id} | "
                f"duration={pipeline_ms}ms | "
                f"model={ctx.selected_model} | "
                f"threats_blocked={ctx.threats_blocked}"
            )

            return response

        except Exception as e:
            logger.error(f"Pipeline error | request={request_id} | error={str(e)}")
            return self._build_error_response(str(e), request_id)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> OmbreResponse:
        if not messages:
            raise ValueError("Messages list cannot be empty")

        last_message = messages[-1]
        if last_message.get("role") != "user":
            raise ValueError("Last message must be from user")

        prompt = last_message["content"]
        history = messages[:-1]

        context_parts = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_parts.append(f"{role.upper()}: {content}")

        context = "\n".join(context_parts) if context_parts else None

        return self.run(
            prompt=prompt,
            context=context,
            system=system,
            model=model,
            session_id=session_id,
            user_id=user_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def embed(
        self,
        text: Union[str, List[str]],
        model: str = "auto",
    ) -> Dict[str, Any]:
        if isinstance(text, str):
            texts = [text]
        else:
            texts = text

        request_id = generate_request_id()
        results = []

        for t in texts:
            ctx = self._build_context(
                prompt=t,
                model=model,
                request_id=request_id,
                session_id=self.session_id,
                metadata={"operation": "embed"},
            )
            ctx = self.security.process(ctx)

            if not ctx.blocked:
                embedding = self.compute.embed(ctx)
                results.append(embedding)
            else:
                results.append(None)

        return {
            "embeddings": results,
            "model": self.config.default_embedding_model,
            "request_id": request_id,
            "count": len(results),
        }

    def batch(
        self,
        prompts: List[str],
        model: str = "auto",
        concurrency: int = 5,
        session_id: Optional[str] = None,
    ) -> List[OmbreResponse]:
        import concurrent.futures

        results = [None] * len(prompts)

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(
                    self.run,
                    prompt=p,
                    model=model,
                    session_id=session_id or self.session_id,
                ): i
                for i, p in enumerate(prompts)
            }
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = self._build_error_response(
                        str(e), generate_request_id()
                    )

        return results

    def scan_code(self, code: str, filename: str = "unknown") -> Dict[str, Any]:
        """Scan code for AI security vulnerabilities using Guardian."""
        vulns = self.guardian.scan_code(code, filename)
        return self.guardian._generate_report(vulns, 1, filename)

    def scan_repository(self, path: str) -> Dict[str, Any]:
        """Scan entire repository for AI security vulnerabilities."""
        return self.guardian.scan_repository(path)

    def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        from .server import OmbreServer
        server = OmbreServer(self)
        logger.info(f"Starting Ombre server on {host}:{port}")
        server.run(host=host, port=port)

    def set_budget(self, limit: float, alert_threshold: float = 0.8) -> None:
        """Set AI spend budget limit."""
        self.cost.set_budget(limit, alert_threshold)

    def set_contract(self, contract: BehaviorContract) -> None:
        """Set AI behavior contract."""
        self.contract.set_contract(contract)

    def get_intelligence_report(self) -> Dict[str, Any]:
        """Get full swarm intelligence report from Sentinel."""
        return self.sentinel.get_intelligence_report()

    def get_cost_report(self) -> Dict[str, Any]:
        """Get cost breakdown and forecast."""
        return self.cost.get_breakdown()

    def get_compliance_report(
        self,
        framework: str = "eu_ai_act",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate compliance report."""
        return self.compliance.generate_report(framework, output_path)

    def stats(self) -> Dict[str, Any]:
        uptime = round(time.time() - self._start_time, 2)
        return {
            "version": self.VERSION,
            "session_id": self.session_id,
            "uptime_seconds": uptime,
            "providers": self.config.available_providers,
            "swarm_intelligence": self._intel.summary(),
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
                "cost": self.cost.stats(),
                "compliance": self.compliance.stats(),
                "vault": self.vault.stats(),
                "firewall": self.firewall.stats(),
                "contract": self.contract.stats(),
                "zerotrust": self.zerotrust.stats(),
                "sentinel": self.sentinel.stats(),
                "guardian": self.guardian.stats(),
            },
        }

    def reset_memory(self, session_id: Optional[str] = None) -> None:
        target = session_id or self.session_id
        self.memory.clear(target)

    def export_audit(
        self,
        output_path: str,
        format: str = "json",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> str:
        return self.audit.export(
            output_path=output_path,
            format=format,
            start_time=start_time,
            end_time=end_time,
        )

    def _build_context(self, prompt: str, **kwargs):
        from .pipeline import PipelineContext
        validate_prompt(prompt)
        return PipelineContext(
            prompt=prompt,
            config=self.config,
            **kwargs,
        )

    def _run_inference(self, ctx):
        return self.compute.infer(ctx)

    def _build_response(self, ctx, request_id, pipeline_start) -> OmbreResponse:
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

    def _build_cached_response(self, ctx, request_id, pipeline_start) -> OmbreResponse:
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

    def _build_blocked_response(self, ctx, request_id) -> OmbreResponse:
        return OmbreResponse(
            text="[Request blocked by Ombre Security Swarm]",
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

    def _build_error_response(self, error: str, request_id: str) -> OmbreResponse:
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
            f"agents=17, "
            f"providers={self.config.available_providers})"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.audit.flush()
        self.memory.flush()
        logger.info(f"Ombre session closed | session={self.session_id}")
        return False
