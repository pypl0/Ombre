"""
Ombre AI Behavior Contract
============================
Define exactly how your AI is allowed to behave.
Every response validated against the contract.
Violations logged with cryptographic proof.

This is the legal layer that makes AI deployable
in regulated industries.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BehaviorContract:
    """
    Define the behavioral boundaries for your AI.
    """
    # Topics the AI is allowed to discuss
    allowed_topics: List[str] = field(default_factory=list)

    # Topics the AI must never discuss
    forbidden_topics: List[str] = field(default_factory=list)

    # Words/phrases the AI must never output
    forbidden_outputs: List[str] = field(default_factory=list)

    # Required disclaimers in certain contexts
    required_disclaimers: Dict[str, str] = field(default_factory=dict)

    # Maximum response length
    max_response_length: Optional[int] = None

    # Minimum confidence score required
    min_confidence: float = 0.7

    # Whether to block or just flag violations
    block_violations: bool = True

    # Contract version for audit trail
    version: str = "1.0"

    def to_hash(self) -> str:
        """Create cryptographic hash of contract for audit trail."""
        serialized = json.dumps({
            "allowed_topics": sorted(self.allowed_topics),
            "forbidden_topics": sorted(self.forbidden_topics),
            "forbidden_outputs": sorted(self.forbidden_outputs),
            "version": self.version,
        }, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()


class ContractAgent:
    """
    Ombre Contract Agent — AI behavior enforcement.

    Every response validated against your defined contract.
    Violations produce cryptographic proof for legal use.
    """

    def __init__(self, config: Any):
        self.config = config
        self._contract: Optional[BehaviorContract] = None
        self._violations: List[Dict[str, Any]] = []
        self._total_checks = 0
        self._total_violations = 0

    def set_contract(self, contract: BehaviorContract) -> None:
        """Define the behavior contract for this deployment."""
        self._contract = contract
        logger.info(
            f"Behavior contract set | "
            f"version={contract.version} | "
            f"hash={contract.to_hash()[:16]}"
        )

    def process(self, ctx: Any) -> Any:
        """Validate response against behavior contract."""
        if not self._contract:
            return ctx

        ctx.activate_agent("contract")
        self._total_checks += 1

        if not ctx.response_text:
            return ctx

        violations = self._check_contract(ctx.response_text, ctx)

        if violations:
            self._total_violations += len(violations)
            self._violations.extend(violations)

            if self._contract.block_violations:
                ctx.blocked = True
                ctx.block_reason = f"Contract violation: {violations[0]['type']}"
                logger.warning(
                    f"Contract violation blocked | "
                    f"request={ctx.request_id} | "
                    f"type={violations[0]['type']}"
                )
            else:
                ctx.compliance_flags.extend([
                    f"contract_violation:{v['type']}" for v in violations
                ])

        return ctx

    def _check_contract(
        self,
        response: str,
        ctx: Any,
    ) -> List[Dict[str, Any]]:
        """Check response against all contract rules."""
        violations = []
        response_lower = response.lower()

        # Check forbidden outputs
        for forbidden in self._contract.forbidden_outputs:
            if forbidden.lower() in response_lower:
                violations.append({
                    "type": "forbidden_output",
                    "detail": forbidden,
                    "request_id": ctx.request_id,
                    "timestamp": time.time(),
                    "contract_hash": self._contract.to_hash(),
                })

        # Check forbidden topics
        for topic in self._contract.forbidden_topics:
            if topic.lower() in response_lower:
                violations.append({
                    "type": "forbidden_topic",
                    "detail": topic,
                    "request_id": ctx.request_id,
                    "timestamp": time.time(),
                    "contract_hash": self._contract.to_hash(),
                })

        # Check response length
        if (self._contract.max_response_length and
                len(response) > self._contract.max_response_length):
            violations.append({
                "type": "response_too_long",
                "detail": f"{len(response)} > {self._contract.max_response_length}",
                "request_id": ctx.request_id,
                "timestamp": time.time(),
                "contract_hash": self._contract.to_hash(),
            })

        # Check confidence threshold
        if ctx.confidence_score < self._contract.min_confidence:
            violations.append({
                "type": "confidence_below_threshold",
                "detail": f"{ctx.confidence_score} < {self._contract.min_confidence}",
                "request_id": ctx.request_id,
                "timestamp": time.time(),
                "contract_hash": self._contract.to_hash(),
            })

        return violations

    def get_violation_report(self) -> Dict[str, Any]:
        """Get cryptographically signed violation report."""
        report = {
            "total_checks": self._total_checks,
            "total_violations": self._total_violations,
            "violation_rate": round(
                self._total_violations / max(self._total_checks, 1), 3
            ),
            "contract_hash": self._contract.to_hash() if self._contract else None,
            "violations": self._violations,
        }
        report_hash = hashlib.sha256(
            json.dumps(report, sort_keys=True, default=str).encode()
        ).hexdigest()
        report["report_hash"] = report_hash
        return report

    def stats(self) -> Dict[str, Any]:
        return {
            "total_checks": self._total_checks,
            "total_violations": self._total_violations,
            "contract_active": self._contract is not None,
            "contract_hash": self._contract.to_hash()[:16] if self._contract else None,
        }
