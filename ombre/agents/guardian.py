"""
Ombre Guardian
===============
The defensive AI security agent.

While Claude Mythos Preview found zero-day vulnerabilities
for the world's largest companies — Guardian brings that
same defensive capability to every developer, every startup,
every company that can't afford a $100M Project Glasswing
membership.

Guardian does four things:
1. Scans AI application code for security vulnerabilities
2. Detects zero-day patterns before attackers find them
3. Monitors runtime behavior for anomalies
4. Reports vulnerabilities to the right people automatically

This is the defensive answer to Mythos.
Open source. Free. For everyone.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.intelligence import ThreatIntelligenceBus, ThreatSignal
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# VULNERABILITY PATTERNS
# Based on OWASP Top 10, NIST NVD, CWE database
# ─────────────────────────────────────────────────────────────

AI_SPECIFIC_VULNERABILITIES = {
    "PROMPT_INJECTION_SURFACE": {
        "pattern": r"(f\"|f').*?\{.*?(user_input|prompt|query|message|request).*?\}",
        "severity": "critical",
        "cwe": "CWE-77",
        "description": "Direct user input interpolated into prompt without sanitization",
        "remediation": "Use Ombre's SecurityAgent to sanitize all user input before interpolation",
    },
    "UNVALIDATED_LLM_OUTPUT": {
        "pattern": r"(eval|exec|subprocess)\s*\(.*?(llm|ai|gpt|claude|response|output)",
        "severity": "critical",
        "cwe": "CWE-94",
        "description": "LLM output executed without validation — code injection risk",
        "remediation": "Never execute LLM output directly. Validate against allowlist first.",
    },
    "API_KEY_IN_CODE": {
        "pattern": r"(openai|anthropic|groq|mistral).*?['\"]sk-[a-zA-Z0-9]{20,}['\"]",
        "severity": "critical",
        "cwe": "CWE-312",
        "description": "API key hardcoded in source code",
        "remediation": "Use environment variables. Never hardcode API keys.",
    },
    "INSECURE_DESERIALIZATION": {
        "pattern": r"pickle\.loads.*?(llm|ai|model|response)",
        "severity": "high",
        "cwe": "CWE-502",
        "description": "Deserializing untrusted AI output with pickle",
        "remediation": "Use JSON deserialization. Never use pickle with untrusted data.",
    },
    "MISSING_RATE_LIMIT": {
        "pattern": r"(def|async def)\s+\w+.*?openai|anthropic|groq.*?(?!rate_limit|throttle|limit)",
        "severity": "high",
        "cwe": "CWE-770",
        "description": "AI API calls without rate limiting — DoS and cost exhaustion risk",
        "remediation": "Implement rate limiting on all AI endpoints.",
    },
    "UNENCRYPTED_AI_MEMORY": {
        "pattern": r"(json\.dump|open.*?w).*?(memory|history|conversation|chat_history)",
        "severity": "high",
        "cwe": "CWE-312",
        "description": "AI conversation history stored without encryption",
        "remediation": "Use Ombre's MemoryAgent which encrypts all stored data with AES-256.",
    },
    "VERBOSE_AI_ERRORS": {
        "pattern": r"(print|logger|log)\s*\(.*?(traceback|exception|error).*?(prompt|model|api)",
        "severity": "medium",
        "cwe": "CWE-209",
        "description": "AI errors exposed with sensitive context information",
        "remediation": "Sanitize error messages before logging or displaying.",
    },
    "CORS_UNRESTRICTED_AI_API": {
        "pattern": r"(CORS|Access-Control-Allow-Origin).*?\*.*?(ai|llm|gpt|claude)",
        "severity": "high",
        "cwe": "CWE-942",
        "description": "AI API endpoint accessible from any origin",
        "remediation": "Restrict CORS to known trusted origins only.",
    },
    "SQL_INJECTION_IN_RAG": {
        "pattern": r"(cursor\.execute|query|SELECT|INSERT).*?\+.*?(user_input|query|question|prompt)",
        "severity": "critical",
        "cwe": "CWE-89",
        "description": "SQL injection risk in RAG database queries",
        "remediation": "Use parameterized queries. Never concatenate user input into SQL.",
    },
    "INSECURE_TOOL_CALL": {
        "pattern": r"(os\.system|subprocess\.call|shell=True).*?(llm|ai|gpt|tool_call|function_call)",
        "severity": "critical",
        "cwe": "CWE-78",
        "description": "Shell commands executed from AI tool calls without validation",
        "remediation": "Validate all AI tool calls against a strict allowlist before execution.",
    },
    "MISSING_OUTPUT_VALIDATION": {
        "pattern": r"return\s+(response|output|result|completion)(?!.*?(validate|sanitize|check|filter))",
        "severity": "medium",
        "cwe": "CWE-20",
        "description": "AI output returned to user without validation",
        "remediation": "Use Ombre's ReliabilityAgent to validate all AI outputs.",
    },
    "HARDCODED_SYSTEM_PROMPT": {
        "pattern": r"system.*?=.*?['\"].*?(ignore|disregard|pretend|you are now)",
        "severity": "high",
        "cwe": "CWE-798",
        "description": "Potentially manipulable system prompt hardcoded",
        "remediation": "Review system prompts for injection vulnerabilities.",
    },
}

RUNTIME_ANOMALY_PATTERNS = [
    "unusual_token_spike",
    "repeated_injection_attempts",
    "credential_probing",
    "data_exfiltration_pattern",
    "model_confusion_attack",
    "context_overflow_attempt",
]


@dataclass
class Vulnerability:
    """A discovered security vulnerability."""
    id: str
    type: str
    severity: str
    cwe: str
    description: str
    remediation: str
    location: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    discovered_at: float = field(default_factory=time.time)
    zero_day_candidate: bool = False
    cvss_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "cwe": self.cwe,
            "cvss_score": self.cvss_score,
            "description": self.description,
            "remediation": self.remediation,
            "location": self.location,
            "line_number": self.line_number,
            "zero_day_candidate": self.zero_day_candidate,
            "discovered_at": self.discovered_at,
        }


class GuardianAgent:
    """
    Ombre Guardian — Defensive AI Security Intelligence.

    The open source answer to Project Glasswing.
    
    Guardian continuously monitors your AI application for:
    - Code-level vulnerabilities (static analysis)
    - Runtime behavioral anomalies (dynamic analysis)
    - Zero-day pattern candidates
    - Emerging attack vectors
    
    When vulnerabilities are found, Guardian:
    - Classifies by severity (Critical/High/Medium/Low)
    - Maps to CWE/CVE standards
    - Generates remediation guidance
    - Notifies the right people
    - Creates audit trail for compliance
    
    Benchmark performance targets:
    - CVEfixes dataset: >85% detection rate
    - OWASP Top 10: 100% coverage
    - CWE Top 25: >90% detection rate
    - False positive rate: <5%
    """

    VERSION = "1.0.0"
    BENCHMARK_TARGETS = {
        "owasp_top10_coverage": 1.0,
        "cwe_top25_detection": 0.90,
        "false_positive_rate": 0.05,
        "zero_day_detection": 0.75,
    }

    def __init__(
        self,
        config: Any,
        intel_bus: Optional[ThreatIntelligenceBus] = None,
    ):
        self.config = config
        self.intel = intel_bus
        self._vulnerabilities: List[Vulnerability] = []
        self._scan_count = 0
        self._runtime_events: List[Dict[str, Any]] = []
        self._notification_callbacks: List[Any] = []
        self._compiled_patterns = {
            name: re.compile(vuln["pattern"], re.IGNORECASE | re.MULTILINE)
            for name, vuln in AI_SPECIFIC_VULNERABILITIES.items()
        }
        logger.info(f"Guardian v{self.VERSION} initialized")

    def process(self, ctx: Any) -> Any:
        """
        Runtime security monitoring on every request.
        Guardian watches behavioral patterns in real time.
        """
        ctx.activate_agent("guardian")

        # Runtime anomaly detection
        anomalies = self._detect_runtime_anomalies(ctx)

        if anomalies:
            for anomaly in anomalies:
                ctx.threats_blocked += 1
                ctx.compliance_flags.append(f"guardian:{anomaly}")

                if self.intel:
                    self.intel.emit(ThreatSignal(
                        agent="guardian",
                        threat_type=anomaly,
                        severity="high",
                        confidence=0.85,
                        detail=f"Runtime anomaly detected: {anomaly}",
                        metadata={
                            "user_id": ctx.user_id,
                            "session_id": ctx.session_id,
                            "request_id": ctx.request_id,
                        },
                    ))

        self._runtime_events.append({
            "request_id": ctx.request_id,
            "timestamp": time.time(),
            "anomalies": anomalies,
            "tokens_used": ctx.tokens_used,
            "model": ctx.selected_model,
        })

        return ctx

    def scan_code(
        self,
        code: str,
        filename: str = "unknown",
    ) -> List[Vulnerability]:
        """
        Static analysis scan of AI application code.
        
        Detects vulnerabilities before they reach production.
        Maps findings to CWE standards for compliance.
        
        Args:
            code: Python source code to scan
            filename: File being scanned (for reporting)
            
        Returns:
            List of discovered vulnerabilities
        """
        self._scan_count += 1
        discovered = []
        lines = code.split("\n")

        for vuln_name, vuln_config in AI_SPECIFIC_VULNERABILITIES.items():
            pattern = self._compiled_patterns[vuln_name]
            for line_num, line in enumerate(lines, 1):
                if pattern.search(line):
                    vuln_id = self._generate_vuln_id(
                        vuln_name, filename, line_num
                    )
                    vuln = Vulnerability(
                        id=vuln_id,
                        type=vuln_name,
                        severity=vuln_config["severity"],
                        cwe=vuln_config["cwe"],
                        description=vuln_config["description"],
                        remediation=vuln_config["remediation"],
                        location=f"{filename}:{line_num}",
                        line_number=line_num,
                        code_snippet=line.strip()[:200],
                        cvss_score=self._estimate_cvss(vuln_config["severity"]),
                    )
                    discovered.append(vuln)
                    self._vulnerabilities.append(vuln)

        # Zero-day candidate detection
        zero_days = self._detect_zero_day_candidates(code, filename)
        discovered.extend(zero_days)

        logger.info(
            f"Guardian scan complete | "
            f"file={filename} | "
            f"vulnerabilities={len(discovered)}"
        )

        # Notify if critical vulnerabilities found
        critical = [v for v in discovered if v.severity == "critical"]
        if critical:
            self._notify_critical(critical, filename)

        return discovered

    def scan_repository(
        self,
        path: str,
        extensions: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan an entire repository for AI security vulnerabilities.
        
        Args:
            path: Path to repository root
            extensions: File extensions to scan (default: .py)
            
        Returns:
            Full vulnerability report
        """
        if extensions is None:
            extensions = [".py"]

        repo_path = Path(path)
        all_vulnerabilities = []
        files_scanned = 0

        for ext in extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                try:
                    code = file_path.read_text(encoding="utf-8", errors="ignore")
                    vulns = self.scan_code(code, str(file_path))
                    all_vulnerabilities.extend(vulns)
                    files_scanned += 1
                except Exception as e:
                    logger.debug(f"Could not scan {file_path}: {e}")

        return self._generate_report(all_vulnerabilities, files_scanned, path)

    def _detect_runtime_anomalies(self, ctx: Any) -> List[str]:
        """
        Detect anomalous runtime behavior patterns.
        These indicate active attacks in progress.
        """
        anomalies = []
        recent = self._runtime_events[-20:] if self._runtime_events else []

        # Token spike detection — possible prompt stuffing attack
        if ctx.tokens_used > 8000:
            anomalies.append("unusual_token_spike")

        # Repeated injection attempts from same session
        session_events = [
            e for e in recent
            if e.get("session_id") == ctx.session_id
        ]
        if len(session_events) > 10:
            anomalies.append("high_frequency_requests")

        # Detect context overflow attempts
        prompt_length = len(ctx.get_effective_prompt())
        if prompt_length > 50000:
            anomalies.append("context_overflow_attempt")

        # Detect probing patterns in metadata
        if ctx.threats_blocked > 3:
            anomalies.append("repeated_attack_pattern")

        return anomalies

    def _detect_zero_day_candidates(
        self,
        code: str,
        filename: str,
    ) -> List[Vulnerability]:
        """
        Detect patterns that may be novel zero-day vulnerabilities.
        
        These are patterns that don't match known CVEs but
        exhibit characteristics of exploitable vulnerabilities.
        """
        candidates = []

        # Pattern: Unvalidated external data flowing into AI context
        unvalidated_flow = re.findall(
            r"(requests\.get|urllib|httpx|aiohttp).*?\n.*?(prompt|context|message)\s*[+=]",
            code, re.MULTILINE
        )
        if unvalidated_flow:
            vuln_id = self._generate_vuln_id("ZERO_DAY", filename, 0)
            candidates.append(Vulnerability(
                id=vuln_id,
                type="UNVALIDATED_EXTERNAL_DATA_FLOW",
                severity="high",
                cwe="CWE-20",
                description="External HTTP response flows directly into AI context without validation — potential indirect injection zero-day",
                remediation="Validate all external content with Ombre's AIFirewall before adding to AI context",
                location=filename,
                zero_day_candidate=True,
                cvss_score=7.5,
            ))

        # Pattern: AI output used in file operations without validation
        file_from_ai = re.findall(
            r"(open|write|mkdir|makedirs).*?\n.*?(llm|ai|gpt|claude|response)",
            code, re.MULTILINE
        )
        if file_from_ai:
            vuln_id = self._generate_vuln_id("ZERO_DAY_FILE", filename, 0)
            candidates.append(Vulnerability(
                id=vuln_id,
                type="AI_OUTPUT_FILE_OPERATION",
                severity="critical",
                cwe="CWE-73",
                description="AI model output used in file system operations — path traversal and arbitrary write zero-day candidate",
                remediation="Never use AI output directly in file operations. Validate path and content against strict allowlist.",
                location=filename,
                zero_day_candidate=True,
                cvss_score=9.1,
            ))

        return candidates

    def _generate_report(
        self,
        vulnerabilities: List[Vulnerability],
        files_scanned: int,
        scan_target: str,
    ) -> Dict[str, Any]:
        """Generate a full vulnerability report."""
        critical = [v for v in vulnerabilities if v.severity == "critical"]
        high = [v for v in vulnerabilities if v.severity == "high"]
        medium = [v for v in vulnerabilities if v.severity == "medium"]
        low = [v for v in vulnerabilities if v.severity == "low"]
        zero_days = [v for v in vulnerabilities if v.zero_day_candidate]

        cwe_coverage = len(set(v.cwe for v in vulnerabilities))
        report_hash = hashlib.sha256(
            json.dumps([v.id for v in vulnerabilities]).encode()
        ).hexdigest()

        return {
            "guardian_version": self.VERSION,
            "scan_target": scan_target,
            "scan_timestamp": time.time(),
            "report_hash": report_hash,
            "summary": {
                "files_scanned": files_scanned,
                "total_vulnerabilities": len(vulnerabilities),
                "critical": len(critical),
                "high": len(high),
                "medium": len(medium),
                "low": len(low),
                "zero_day_candidates": len(zero_days),
                "cwe_categories_found": cwe_coverage,
            },
            "risk_score": self._calculate_risk_score(vulnerabilities),
            "vulnerabilities": {
                "critical": [v.to_dict() for v in critical],
                "high": [v.to_dict() for v in high],
                "medium": [v.to_dict() for v in medium],
                "low": [v.to_dict() for v in low],
                "zero_day_candidates": [v.to_dict() for v in zero_days],
            },
            "compliance": {
                "owasp_top10_coverage": self._check_owasp_coverage(vulnerabilities),
                "cwe_top25_coverage": self._check_cwe_coverage(vulnerabilities),
            },
            "remediation_priority": [
                v.to_dict() for v in sorted(
                    vulnerabilities,
                    key=lambda x: x.cvss_score or 0,
                    reverse=True,
                )[:5]
            ],
        }

    def _calculate_risk_score(self, vulnerabilities: List[Vulnerability]) -> float:
        """Calculate overall risk score 0-10."""
        if not vulnerabilities:
            return 0.0
        weights = {"critical": 4, "high": 2, "medium": 1, "low": 0.5}
        total = sum(weights.get(v.severity, 0) for v in vulnerabilities)
        return min(10.0, round(total / len(vulnerabilities) * 2, 1))

    def _check_owasp_coverage(self, vulnerabilities: List[Vulnerability]) -> float:
        """Check OWASP Top 10 coverage."""
        owasp_cwes = {
            "CWE-77", "CWE-89", "CWE-94", "CWE-312",
            "CWE-502", "CWE-770", "CWE-78", "CWE-20",
            "CWE-942", "CWE-798",
        }
        found_cwes = {v.cwe for v in vulnerabilities}
        covered = len(owasp_cwes & found_cwes)
        return round(covered / len(owasp_cwes), 2)

    def _check_cwe_coverage(self, vulnerabilities: List[Vulnerability]) -> float:
        """Check CWE Top 25 coverage."""
        cwe_top25 = {
            "CWE-787", "CWE-79", "CWE-89", "CWE-416",
            "CWE-78", "CWE-20", "CWE-125", "CWE-22",
            "CWE-352", "CWE-434", "CWE-862", "CWE-476",
            "CWE-287", "CWE-190", "CWE-502", "CWE-77",
            "CWE-119", "CWE-798", "CWE-918", "CWE-306",
            "CWE-362", "CWE-269", "CWE-94", "CWE-863",
            "CWE-276",
        }
        found_cwes = {v.cwe for v in vulnerabilities}
        covered = len(cwe_top25 & found_cwes)
        return round(covered / len(cwe_top25), 2)

    def _estimate_cvss(self, severity: str) -> float:
        """Estimate CVSS score from severity."""
        return {"critical": 9.1, "h
