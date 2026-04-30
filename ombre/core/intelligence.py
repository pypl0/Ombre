"""
Ombre Shared Threat Intelligence
==================================
The nervous system of the Ombre swarm.

Every agent reads from and writes to this bus.
One detection ripples through the entire system instantly.

This is what makes Ombre feel like AGI-level security —
not one guard at one door, but a living immune system
that adapts in real time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ThreatSignal:
    """A threat signal from any agent in the swarm."""
    agent: str
    threat_type: str
    severity: str  # critical, high, medium, low
    confidence: float  # 0.0 to 1.0
    detail: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ThreatIntelligenceBus:
    """
    Shared intelligence between all Ombre agents.
    
    When SecurityAgent detects injection → Vault tightens
    When Firewall finds malicious content → ZeroTrust flags user
    When Contract is violated → Audit escalates
    
    The swarm thinks together.
    """

    def __init__(self):
        self._signals: List[ThreatSignal] = []
        self._threat_level: str = "normal"  # normal, elevated, critical
        self._user_risk_scores: Dict[str, float] = {}
        self._session_risk_scores: Dict[str, float] = {}
        self._blocked_patterns: List[str] = []
        self._active_agents: List[str] = []

    def emit(self, signal: ThreatSignal) -> None:
        """Any agent emits a threat signal to the bus."""
        self._signals.append(signal)
        self._recalculate_threat_level()
        self._update_risk_scores(signal)

    def get_threat_level(self) -> str:
        """Current system-wide threat level."""
        return self._threat_level

    def get_user_risk(self, user_id: str) -> float:
        """Risk score for a specific user (0.0 = safe, 1.0 = critical)."""
        return self._user_risk_scores.get(user_id, 0.0)

    def get_session_risk(self, session_id: str) -> float:
        """Risk score for a specific session."""
        return self._session_risk_scores.get(session_id, 0.0)

    def should_escalate(self, ctx: Any) -> bool:
        """Should this request be treated with extra scrutiny?"""
        user_risk = self.get_user_risk(ctx.user_id or "")
        session_risk = self.get_session_risk(ctx.session_id)
        return (
            user_risk > 0.5 or
            session_risk > 0.5 or
            self._threat_level == "critical"
        )

    def register_agent(self, agent_name: str) -> None:
        """Register an agent as active in the swarm."""
        if agent_name not in self._active_agents:
            self._active_agents.append(agent_name)

    def get_recent_signals(self, limit: int = 10) -> List[ThreatSignal]:
        """Get most recent threat signals."""
        return self._signals[-limit:]

    def _recalculate_threat_level(self) -> None:
        """Recalculate system threat level from recent signals."""
        if not self._signals:
            self._threat_level = "normal"
            return

        recent = self._signals[-10:]
        critical = sum(1 for s in recent if s.severity == "critical")
        high = sum(1 for s in recent if s.severity == "high")

        if critical >= 2 or high >= 5:
            self._threat_level = "critical"
        elif critical >= 1 or high >= 2:
            self._threat_level = "elevated"
        else:
            self._threat_level = "normal"

    def _update_risk_scores(self, signal: ThreatSignal) -> None:
        """Update risk scores based on new signal."""
        user_id = signal.metadata.get("user_id")
        session_id = signal.metadata.get("session_id")

        severity_weights = {
            "critical": 0.4,
            "high": 0.2,
            "medium": 0.1,
            "low": 0.05,
        }
        weight = severity_weights.get(signal.severity, 0.1)

        if user_id:
            current = self._user_risk_scores.get(user_id, 0.0)
            self._user_risk_scores[user_id] = min(1.0, current + weight)

        if session_id:
            current = self._session_risk_scores.get(session_id, 0.0)
            self._session_risk_scores[session_id] = min(1.0, current + weight)

    def summary(self) -> Dict[str, Any]:
        return {
            "threat_level": self._threat_level,
            "total_signals": len(self._signals),
            "active_agents": self._active_agents,
            "high_risk_users": len([
                u for u, r in self._user_risk_scores.items() if r > 0.5
            ]),
            "recent_signals": len(self.get_recent_signals()),
  }
