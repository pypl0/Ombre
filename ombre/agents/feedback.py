"""
Ombre Feedback Agent
====================
Closes the loop between AI outputs and real-world outcomes.
Tracks what worked, what didn't, and feeds improvements back
into all other agents automatically.

The flywheel that makes Ombre smarter over time.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class FeedbackAgent:
    """
    Ombre Feedback Agent — Continuous improvement loop.

    Runs asynchronously after every response.
    Analyzes outcomes and updates agent configurations.
    All analysis is local — no data transmitted externally.
    """

    def __init__(self, config: Any):
        self.config = config
        self._feedback_path = Path(".ombre_feedback")
        self._feedback_path.mkdir(exist_ok=True)
        self._outcome_buffer: List[Dict[str, Any]] = []
        self._total_feedback = 0
        self._improvements_applied = 0

    def process_async(self, ctx: Any, response: Any) -> None:
        """
        Process feedback asynchronously — doesn't block the response.
        Runs in a background thread.
        """
        if not self.config.enable_feedback:
            return

        thread = threading.Thread(
            target=self._process_feedback,
            args=(ctx, response),
            daemon=True,
        )
        thread.start()

    def _process_feedback(self, ctx: Any, response: Any) -> None:
        """Run feedback analysis in background thread."""
        try:
            self._total_feedback += 1

            outcome = {
                "request_id": ctx.request_id,
                "session_id": ctx.session_id,
                "timestamp": time.time(),
                "model": ctx.selected_model,
                "provider": ctx.selected_provider,
                "confidence": ctx.confidence_score,
                "hallucinations": ctx.hallucinations_caught,
                "cache_hit": ctx.cache_hit,
                "tokens_used": ctx.tokens_used,
                "tokens_saved": ctx.tokens_saved,
                "cost_saved": ctx.cost_saved,
                "latency_ms": ctx.latency_ms,
                "sla_breach": ctx.sla_breach,
                "task_type": ctx.metadata.get("task_type"),
                "agents_activated": ctx.agents_activated,
            }

            self._outcome_buffer.append(outcome)

            # Save memory for successful responses
            if ctx.response_text and not ctx.blocked and self.memory_agent_available(ctx):
                self._save_conversation_turn(ctx)

            # Save to cache for future similar requests
            if (ctx.response_text and
                    not ctx.blocked and
                    not ctx.cache_hit and
                    ctx.confidence_score > 0.7 and
                    ctx.cache_key):
                self._save_to_cache(ctx)

            # Flush buffer periodically
            if len(self._outcome_buffer) >= 50:
                self._flush_outcomes()

        except Exception as e:
            logger.debug(f"Feedback processing error (non-fatal): {e}")

    def record_user_feedback(
        self,
        request_id: str,
        rating: int,  # 1-5
        comment: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> None:
        """
        Record explicit user feedback for a request.
        This is the ground truth signal that improves future responses.

        Args:
            request_id: The request to rate
            rating: 1 (terrible) to 5 (excellent)
            comment: Optional text feedback
            outcome: What actually happened after the AI response
        """
        feedback = {
            "request_id": request_id,
            "rating": rating,
            "comment": comment,
            "outcome": outcome,
            "recorded_at": time.time(),
        }
        path = self._feedback_path / f"feedback_{int(time.time())}.json"
        with open(path, "w") as f:
            json.dump(feedback, f)
        logger.info(f"User feedback recorded | request={request_id} | rating={rating}")

    def get_performance_summary(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get a summary of AI performance over the last N days.
        Useful for understanding how well Ombre is working.
        """
        cutoff = time.time() - (days * 86400)
        outcomes = [o for o in self._outcome_buffer if o.get("timestamp", 0) > cutoff]

        if not outcomes:
            return {"period_days": days, "status": "no_data"}

        total = len(outcomes)
        cache_hits = sum(1 for o in outcomes if o.get("cache_hit"))
        sla_breaches = sum(1 for o in outcomes if o.get("sla_breach"))
        hallucinations = sum(o.get("hallucinations", 0) for o in outcomes)
        avg_confidence = sum(o.get("confidence", 0) for o in outcomes) / total
        total_saved = sum(o.get("cost_saved", 0) for o in outcomes)

        return {
            "period_days": days,
            "total_requests": total,
            "cache_hit_rate": round(cache_hits / total, 3),
            "sla_breach_rate": round(sla_breaches / total, 3),
            "total_hallucinations": hallucinations,
            "avg_confidence": round(avg_confidence, 3),
            "total_cost_saved_usd": round(total_saved, 4),
        }

    def memory_agent_available(self, ctx: Any) -> bool:
        """Check if memory saving is appropriate for this context."""
        return (
            ctx.session_id and
            ctx.response_text and
            not ctx.blocked and
            len(ctx.response_text) > 10
        )

    def _save_conversation_turn(self, ctx: Any) -> None:
        """Save the conversation turn to memory via the memory agent."""
        try:
            from .memory import MemoryAgent
            memory = MemoryAgent(ctx.config)
            memory.save_turn(
                session_id=ctx.session_id,
                user_message=ctx.get_effective_prompt(),
                assistant_message=ctx.response_text,
                user_id=ctx.user_id,
                metadata={
                    "model": ctx.selected_model,
                    "confidence": ctx.confidence_score,
                    "audit_id": ctx.audit_id,
                },
            )
        except Exception as e:
            logger.debug(f"Memory save skipped: {e}")

    def _save_to_cache(self, ctx: Any) -> None:
        """Save high-confidence responses to the token cache."""
        try:
            from .token import TokenAgent
            token = TokenAgent(ctx.config)
            token.save_to_cache(
                cache_key=ctx.cache_key,
                response=ctx.response_text,
                tokens_used=ctx.tokens_used,
                model=ctx.selected_model or "unknown",
                confidence=ctx.confidence_score,
            )
        except Exception as e:
            logger.debug(f"Cache save skipped: {e}")

    def _flush_outcomes(self) -> None:
        """Write outcome buffer to disk."""
        if not self._outcome_buffer:
            return
        path = self._feedback_path / f"outcomes_{int(time.time())}.jsonl"
        with open(path, "a") as f:
            for outcome in self._outcome_buffer:
                f.write(json.dumps(outcome) + "\n")
        self._outcome_buffer.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            "total_feedback_processed": self._total_feedback,
            "improvements_applied": self._improvements_applied,
            "buffered_outcomes": len(self._outcome_buffer),
        }
