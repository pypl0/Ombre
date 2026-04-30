"""
Ombre AI Firewall
==================
The world's first indirect prompt injection firewall.

Direct injection: user types malicious instructions
Indirect injection: malicious instructions hidden in:
- Documents the AI reads
- Websites the AI browses  
- Database records the AI queries
- Emails the AI processes
- API responses the AI consumes

This firewall scans ALL of it.
Not just user input. Everything.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Indirect injection patterns — hidden in documents/URLs/data
INDIRECT_PATTERNS = [
    # Hidden instructions in documents
    r"<!--.*?(ignore|disregard|forget|override).*?-->",
    r"\/\*.*?(ignore|disregard|forget|override).*?\*\/",
    r"\[INST\].*?\[/INST\]",
    r"<\|system\|>.*?<\|end\|>",
    # White text / invisible ink attacks
    r"color:\s*white.*?(ignore|override|forget)",
    r"font-size:\s*0.*?(ignore|override|forget)",
    r"opacity:\s*0.*?(ignore|override|forget)",
    # Encoded injection attempts
    r"base64.*?(aWdub3Jl|ZGlzcmVnYXJk)",  # base64 "ignore", "disregard"
    # URL-based injections
    r"https?://.*?\?(.*?(ignore|override|inject|prompt).*?=)",
    # Markdown-hidden injections
    r"\[.*?\]\(.*?(ignore|override|inject).*?\)",
    # Zero-width character attacks
    r"[\u200b\u200c\u200d\ufeff].*?(ignore|override)",
    # Data exfiltration attempts
    r"(send|POST|fetch|curl).*?(password|secret|key|token).*?(http|ftp)",
    r"(summarize|include|repeat|echo).*?(system prompt|instructions|configuration)",
    # Virtualization attacks
    r"(pretend|imagine|simulate|roleplay).*?(no restrictions|no rules|unrestricted)",
    r"(hypothetically|theoretically|in a story).*?(how would|explain how|tell me how)",
]

# Malicious URL patterns
MALICIOUS_URL_PATTERNS = [
    r"http://169\.254\.169\.254",  # AWS metadata
    r"http://metadata\.google\.internal",  # GCP metadata
    r"file://",  # Local file access
    r"javascript:",  # JS injection
    r"data:text/html",  # Data URI injection
]


class AIFirewall:
    """
    Ombre AI Firewall — Indirect injection protection.
    
    Scans documents, URLs, API responses, and all external
    content before it enters AI context.
    """

    def __init__(self, config: Any):
        self.config = config
        self._indirect_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL)
            for p in INDIRECT_PATTERNS
        ]
        self._url_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in MALICIOUS_URL_PATTERNS
        ]
        self._total_scans = 0
        self._total_blocked = 0
        self._indirect_injections_caught = 0

    def process(self, ctx: Any) -> Any:
        """
        Scan all content in context for indirect injection.
        """
        ctx.activate_agent("firewall")
        self._total_scans += 1

        # Scan context documents
        if ctx.context:
            result = self._scan_content(ctx.context, "context")
            if result["detected"]:
                ctx.threats_blocked += 1
                self._total_blocked += 1
                self._indirect_injections_caught += 1
                # Sanitize instead of block — remove the injection
                ctx.context = result["sanitized"]
                logger.warning(
                    f"Indirect injection sanitized | "
                    f"request={ctx.request_id} | "
                    f"type={result['type']}"
                )

        # Scan conversation history
        if ctx.conversation_history:
            clean_history = []
            for msg in ctx.conversation_history:
                content = msg.get("content", "")
                result = self._scan_content(content, "history")
                if result["detected"]:
                    ctx.threats_blocked += 1
                    self._indirect_injections_caught += 1
                    msg = {**msg, "content": result["sanitized"]}
                clean_history.append(msg)
            ctx.conversation_history = clean_history

        # Scan persistent facts
        if ctx.persistent_facts:
            clean_facts = []
            for fact in ctx.persistent_facts:
                result = self._scan_content(fact, "facts")
                if not result["detected"]:
                    clean_facts.append(fact)
                else:
                    ctx.threats_blocked += 1
                    self._indirect_injections_caught += 1
                    logger.warning(
                        f"Malicious fact blocked | request={ctx.request_id}"
                    )
            ctx.persistent_facts = clean_facts

        return ctx

    def scan_document(self, content: str) -> Dict[str, Any]:
        """
        Scan an external document before feeding to AI.
        Use this before loading any external content into context.
        """
        result = self._scan_content(content, "document")
        return {
            "safe": not result["detected"],
            "sanitized": result["sanitized"],
            "threats_found": result["threats"],
            "injection_type": result.get("type"),
        }

    def scan_url_content(self, url: str, content: str) -> Dict[str, Any]:
        """
        Scan URL and its content before AI processes it.
        """
        # Check URL itself
        for pattern in self._url_patterns:
            if pattern.search(url):
                return {
                    "safe": False,
                    "reason": f"Malicious URL pattern detected: {url[:50]}",
                    "sanitized": "",
                }

        # Check content
        return self.scan_document(content)

    def _scan_content(
        self,
        text: str,
        source: str,
    ) -> Dict[str, Any]:
        """Scan text for indirect injection patterns."""
        threats = []
        sanitized = text

        for i, pattern in enumerate(self._indirect_patterns):
            matches = pattern.findall(sanitized)
            if matches:
                threats.append({
                    "pattern": INDIRECT_PATTERNS[i][:50],
                    "source": source,
                    "count": len(matches),
                })
                # Remove the injection attempt
                sanitized = pattern.sub("[CONTENT REMOVED BY OMBRE FIREWALL]", sanitized)

        return {
            "detected": len(threats) > 0,
            "threats": threats,
            "sanitized": sanitized,
            "type": threats[0]["pattern"] if threats else None,
        }

    def stats(self) -> Dict[str, Any]:
        return {
            "total_scans": self._total_scans,
            "total_blocked": self._total_blocked,
            "indirect_injections_caught": self._indirect_injections_caught,
}
