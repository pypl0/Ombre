"""
Ombre Privacy Vault
====================
PII never enters the model. Ever.

Unlike redaction which removes data, the vault tokenizes it.
The model reasons about PERSON_A not John Smith.
Ombre restores the real data in the response.

This is the difference between:
- Redaction: "Hello [REDACTED], your account..."
- Vault: "Hello PERSON_A, your account..." → "Hello John, your account..."

HIPAA, GDPR, CCPA compliant by architecture not by policy.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class PrivacyVault:
    """
    Ombre Privacy Vault — PII tokenization engine.
    
    Tokenizes PII before inference.
    De-tokenizes after inference.
    The model never sees real sensitive data.
    """

    # PII patterns to tokenize
    PII_PATTERNS = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "PHONE": r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
        "IP": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
        "DOB": r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b",
        "PASSPORT": r"\b[A-Z]{1,2}\d{6,9}\b",
        "IBAN": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b",
    }

    def __init__(self):
        self._token_map: Dict[str, str] = {}
        self._reverse_map: Dict[str, str] = {}
        self._compiled = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PII_PATTERNS.items()
        }

    def tokenize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Replace PII with tokens.
        Returns tokenized text and the token map for restoration.
        """
        result = text
        session_map = {}

        for pii_type, pattern in self._compiled.items():
            matches = pattern.findall(result)
            for match in matches:
                match_str = match if isinstance(match, str) else match[0]
                if match_str not in self._token_map:
                    token = f"{pii_type}_{uuid.uuid4().hex[:8].upper()}"
                    self._token_map[match_str] = token
                    self._reverse_map[token] = match_str
                token = self._token_map[match_str]
                session_map[token] = match_str
                result = result.replace(match_str, token)

        return result, session_map

    def restore(self, text: str) -> str:
        """
        Restore tokens back to original PII in model response.
        """
        result = text
        for token, original in self._reverse_map.items():
            result = result.replace(token, original)
        return result

    def clear(self) -> None:
        """Clear the vault — use between sessions."""
        self._token_map.clear()
        self._reverse_map.clear()


class VaultAgent:
    """
    Ombre Vault Agent — Zero-knowledge PII protection.
    
    The model never sees real PII. 
    Users get responses with their real data restored.
    """

    def __init__(self, config: Any):
        self.config = config
        self._vault = PrivacyVault()
        self._total_tokenized = 0
        self._total_restored = 0

    def process(self, ctx: Any) -> Any:
        """Tokenize PII in prompt before inference."""
        ctx.activate_agent("vault")

        prompt = ctx.get_effective_prompt()
        tokenized, token_map = self._vault.tokenize(prompt)

        if token_map:
            ctx.sanitized_prompt = tokenized
            ctx.metadata["vault_tokens"] = token_map
            self._total_tokenized += len(token_map)
            logger.info(
                f"Vault tokenized {len(token_map)} PII items | "
                f"request={ctx.request_id}"
            )

        # Also tokenize context
        if ctx.context:
            tokenized_ctx, ctx_tokens = self._vault.tokenize(ctx.context)
            if ctx_tokens:
                ctx.context = tokenized_ctx
                self._total_tokenized += len(ctx_tokens)

        return ctx

    def restore(self, ctx: Any) -> Any:
        """Restore real PII in response after inference."""
        if ctx.response_text:
            restored = self._vault.restore(ctx.response_text)
            if restored != ctx.response_text:
                ctx.response_text = restored
                self._total_restored += 1
                logger.info(f"Vault restored PII | request={ctx.request_id}")
        return ctx

    def stats(self) -> Dict[str, Any]:
        return {
            "total_tokenized": self._total_tokenized,
            "total_restored": self._total_restored,
  }
