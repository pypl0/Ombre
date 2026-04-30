"""
Ombre Sentinel
===============
The meta-agent. The brain of the swarm.

Sentinel coordinates all security agents simultaneously.
It reads threat intelligence from every agent and makes
system-wide decisions in real time.

Inspired by defensive AI mythology — the guardian that
never sleeps, never misses, never forgets.

This is what AGI-level security feels like.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..core.intelligence import ThreatIntelligenceBus, ThreatSignal
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SentinelAgent:
    """
    Ombre Sentinel — Swarm coordinator and meta-intelligence.

    Sentinel sees everything every agent sees.
    It adapts the entire swarm's behavior in real time.
    
    Three modes:
    - PASSIVE: Monitor and log. Normal operations.
    - ACTIVE: Heightened scrutiny. Recent threats detected.
    - LOCKDOWN: Maximum security. Critical threat active.
    """

    MODES = ["PASSIVE", "ACTIVE", "LOCKDOWN"]

    def __init__(self, config: Any, intel_bus: ThreatIntelligenceBus):
        self.config = config
        self.intel = intel_bus
        self._mode = "PASSIVE"
        self._decisions: List[Dict[str, Any]] = []
        self._total_coordinations = 0
        self.intel.register_agent("sentinel")

    def process(self, ctx: Any) -> Any:
        """
        Sentinel runs BEFORE all other agents.
        Sets the security posture for this entire request.
        """
        ctx.activate_agent("sentinel")
        self._total_coordinations += 1

        # Read threat intelligence
        threat_level = self.intel.get_threat_level()
        user_risk = self.intel.get_user_risk(ctx.user_id or "")
        session_risk = self.intel.get_session_risk(ctx.session_id)

        # Update mode based on intelligence
        self._update_mode(threat_level, user_risk, session_risk)

        # Inject sentinel intelligence into context
        ctx.metadata["sentinel_mode"] = self._mode
        ctx.metadata["threat_level"] = threat_level
        ctx.metadata["user_risk_score"] = user_risk
        ctx.metadata["session_risk_score"] = session_risk

        # In LOCKDOWN mode — block high-risk requests immediately
        if self._mode == "LOCKDOWN" and (user_risk > 0.8 or session_risk > 0.8):
            ctx.blocked = True
            ctx.block_reason = "Sentinel lockdown — high risk session"
            ctx.threats_blocked += 1
            self._log_decision(ctx, "LOCKDOWN_BLOCK", "High risk session blocked")
            logger.warning(
                f"Sentinel lockdown block | "
                f"request={ctx.request_id} | "
                f"user_risk={user_risk:.2f}"
            )
            return ctx

        # In ACTIVE mode — enable all security layers
        if self._mode in ["ACTIVE", "LOCKDOWN"]:
            ctx.metadata["enhanced_security"] = True
            logger.info(
                f"Sentinel {self._mode} mode | "
                f"request={ctx.request_id}"
            )

        self._log_decision(
            ctx,
            "PROCESSED",
            f"Mode={self._mode} threat={threat_level}",
        )
        return ctx

    def post_process(self, ctx: Any) -> Any:
        """
        Sentinel runs AFTER all other agents.
        Learns from what the swarm detected.
        Updates threat intelligence for future requests.
        """
        if ctx.threats_blocked > 0:
            self.intel.emit(ThreatSignal(
                agent="sentinel",
                threat_type="aggregate_threat",
                severity="high" if ctx.threats_blocked > 2 else "medium",
                confidence=0.9,
                detail=f"{ctx.threats_blocked} threats blocked in one request",
                metadata={
                    "user_id": ctx.user_id,
                    "session_id": ctx.session_id,
                    "request_id": ctx.request_id,
                },
            ))

        if ctx.hallucinations_caught > 0:
            self.intel.emit(ThreatSignal(
                agent="sentinel",
                threat_type="reliability_concern",
                severity="medium",
                confidence=0.7,
                detail=f"{ctx.hallucinations_caught} hallucinations in response",
                metadata={
                    "session_id": ctx.session_id,
                    "model": ctx.selected_model,
                },
            ))

        return ctx

    def get_intelligence_report(self) -> Dict[str, Any]:
        """
        Full intelligence report from the swarm.
        This is what makes Ombre feel like AGI.
        """
        return {
            "sentinel_mode": self._mode,
            "threat_intelligence": self.intel.summary(),
            "recent_signals": [
                {
                    "agent": s.agent,
                    "type": s.threat_type,
                    "severity": s.severity,
                    "confidence": s.confidence,
                }
                for s in self.intel.get_recent_signals()
            ],
            "total_coordinations": self._total_coordinations,
            "decisions": self._decisions[-10:],
        }

    def _update_mode(
        self,
        threat_level: str,
        user_risk: float,
        session_risk: float,
    ) -> None:
        """Update Sentinel mode based on threat intelligence."""
        if threat_level == "critical" or user_risk > 0.8 or session_risk > 0.8:
            new_mode = "LOCKDOWN"
        elif threat_level == "elevated" or user_risk > 0.4 or session_risk > 0.4:
            new_mode = "ACTIVE"
        else:
            new_mode = "PASSIVE"

        if new_mode != self._mode:
            logger.warning(
                f"Sentinel mode change | "
                f"{self._mode} → {new_mode} | "
                f"threat={threat_level}"
            )
            self._mode = new_mode

    def _log_decision(
        self,
        ctx: Any,
        decision: str,
        reason: str,
    ) -> None:
        """Log a Sentinel decision."""
        self._decisions.append({
            "request_id": ctx.request_id,
            "decision": decision,
            "reason": reason,
            "mode": self._mode,
            "timestamp": time.time(),
        })

    def stats(self) -> Dict[str, Any]:
        return {
            "mode": self._mode,
            "total_coordinations": self._total_coordinations,
            "threat_intelligence": self.intel.summary(),
  }
