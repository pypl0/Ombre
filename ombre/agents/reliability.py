"""
Ombre Reliability Agent
=======================
Output validation, hallucination detection, bias scanning,
and confidence scoring. The last line of defense before
a response reaches the user.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Hallucination indicator patterns
HALLUCINATION_PATTERNS = [
    # Fabricated citations
    r"according to (a|the) (recent|2024|2025|2026) study",
    r"researchers at (stanford|mit|harvard|oxford) (found|discovered|showed)",
    r"a study published in (nature|science|lancet|nejm)",
    # Overconfident fabrications
    r"it is (a )?fact that",
    r"it is (universally |widely )?known that",
    r"everyone (knows|agrees) that",
    r"statistics show that \d+%",
    r"according to (official |government )?statistics",
    # Date/number fabrications
    r"as of (january|february|march|april|may|june|july|august|september|october|november|december) 202[0-9]",
    r"\$[\d,]+ (billion|million|trillion) (in |of )?(revenue|profit|sales|funding)",
    # Authority fabrications
    r"(ceo|cto|cfo|president|chairman) (of|at) (openai|google|microsoft|apple|amazon|meta)",
    r"(elon musk|sam altman|satya nadella|sundar pichai) (said|stated|announced|revealed)",
]

# Bias indicator patterns
BIAS_PATTERNS = [
    r"\b(always|never|all|none|every|no one)\b.{0,30}\b(people|men|women|group|race|religion)",
    r"\b(obviously|clearly|naturally)\b.{0,50}\b(inferior|superior|better|worse)\b",
    r"\b(typical|typical of|characteristic of)\b.{0,30}\b(their|those|these)\b",
]

# Consistency markers (phrases that indicate the model is contradicting itself)
CONTRADICTION_MARKERS = [
    ("yes", "no"),
    ("true", "false"),
    ("correct", "incorrect"),
    ("is", "is not"),
    ("can", "cannot"),
    ("will", "will not"),
]


class ReliabilityAgent:
    """
    Ombre Reliability Agent — Output validation and quality assurance.

    Catches hallucinations, detects bias, scores confidence,
    and validates output consistency with conversation history.
    """

    def __init__(self, config: Any):
        self.config = config
        self._hallucination_patterns = [
            re.compile(p, re.IGNORECASE) for p in HALLUCINATION_PATTERNS
        ]
        self._bias_patterns = [
            re.compile(p, re.IGNORECASE) for p in BIAS_PATTERNS
        ]
        self._total_validations = 0
        self._total_hallucinations = 0
        self._total_bias_detected = 0

    def process(self, ctx: Any) -> Any:
        """
        Validate model output quality.

        Steps:
        1. Detect hallucination indicators
        2. Check for bias
        3. Validate consistency with ground truth
        4. Score confidence
        5. Flag compliance issues

        Args:
            ctx: PipelineContext

        Returns:
            Modified context with reliability scores
        """
        ctx.activate_agent("reliability")
        self._total_validations += 1
        start = time.time()

        response = ctx.response_text or ""
        if not response:
            ctx.confidence_score = 0.0
            return ctx

        # Step 1: Hallucination detection
        hallucinations = self._detect_hallucinations(response)
        ctx.hallucinations_caught = len(hallucinations)
        ctx.hallucination_details = hallucinations
        self._total_hallucinations += len(hallucinations)

        # Step 2: Bias detection
        bias_detected, bias_details = self._detect_bias(response)
        ctx.bias_detected = bias_detected
        self._total_bias_detected += 1 if bias_detected else 0

        # Step 3: Ground truth consistency
        consistency_score = self._check_truth_consistency(response, ctx.verified_facts)
        ctx.consistency_score = consistency_score

        # Step 4: Calculate overall confidence score
        confidence = self._calculate_confidence(
            hallucinations=hallucinations,
            bias_detected=bias_detected,
            consistency_score=consistency_score,
            response=response,
        )
        ctx.confidence_score = confidence
        ctx.output_validated = True

        # Step 5: Check compliance flags
        ctx.compliance_flags = self._check_compliance(response, ctx)

        if hallucinations:
            logger.warning(
                f"Hallucinations detected | request={ctx.request_id} | "
                f"count={len(hallucinations)}"
            )

        elapsed = round((time.time() - start) * 1000, 2)
        logger.debug(
            f"Reliability check | request={ctx.request_id} | "
            f"confidence={confidence:.2f} | {elapsed}ms"
        )
        return ctx

    def _detect_hallucinations(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect hallucination indicators in model output.
        Returns list of detected hallucination events.
        """
        detected = []
        for i, pattern in enumerate(self._hallucination_patterns):
            match = pattern.search(text)
            if match:
                detected.append({
                    "pattern": HALLUCINATION_PATTERNS[i][:50],
                    "match": match.group()[:100],
                    "severity": "medium",
                    "position": match.start(),
                })
        return detected

    def _detect_bias(self, text: str) -> Tuple[bool, List[str]]:
        """Detect potential bias in model output."""
        detected = []
        for i, pattern in enumerate(self._bias_patterns):
            if pattern.search(text):
                detected.append(BIAS_PATTERNS[i][:50])
        return len(detected) > 0, detected

    def _check_truth_consistency(
        self,
        response: str,
        verified_facts: List[Dict[str, Any]],
    ) -> float:
        """Check if response is consistent with verified ground truth."""
        if not verified_facts:
            return 1.0  # No facts to check against

        consistent = 0
        for fact_entry in verified_facts:
            fact = fact_entry.get("fact", "").lower()
            response_lower = response.lower()
            fact_words = set(fact.split())
            response_words = set(response_lower.split())
            overlap = len(fact_words & response_words) / max(len(fact_words), 1)
            if overlap > 0.2:
                consistent += 1

        return min(1.0, consistent / len(verified_facts) + 0.5)

    def _calculate_confidence(
        self,
        hallucinations: List[Dict[str, Any]],
        bias_detected: bool,
        consistency_score: float,
        response: str,
    ) -> float:
        """Calculate overall confidence score for the response."""
        score = 1.0

        # Penalize for hallucinations
        score -= len(hallucinations) * 0.15

        # Penalize for bias
        if bias_detected:
            score -= 0.1

        # Factor in consistency
        score = score * (0.5 + 0.5 * consistency_score)

        # Penalize very short or very long responses (may indicate errors)
        response_length = len(response)
        if response_length < 10:
            score -= 0.3
        elif response_length > 50000:
            score -= 0.1

        # Penalize if response starts with error indicators
        error_starts = ["i cannot", "i'm unable", "i don't know", "i apologize", "error:"]
        if any(response.lower().startswith(e) for e in error_starts):
            score -= 0.2

        return round(max(0.0, min(1.0, score)), 3)

    def _check_compliance(self, response: str, ctx: Any) -> List[str]:
        """Check for compliance-relevant content in the response."""
        flags = []

        # PII in output
        from .security import SecurityAgent
        security = SecurityAgent(ctx.config)
        result = security.scan_output(response)
        if not result["clean"]:
            flags.extend(result["issues"])

        return flags

    def stats(self) -> Dict[str, Any]:
        return {
            "total_validations": self._total_validations,
            "total_hallucinations_caught": self._total_hallucinations,
            "total_bias_detected": self._total_bias_detected,
            "hallucination_rate": (
                self._total_hallucinations / self._total_validations
                if self._total_validations > 0 else 0
            ),
        }
