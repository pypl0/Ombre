"""
Ombre Cost Agent
================
Real-time AI spend tracking, budget enforcement,
and cost forecasting. The financial intelligence
layer that makes AI costs predictable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CostAgent:
    """
    Ombre Cost Agent — AI spend intelligence.

    Tracks every dollar spent on AI inference.
    Enforces budgets. Forecasts future spend.
    Alerts when costs exceed thresholds.
    All data stays local — never transmitted externally.
    """

    def __init__(self, config: Any):
        self.config = config
        self._spend_path = Path(".ombre_costs")
        self._spend_path.mkdir(exist_ok=True)
        self._session_spend = 0.0
        self._session_saved = 0.0
        self._request_count = 0
        self._budget_limit: Optional[float] = None
        self._alert_threshold: float = 0.8
        self._spend_history: List[Dict[str, Any]] = []
        self._load_history()

    def process(self, ctx: Any) -> Any:
        """
        Track costs and enforce budget limits.

        Args:
            ctx: PipelineContext

        Returns:
            Modified context with cost tracking active
        """
        ctx.activate_agent("cost")
        self._request_count += 1

        # Check budget before inference
        if self._budget_limit:
            if self._session_spend >= self._budget_limit:
                ctx.blocked = True
                ctx.block_reason = (
                    f"Budget limit reached: "
                    f"${self._session_spend:.4f} / ${self._budget_limit:.4f}"
                )
                logger.warning(
                    f"Budget limit reached | "
                    f"spent=${self._session_spend:.4f} | "
                    f"limit=${self._budget_limit:.4f}"
                )
                return ctx

            # Alert at threshold
            spend_ratio = self._session_spend / self._budget_limit
            if spend_ratio >= self._alert_threshold:
                logger.warning(
                    f"Budget alert: {spend_ratio:.0%} of limit used | "
                    f"spent=${self._session_spend:.4f} | "
                    f"limit=${self._budget_limit:.4f}"
                )

        return ctx

    def record_spend(self, ctx: Any) -> None:
        """Record actual spend after inference completes."""
        actual_cost = getattr(ctx, 'actual_cost', 0.0)
        cost_saved = getattr(ctx, 'cost_saved', 0.0)

        self._session_spend += actual_cost
        self._session_saved += cost_saved

        # Record to history
        record = {
            "timestamp": time.time(),
            "request_id": ctx.request_id,
            "model": ctx.selected_model,
            "provider": ctx.selected_provider,
            "tokens_used": ctx.tokens_used,
            "actual_cost": actual_cost,
            "cost_saved": cost_saved,
            "cache_hit": ctx.cache_hit,
        }
        self._spend_history.append(record)

        # Persist to disk
        self._save_record(record)

        logger.debug(
            f"Cost recorded | request={ctx.request_id} | "
            f"cost=${actual_cost:.4f} | saved=${cost_saved:.4f} | "
            f"session_total=${self._session_spend:.4f}"
        )

    def set_budget(
        self,
        limit: float,
        alert_threshold: float = 0.8,
    ) -> None:
        """
        Set a budget limit for AI spend.

        Args:
            limit: Maximum spend in USD before requests are blocked
            alert_threshold: Fraction of budget at which to alert (0.0-1.0)
        """
        self._budget_limit = limit
        self._alert_threshold = alert_threshold
        logger.info(
            f"Budget set | limit=${limit:.2f} | "
            f"alert_at={alert_threshold:.0%}"
        )

    def get_forecast(self, days: int = 30) -> Dict[str, Any]:
        """
        Forecast AI spend for the next N days based on history.

        Args:
            days: Number of days to forecast

        Returns:
            Forecast dictionary with projected costs
        """
        if not self._spend_history:
            return {"forecast_usd": 0.0, "basis": "no_history"}

        # Calculate daily average from recent history
        cutoff = time.time() - (7 * 86400)  # Last 7 days
        recent = [
            r for r in self._spend_history
            if r.get("timestamp", 0) > cutoff
        ]

        if not recent:
            return {"forecast_usd": 0.0, "basis": "no_recent_history"}

        total_recent_spend = sum(r.get("actual_cost", 0) for r in recent)
        daily_average = total_recent_spend / 7
        projected = daily_average * days

        return {
            "forecast_usd": round(projected, 4),
            "daily_average_usd": round(daily_average, 4),
            "forecast_days": days,
            "basis": f"last_7_days_{len(recent)}_requests",
            "total_saved_usd": round(self._session_saved, 4),
        }

    def get_breakdown(self) -> Dict[str, Any]:
        """Get cost breakdown by model and provider."""
        breakdown: Dict[str, float] = {}

        for record in self._spend_history:
            model = record.get("model", "unknown")
            cost = record.get("actual_cost", 0.0)
            breakdown[model] = breakdown.get(model, 0.0) + cost

        return {
            "by_model": breakdown,
            "total_spend_usd": round(self._session_spend, 4),
            "total_saved_usd": round(self._session_saved, 4),
            "total_requests": self._request_count,
            "average_cost_per_request": round(
                self._session_spend / max(self._request_count, 1), 6
            ),
            "cache_savings_usd": round(self._session_saved, 4),
        }

    def export_report(
        self,
        output_path: str,
        format: str = "json",
    ) -> str:
        """
        Export cost report to file.

        Args:
            output_path: Where to write the report
            format: 'json' or 'csv'

        Returns:
            Path to exported file
        """
        report = {
            "generated_at": time.time(),
            "summary": self.get_breakdown(),
            "forecast_30_days": self.get_forecast(30),
            "budget": {
                "limit_usd": self._budget_limit,
                "spent_usd": round(self._session_spend, 4),
                "remaining_usd": round(
                    (self._budget_limit or 0) - self._session_spend, 4
                ) if self._budget_limit else None,
            },
            "history": self._spend_history,
        }

        path = Path(output_path)
        if format == "json":
            with open(path, "w") as f:
                json.dump(report, f, indent=2)
        elif format == "csv":
            import csv
            with open(path, "w", newline="") as f:
                if self._spend_history:
                    writer = csv.DictWriter(
                        f, fieldnames=self._spend_history[0].keys()
                    )
                    writer.writeheader()
                    writer.writerows(self._spend_history)

        logger.info(f"Cost report exported | path={output_path}")
        return str(path)

    def reset_session(self) -> None:
        """Reset session spend counters."""
        self._session_spend = 0.0
        self._session_saved = 0.0
        self._request_count = 0
        logger.info("Cost session reset")

    def _load_history(self) -> None:
        """Load spend history from disk."""
        history_file = self._spend_path / "history.jsonl"
        if not history_file.exists():
            return
        try:
            with open(history_file, "r") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        self._spend_history.append(record)
                        self._session_spend += record.get("actual_cost", 0)
                        self._session_saved += record.get("cost_saved", 0)
                        self._request_count += 1
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"Cost history load failed: {e}")

    def _save_record(self, record: Dict[str, Any]) -> None:
        """Save a spend record to disk."""
        history_file = self._spend_path / "history.jsonl"
        try:
            with open(history_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.debug(f"Cost record save failed: {e}")

    def stats(self) -> Dict[str, Any]:
        """Return cost agent statistics."""
        return {
            "session_spend_usd": round(self._session_spend, 4),
            "session_saved_usd": round(self._session_saved, 4),
            "total_requests": self._request_count,
            "budget_limit_usd": self._budget_limit,
            "forecast_30d": self.get_forecast(30),
}
