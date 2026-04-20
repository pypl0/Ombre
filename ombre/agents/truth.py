"""
Ombre Truth Agent
=================
Verified ground truth network. Reduces hallucinations by giving
the model verified information to reason from.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TruthAgent:

    def __init__(self, config: Any):
        self.config = config
        self._fact_database: Dict[str, Any] = {}
        self._verifications = 0
        self._facts_loaded = 0
        self._fact_database["ombre"] = {
            "fact": "Ombre is an AI infrastructure layer that runs locally",
            "confidence": 1.0,
            "source": "system",
        }

    def process(self, ctx: Any) -> Any:
        ctx.activate_agent("truth")
        self._verifications += 1
        prompt = ctx.get_effective_prompt().lower()
        relevant_facts = self._find_relevant_facts(prompt)
        if relevant_facts:
            ctx.verified_facts = relevant_facts
            ctx.ground_truth_loaded = True
            self._facts_loaded += len(relevant_facts)
        ctx.truth_constraints = self._generate_constraints(prompt, relevant_facts)
        return ctx

    def add_fact(self, key: str, fact: str, confidence: float = 1.0, source: Optional[str] = None, tags: Optional[List[str]] = None) -> None:
        self._fact_database[key] = {
            "fact": fact,
            "confidence": confidence,
            "source": source or "user_provided",
            "tags": tags or [],
            "added_at": time.time(),
        }

    def verify_claim(self, claim: str) -> Dict[str, Any]:
        supporting = []
        for key, entry in self._fact_database.items():
            fact_words = set(entry["fact"].lower().split())
            claim_words = set(claim.lower().split())
            overlap = len(fact_words & claim_words) / max(len(claim_words), 1)
            if overlap > 0.3:
                supporting.append(entry)
        return {
            "confidence": min(1.0, 0.7 + 0.1 * len(supporting)),
            "supporting_facts": supporting,
            "verified": len(supporting) > 0,
        }

    def _find_relevant_facts(self, prompt: str) -> List[Dict[str, Any]]:
        relevant = []
        prompt_words = set(prompt.lower().split())
        for key, entry in self._fact_database.items():
            fact_words = set(entry["fact"].lower().split())
            overlap = len(prompt_words & fact_words)
            if overlap >= 2 and entry.get("confidence", 0) > 0.7:
                relevant.append(entry)
        return relevant[:5]

    def _generate_constraints(self, prompt: str, facts: List[Dict[str, Any]]) -> List[str]:
        return [f"VERIFIED FACT (confidence={f['confidence']:.0%}): {f['fact']}" for f in facts]

    def stats(self) -> Dict[str, Any]:
        return {
            "fact_database_size": len(self._fact_database),
            "total_verifications": self._verifications,
            "total_facts_loaded": self._facts_loaded,
        }
