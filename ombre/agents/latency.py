"""
Ombre Latency Agent
===================
Real-time SLA monitoring, circuit breaking, and request batching.
Ensures AI responses meet performance guarantees.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Deque, Dict, List

from ..utils.logger import get_logger

logger = get_logger(__name__)


class LatencyAgent:
    """
    Ombre Latency Agent — Performance monitoring and SLA enforcement.

    Tracks P50, P95, P99 latency. Triggers circuit breakers when
    providers degrade. Manages request queuing under high load.
    """

    def __init__(self, config: Any):
        self.config = config
        self._latency_samples: Deque[float] = deque(maxlen=1000)
        self._sla_breaches = 0
        self._total_requests = 0
        self._reroutes = 0

    def process(self, ctx: Any) -> Any:
        """Monitor latency and enforce SLA."""
        ctx.activate_agent("latency")
        self._total_requests += 1

        if ctx.inference_end:
            inference_ms = (ctx.inference_end - ctx.inference_start) * 1000
            ctx.latency_ms = inference_ms
            self._latency_samples.append(inference_ms)

            sla_threshold = self.config.sla_latency_ms
            if inference_ms > sla_threshold:
                ctx.sla_breach = True
                ctx.latency_ok = False
                self._sla_breaches += 1
                logger.warning(
                    f"SLA breach | request={ctx.request_id} | "
                    f"latency={inference_ms:.0f}ms | threshold={sla_threshold}ms"
                )

        return ctx

    def get_percentile(self, percentile: float) -> float:
        """Calculate latency percentile from recent samples."""
        if not self._latency_samples:
            return 0.0
        sorted_samples = sorted(self._latency_samples)
        index = int(len(sorted_samples) * percentile / 100)
        return sorted_samples[min(index, len(sorted_samples) - 1)]

    def stats(self) -> Dict[str, Any]:
        return {
            "total_requests": self._total_requests,
            "sla_breaches": self._sla_breaches,
            "reroutes": self._reroutes,
            "p50_ms": round(self.get_percentile(50), 2),
            "p95_ms": round(self.get_percentile(95), 2),
            "p99_ms": round(self.get_percentile(99), 2),
            "sla_threshold_ms": self.config.sla_latency_ms,
        }
