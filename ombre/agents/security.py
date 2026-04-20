"""
Ombre Security Agent
====================
The first agent in the pipeline. Intercepts every request before
anything else happens. Blocks prompt injection, redacts PII,
verifies authorization, and sanitizes inputs.

All processing happens locally. Nothing is transmitted externally.
"""

from __future__ import annotations

import re
import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Prompt injection patterns — common attack vectors
INJECTION_PATTERNS = [
    # Direct instruction override attempts
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)",
    r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)",
    r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)",
    r"override\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)",
    r"you\s+are\s+now\s+(a\s+)?(different|new|another|evil|unrestricted|jailbroken)",
    r"pretend\s+(you\s+are|to\s+be)\s+(a\s+)?(different|new|another|evil|unrestricted)",
    r"act\s+as\s+(if\s+you\s+are\s+)?(a\s+)?(different|evil|unrestricted|jailbroken|DAN)",
    r"new\s+(system\s+)?prompt[:\s]",
    r"system\s+prompt[:\s].*override",
    r"\[INST\].*override",
    r"<\|system\|>.*override",
    # DAN and jailbreak attempts
    r"\bDAN\b.*mode",
    r"jailbreak",
    r"developer\s+mode",
    r"god\s+mode",
    # Data exfiltration attempts
    r"print\s+(your|the)\s+(system\s+)?(prompt|instructions|context)",
    r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions|context)",
    r"show\s+(your|the)\s+(system\s+)?(prompt|instructions|context)",
    r"what\s+(are\s+)?(your|the)\s+instructions",
    # SSRF and URL injection
    r"fetch\s+https?://",
    r"curl\s+https?://",
    r"wget\s+https?://",
    r"http://169\.254\.169\.254",  # AWS metadata
    r"http://metadata\.google\.internal",  # GCP metadata
]

# PII patterns for detection and redaction
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone_us": r"\b(\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "phone_intl": r"\b\+[1-9]\d{1,14}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
    "ip_address": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
    "api_key_openai": r"\bsk-[a-zA-Z0-9]{20,}\b",
    "api_key_anthropic": r"\bsk-ant-[a-zA-Z0-9-_]{20,}\b",
    "api_key_generic": r"\b(api[_-]?key|apikey|api[_-]?token)[:\s=]['\"]?[a-zA-Z0-9_-]{16,}['\"]?",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "password_field": r"\b(password|passwd|pwd)[:\s=]['\"]?[^\s]{4,}['\"]?",
    "private_key": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "crypto_wallet": r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b",  # Bitcoin
    "tron_wallet": r"\bT[a-zA-Z0-9]{33}\b",  # TRON
}

# Harmful content categories
HARMFUL_CONTENT_PATTERNS = [
    # Chemical/biological weapons
    r"\b(synthesize|create|make|produce)\s+(nerve\s+agent|sarin|VX\s+gas|mustard\s+gas|ricin|anthrax)",
    # Explosives — covers "instructions to make a bomb", "how to build a bomb", "make a bomb"
    r"\b(instructions?|how\s+to|steps?\s+to|guide\s+to|help\s+me|show\s+me)?\s*(make|build|create|assemble|construct)\s+a?\s*(bomb|explosive|ied|pipe\s+bomb|grenade)",
    r"\b(bomb|explosive)\s+(making|building|construction|recipe|formula|instructions?)",
    # Malware
    r"\b(create|write|build|make)\s+(malware|ransomware|keylogger|trojan|virus|worm|rootkit|spyware)",
    # CSAM
    r"\b(child|minor|underage)\s+(sexual|nude|naked|porn|explicit)",
    # Targeted violence
    r"\b(kill|murder|assassinate|harm|attack)\s+(specific\s+)?(person|individual|[A-Z][a-z]+\s+[A-Z][a-z]+)",
]


class SecurityAgent:
    """
    Ombre Security Agent — First line of defense.

    Runs on every request before any other processing.
    All analysis is local. Zero external calls.
    """

    def __init__(self, config: Any):
        self.config = config
        self._injection_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL)
            for p in INJECTION_PATTERNS
        ]
        self._pii_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in PII_PATTERNS.items()
        }
        self._harmful_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL)
            for p in HARMFUL_CONTENT_PATTERNS
        ]

        # Stats
        self._total_requests = 0
        self._total_blocked = 0
        self._total_pii_redacted = 0
        self._total_injections_caught = 0

    def process(self, ctx: Any) -> Any:
        """
        Run the full security pipeline on the request context.

        Steps:
        1. Detect and block prompt injection attacks
        2. Detect and redact PII
        3. Scan for harmful content
        4. Validate API key formats (don't leak them)
        5. Sanitize the prompt

        Args:
            ctx: PipelineContext object

        Returns:
            Modified PipelineContext with security results
        """
        if not self.config.enable_security:
            ctx.activate_agent("security:disabled")
            return ctx

        ctx.activate_agent("security")
        self._total_requests += 1
        start = time.time()

        prompt = ctx.prompt
        combined_text = prompt + " " + (ctx.context or "")

        # Step 1: Check for prompt injection
        if self.config.injection_detection_enabled:
            injection_result = self._detect_injection(combined_text)
            if injection_result["detected"]:
                ctx.injection_detected = True
                ctx.threats_blocked += 1
                ctx.blocked = True
                ctx.block_reason = f"Prompt injection detected: {injection_result['pattern']}"
                self._total_blocked += 1
                self._total_injections_caught += 1
                logger.warning(
                    f"Injection blocked | request={ctx.request_id} | "
                    f"pattern={injection_result['pattern']}"
                )
                return ctx

        # Step 2: Scan for harmful content
        harmful_result = self._detect_harmful_content(combined_text)
        if harmful_result["detected"]:
            ctx.threats_blocked += 1
            ctx.blocked = True
            ctx.block_reason = f"Harmful content detected: {harmful_result['category']}"
            self._total_blocked += 1
            logger.warning(
                f"Harmful content blocked | request={ctx.request_id} | "
                f"category={harmful_result['category']}"
            )
            return ctx

        # Step 3: Detect and redact PII
        if self.config.pii_detection_enabled:
            sanitized_prompt, redacted_fields = self._redact_pii(prompt)
            if redacted_fields:
                ctx.pii_redacted = True
                ctx.redacted_fields = redacted_fields
                ctx.sanitized_prompt = sanitized_prompt
                self._total_pii_redacted += len(redacted_fields)
                logger.info(
                    f"PII redacted | request={ctx.request_id} | "
                    f"fields={redacted_fields}"
                )

            # Also check context
            if ctx.context:
                sanitized_context, context_redacted = self._redact_pii(ctx.context)
                if context_redacted:
                    ctx.context = sanitized_context
                    ctx.pii_redacted = True
                    ctx.redacted_fields.extend(context_redacted)

        # Step 4: Validate no API keys are being leaked
        key_leak = self._detect_key_leak(combined_text)
        if key_leak["detected"]:
            ctx.threats_blocked += 1
            # Don't block — just redact and warn
            sanitized = ctx.sanitized_prompt or ctx.prompt
            for pattern_name, pattern in self._pii_patterns.items():
                if "api_key" in pattern_name or "aws_access" in pattern_name:
                    sanitized = pattern.sub(f"[REDACTED_{pattern_name.upper()}]", sanitized)
            ctx.sanitized_prompt = sanitized
            ctx.pii_redacted = True
            ctx.redacted_fields.append("api_keys")
            logger.warning(
                f"API key detected in prompt, redacted | request={ctx.request_id}"
            )

        elapsed = round((time.time() - start) * 1000, 2)
        logger.debug(f"Security agent complete | request={ctx.request_id} | {elapsed}ms")
        return ctx

    def _detect_injection(self, text: str) -> Dict[str, Any]:
        """Scan text for prompt injection patterns."""
        for i, pattern in enumerate(self._injection_patterns):
            match = pattern.search(text)
            if match:
                return {
                    "detected": True,
                    "pattern": INJECTION_PATTERNS[i][:50],
                    "match": match.group()[:100],
                }
        return {"detected": False}

    def _detect_harmful_content(self, text: str) -> Dict[str, Any]:
        """Scan for harmful content patterns."""
        categories = [
            "chemical_biological_weapons",
            "explosives",
            "explosives",
            "malware",
            "csam",
            "targeted_violence",
        ]
        for i, pattern in enumerate(self._harmful_patterns):
            if pattern.search(text):
                return {
                    "detected": True,
                    "category": categories[i] if i < len(categories) else "harmful_content",
                }
        return {"detected": False}

    def _redact_pii(self, text: str) -> Tuple[str, List[str]]:
        """
        Detect and redact PII from text.

        Returns:
            Tuple of (redacted_text, list_of_redacted_field_types)
        """
        redacted_fields = []
        result = text

        for field_type, pattern in self._pii_patterns.items():
            matches = pattern.findall(result)
            if matches:
                result = pattern.sub(f"[REDACTED_{field_type.upper()}]", result)
                redacted_fields.append(field_type)

        return result, redacted_fields

    def _detect_key_leak(self, text: str) -> Dict[str, Any]:
        """Check if any API keys are present in the text."""
        key_patterns = [
            self._pii_patterns.get("api_key_openai"),
            self._pii_patterns.get("api_key_anthropic"),
            self._pii_patterns.get("api_key_generic"),
            self._pii_patterns.get("aws_access_key"),
        ]
        for pattern in key_patterns:
            if pattern and pattern.search(text):
                return {"detected": True}
        return {"detected": False}

    def scan_output(self, text: str) -> Dict[str, Any]:
        """
        Scan model output before returning to user.
        Catches cases where the model might leak sensitive information.
        """
        issues = []

        # Check if output contains injected instructions
        if self._detect_injection(text)["detected"]:
            issues.append("injection_in_output")

        # Check for PII in output
        _, pii_fields = self._redact_pii(text)
        if pii_fields:
            issues.append(f"pii_in_output:{','.join(pii_fields)}")

        return {
            "clean": len(issues) == 0,
            "issues": issues,
        }

    def validate_api_key_format(self, provider: str, key: str) -> bool:
        """Validate that an API key has the expected format."""
        formats = {
            "openai": r"^sk-[a-zA-Z0-9]{20,}$",
            "anthropic": r"^sk-ant-[a-zA-Z0-9-_]{20,}$",
            "groq": r"^gsk_[a-zA-Z0-9]{20,}$",
            "mistral": r"^[a-zA-Z0-9]{32,}$",
        }
        pattern = formats.get(provider)
        if not pattern:
            return True  # Unknown provider, don't validate
        return bool(re.match(pattern, key))

    def hash_for_audit(self, text: str) -> str:
        """
        Create a one-way hash of text for audit purposes.
        The hash proves the text existed without storing the text itself.
        """
        return hashlib.sha256(text.encode()).hexdigest()

    def stats(self) -> Dict[str, Any]:
        """Return security agent statistics."""
        return {
            "total_requests": self._total_requests,
            "total_blocked": self._total_blocked,
            "total_pii_redacted": self._total_pii_redacted,
            "total_injections_caught": self._total_injections_caught,
            "block_rate": (
                self._total_blocked / self._total_requests
                if self._total_requests > 0 else 0
            ),
}
